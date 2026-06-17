# Bàn giao — Agent `clean-transcript-to-report`

Bộ bàn giao đầy đủ cho agent hợp nhất **clean-transcript-to-report**: một web app / một
container, hai bước trong cùng pipeline.

1. **Clean** — upload `.vtt` (Teams) / `.docx` / `.txt` → parse trong trình duyệt → bật/tắt rule →
   làm sạch bằng LLM (proxy `POST /api/chat`). Người dùng review/sửa transcript đã sạch.
2. **Analyze (Route A)** — transcript đã sạch (1 file) → report HTML theo loại `cs` / `ux` / `meeting`.

> Route B (multi-file ladder) đã được gỡ bỏ khỏi agent này.

## 1. Thông tin triển khai hiện tại

| Hạng mục | Giá trị |
|---|---|
| Image đã push | `vcr.vngcloud.vn/111480-abp111918/clean-transcript-to-report:v20260616204548` |
| Registry | `vcr.vngcloud.vn` — project `111480-abp111918` |
| Entrypoint | `python -m app.server` (Starlette, port 8080, health `ping`) |
| Runtime ID | `runtime-848289ef-3835-48d4-9f28-85421c1a850c` |
| Endpoint | `https://endpoint-74802de2-5e06-412b-bb9b-d75f71bf46f6.agentbase-runtime.aiplatform.vngcloud.vn` |
| Network mode | PUBLIC (không auth — xem mục Bảo mật) |

## 2. Cấu trúc bộ bàn giao

```
clean-transcript-to-report-handover/
├── HANDOVER.md                  ← file này (điểm vào)
├── DEPLOY.md                    ← hướng dẫn build/push image + tạo runtime (tự chứa)
├── src/                         ← toàn bộ source code (đã loại secret/cache/venv)
│   ├── app/                     ← code agent: server, pipeline, gate, llm, render, prompts...
│   ├── Dockerfile               ← build image (python:3.13-slim, port 8080)
│   ├── requirements.txt
│   ├── .dockerignore
│   ├── .env.example             ← MẪU cấu hình LLM (điền key thật, đừng commit .env)
│   └── .greennode.json.example  ← MẪU credential GreenNode (client_id/secret)
└── docs/                        ← tài liệu liên quan
    ├── INDEX.md                 ← mục lục tài liệu
    ├── 01-agent-README.md       ← README chính: kiến trúc, pipeline, run/deploy
    ├── 02-clean-pipeline-9-rules.md ← spec làm sạch 9-stage (đứng sau Bước 1)
    └── prompts/                 ← Brain prompt phân tích: cs / ux / meeting
```

## 3. Chạy local

```bash
cd src
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # rồi điền LLM_API_KEY / LLM_BASE_URL / LLM_MODEL thật
python -m app.server            # http://localhost:8080
```

## 4. Build & deploy lại

Xem **`DEPLOY.md`** — hướng dẫn đầy đủ, tự chứa:
- **Phần A** (build & push image): chỉ cần Docker + credential Container Registry. Đã verify build OK.
- **Phần B** (tạo/cập nhật runtime): qua skill GreenNode AgentBase trong Claude Code **hoặc** web console.

> ⚠️ Lệnh deploy `runtime.sh` thuộc **skill GreenNode AgentBase**, **không** kèm trong package này.
> Người nhận deploy qua skill đó (Claude Code) hoặc qua GreenNode Console — `DEPLOY.md` mô tả cả hai
> kèm đầy đủ tham số runtime.

Env bắt buộc khi deploy: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`
(tuỳ chọn: `LLM_RPM_DEFAULT`, `LLM_RPM_LIMITS`).

> ⚠️ Phải set **cả 3** biến LLM. Chỉ `LLM_API_KEY` là **không đủ** — Clean lẫn Analyze sẽ hỏng (xem ghi chú env trong `DEPLOY.md`).
> `LLM_MODEL` nên dùng model chain `qwen/qwen3-5-27b,qwen/qwen3.6-27b` (đã verify chạy). `qwen/qwen3.7-plus` bị rate-limit cứng.

## 5. ⚠️ Bảo mật — đọc trước khi bàn giao

- Bộ này **đã loại** mọi secret: `.env` thật, `.greennode.json` thật, `.agentbase/`, cache.
  Chỉ còn các file `*.example` với placeholder. Người nhận tự điền key của họ.
- **Rotate ngay** các credential sau nếu chúng từng được chia sẻ ở bản gốc:
  - `LLM_API_KEY` (MaaS GreenNode AI Platform)
  - `client_id` / `client_secret` trong `.greennode.json`
- Endpoint hiện ở **PUBLIC, không auth** — bất kỳ ai có URL đều gọi được và tiêu quota key.
  Cân nhắc chuyển sang **VPC mode** hoặc thêm token bảo vệ trước khi giao cho bên ngoài.
