# Transcript Agent — Clean → Report (merged)

Một agent **duy nhất**, hai bước trong cùng một web app / một container:

1. **Làm sạch (Clean)** — upload `.vtt` (Teams) / `.docx` / `.txt`, parse trong trình duyệt, bật/tắt 9 rule + custom rule, làm sạch bằng LLM. Bạn **xem lại / chỉnh sửa** transcript đã sạch.
2. **Phân tích (Analyze, Route A)** — transcript đã sạch (1 file) → report HTML theo loại `cs` / `ux` / `meeting`.

> Đây là kết quả gộp 2 agent cũ (`clean-transcript/` + `analyzer/`). Phần phân tích **chỉ còn Route A** (single file); toàn bộ Route B (multi-file `qual_pipeline` ladder) đã được gỡ bỏ.

## Kiến trúc

```
[app/templates/ui.html]  React SPA (CDN, không build) — 1 trang, 2 bước
   │  Bước 1: parse .vtt/.docx/.txt → ghép rule 9 stage → POST /api/chat (làm sạch)
   │  Bước 2: transcript đã sạch (đã review/sửa) → POST /invocations (phân tích)
   ▼
[app/server.py]  GreenNode AgentBase SDK (Starlette, port 8080)
   ├─ GET  /            wizard UI
   ├─ POST /api/chat    proxy LLM cho bước làm sạch (gắn LLM_API_KEY server-side)
   ├─ POST /invocations entrypoint phân tích (ingest → gate → prepare → analyze_single → render)
   └─ ping              health
   ▼
[GreenNode AI Platform]  OpenAI-compatible · qwen/...
```

Cả hai bước dùng chung 1 endpoint LLM (`LLM_BASE_URL`) và 1 key (`LLM_API_KEY`). Key chỉ nằm ở server — bước làm sạch gọi qua proxy `/api/chat` nên key không lộ ra trình duyệt và không vướng CORS.

## Pipeline phân tích (Route A)

`app/pipeline.py`: `ingest → gate → prepare → analyze_single → render_report`.

- **gate** (`app/gate.py`): bắt buộc `objectives`, đúng **1 file**, đủ độ dài tối thiểu theo loại (ux 500 / cs 300 / meeting 500 từ) — chạy **trước** mọi lần gọi LLM.
- **analyze_single** (`app/analyze_single.py`): nhồi objectives + transcript vào Brain prompt theo loại, gọi LLM trả JSON validate bằng schema (`app/brain_schema.py`).
- **render** (`app/render/render.py`): Python dựng toàn bộ HTML từ JSON.
- **governor** (`app/governor.py`): rate-limit per-(account, model) — đã chuyển từ `qual_pipeline` sang `app` khi gỡ Route B.

## Chạy local

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
# .env: LLM_API_KEY + LLM_BASE_URL + LLM_MODEL (xem .env mẫu)
python -m app.server          # http://localhost:8080
```

## Deploy lên GreenNode AgentBase

Đóng gói sẵn (`Dockerfile`, port 8080, `ping` health). 1 image, 1 runtime cho cả 2 bước.

```bash
docker build --platform linux/amd64 -t <registry>/transcript-agent:<tag> .
docker push <registry>/transcript-agent:<tag>

runtime.sh create --name transcript-agent \
  --image <registry>/transcript-agent:<tag> \
  --flavor runtime-s2-general-2x4 \
  --env-file .env --from-cr --network-mode PUBLIC \
  --min-replicas 1 --max-replicas 1
```

Env cần có: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` (+ tuỳ chọn `LLM_RPM_DEFAULT`, `LLM_RPM_LIMITS`).

> Endpoint PUBLIC không auth — ai có URL đều dùng được và tiêu quota key. Cân nhắc đổi sang VPC mode hoặc thêm token bảo vệ.

## Bảo mật

`.env`, `.greennode.json`, `.agentbase/` đã nằm trong `.dockerignore` + `.gitignore` — không vào image/repo. **Lưu ý:** key MaaS và `.greennode.json` (client_id/secret) đang ở dạng plaintext trên đĩa — nên rotate nếu đã từng chia sẻ.
