# DEPLOY — clean-transcript-to-report

Hướng dẫn deploy tự chứa. **Phần A (build & push image)** chỉ cần Docker + credential
Container Registry — không phụ thuộc công cụ ngoài. **Phần B (tạo/cập nhật runtime)** làm qua
GreenNode AgentBase (skill Claude Code hoặc web console).

---

## 0. Thứ người nhận PHẢI tự chuẩn bị (không kèm trong package)

| Cần | Lấy ở đâu |
|---|---|
| `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` | MaaS GreenNode AI Platform → điền vào `src/.env` |
| Credential Container Registry (username + password/token) | GreenNode Console → Container Registry → repo `111480-abp111918` |
| `client_id` / `client_secret` GreenNode | GreenNode Console → IAM → điền vào `src/.greennode.json` (nếu deploy bằng skill/CLI) |
| Docker (buildx, hỗ trợ `--platform linux/amd64`) | cài sẵn trên máy build |

```bash
cd src
cp .env.example .env                       # rồi điền key/model thật
cp .greennode.json.example .greennode.json # rồi điền client_id/secret (chỉ cần cho Phần B qua CLI)
```

---

## Phần A — Build & push image (tự chứa, chỉ cần Docker)

```bash
cd src
REG=vcr.vngcloud.vn/111480-abp111918
TAG=v$(date +%Y%m%d%H%M%S)

# 1. Đăng nhập registry (nhập username + password/token của CR)
docker login vcr.vngcloud.vn

# 2. Build cho linux/amd64 (BẮT BUỘC — runtime chạy amd64)
docker build --platform linux/amd64 -t $REG/clean-transcript-to-report:$TAG .

# 3. Push
docker push $REG/clean-transcript-to-report:$TAG
echo "Image: $REG/clean-transcript-to-report:$TAG"
```

> Đã verify: image build từ `src/` thành công, container chạy và phục vụ `GET / → 200`.

---

## Phần B — Tạo / cập nhật runtime trên GreenNode AgentBase

Cần image ở Phần A. Chọn **một** trong hai cách.

### Tham số runtime (dùng chung cho cả hai cách)

| Tham số | Giá trị |
|---|---|
| Image | `vcr.vngcloud.vn/111480-abp111918/clean-transcript-to-report:<TAG>` |
| Port | `8080` |
| Health check | `ping` (cơ chế nội bộ của SDK AgentBase, không phải HTTP `/ping`) |
| Flavor | `runtime-s2-general-2x4` |
| Replicas | min `1`, max `1` |
| Network mode | `PUBLIC` (cân nhắc `VPC` — xem Bảo mật trong HANDOVER.md) |
| Pull từ CR nội bộ | bật (`--from-cr`) |
| Env | `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` (+ tuỳ chọn `LLM_RPM_DEFAULT`, `LLM_RPM_LIMITS`) — từ `.env` |

> ⚠️ **Bắt buộc cả 3 biến LLM, không chỉ `LLM_API_KEY`.** Nếu thiếu `LLM_BASE_URL` → bước Clean POST tới URL rỗng và bước Analyze trỏ nhầm `api.openai.com` (gọi bằng key MaaS → fail). Nếu thiếu `LLM_MODEL` → mặc định `gpt-4o-mini` (không có trên MaaS).
> - `LLM_BASE_URL=https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1`
> - `LLM_MODEL` nên là **model chain** (primary,fallback) để né rate-limit, ví dụ `qwen/qwen3-5-27b,qwen/qwen3.6-27b`. Liệt kê model ENABLED bằng skill `/agentbase-llm`. (Lưu ý: `qwen/qwen3.7-plus` bị rate-limit cứng — tránh dùng đơn lẻ.)

### Cách 1 — Claude Code + skill GreenNode AgentBase (khuyến nghị)

Mở thư mục `src/` trong Claude Code (đã cài plugin/skill `agentbase-deploy`) rồi yêu cầu:
*"deploy agent này lên GreenNode, image `<REG>/clean-transcript-to-report:<TAG>`, flavor
runtime-s2-general-2x4, port 8080, PUBLIC, 1 replica, env từ .env"*.

Tạo mới hoặc cập nhật runtime hiện có:

- **Runtime hiện tại:** `runtime-848289ef-3835-48d4-9f28-85421c1a850c`
- **Endpoint:** `https://endpoint-74802de2-5e06-412b-bb9b-d75f71bf46f6.agentbase-runtime.aiplatform.vngcloud.vn`

Lệnh tương ứng skill chạy (chỉ để tham khảo — `runtime.sh` thuộc skill, **không** kèm trong package):

```bash
# Cập nhật runtime đang chạy sang image mới
runtime.sh update --runtime-id runtime-848289ef-3835-48d4-9f28-85421c1a850c \
  --image $REG/clean-transcript-to-report:$TAG --from-cr

# Hoặc tạo runtime mới
runtime.sh create --name clean-transcript-to-report \
  --image $REG/clean-transcript-to-report:$TAG \
  --flavor runtime-s2-general-2x4 \
  --env-file .env --from-cr --network-mode PUBLIC \
  --min-replicas 1 --max-replicas 1
```

### Cách 2 — GreenNode Console (không cần Claude Code)

Console → AI Platform → AgentBase → Agent Runtimes → *Create / Update* → điền theo bảng tham số ở
trên, set biến môi trường thủ công, chọn image vừa push.

---

## Kiểm tra sau deploy

```bash
# Thay <ENDPOINT> bằng URL runtime
curl -s -X POST https://<ENDPOINT>/invocations \
  -H 'Content-Type: application/json' \
  -d '{"type":"meeting","mode":"single","transcripts":[{"participant":"x","text":"..."}],"objectives":"RQ1 ..."}'
```

Mở `https://<ENDPOINT>/` để dùng wizard UI (Bước 1 Clean → Bước 2 Analyze).
