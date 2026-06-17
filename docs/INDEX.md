# clean-transcript-to-report — Tài liệu tổng hợp

Tổng hợp **chỉ** các tài liệu liên quan đến agent hợp nhất **clean-transcript-to-report**
(một container, hai bước: **Clean** → **Analyze Route A**).

- **Image đã push:** `vcr.vngcloud.vn/111480-abp111918/clean-transcript-to-report:v20260616204548`
- **Source code gốc:** `analyzer/t2r-transcript-report-src/` (CMD `python -m app.server`)
- **Phạm vi:** chỉ Route A (single-file). Toàn bộ Route B (multi-file ladder) đã bị gỡ khỏi agent này.

## Nội dung

| File | Nguồn gốc | Mô tả |
|---|---|---|
| `01-agent-README.md` | `t2r-transcript-report-src/README.md` | Tài liệu chính: kiến trúc, pipeline phân tích, cách chạy local, cách deploy lên GreenNode AgentBase. |
| `02-clean-pipeline-9-rules.md` | `claw-a-thon-demo-agent/zalopay_transcript_cleaning_pipeline.md` | Spec đầy đủ pipeline làm sạch (9 stage, Precision > Recall) đứng sau **Bước 1 — Clean**. |
| `prompts/cs.md` | `app/prompts/cs.md` | Brain prompt phân tích loại **CS** (customer support). |
| `prompts/ux.md` | `app/prompts/ux.md` | Brain prompt phân tích loại **UX** research. |
| `prompts/meeting.md` | `app/prompts/meeting.md` | Brain prompt phân tích loại **meeting**. |

## Đã loại ra (không liên quan đến agent mới)

| File | Lý do loại |
|---|---|
| `analyzer/TRANSCRIPT_FORMAT.md` | Chỉ áp dụng cho **Route B** (multi-file ladder) — đã bị gỡ khỏi agent này. |
| `clean-transcript/README.md` | Folder đã **deprecated**, chỉ là redirect sang `t2r-transcript-report-src/`. |
| `clean-transcript/transcript_cleaner_handoff_brief.md` | Mô tả stack **cũ** (React artifact + Anthropic API), đã được thay bằng `app/templates/ui.html` + proxy `/api/chat`. |

> Đây là bản **copy** — tài liệu gốc vẫn nằm nguyên ở vị trí cũ. Nếu cần kéo thêm bất kỳ file nào trong danh sách loại ra, báo mình.
