# Zalopay Transcript Cleaning — Master Pipeline Document

> **Phạm vi áp dụng:** Transcript phỏng vấn người dùng (UX research), tiếng Việt + code-switching tiếng Anh, có thể có giọng miền Nam. Output dùng để feed vào NLP/AI model downstream.
>
> **Nguyên tắc xuyên suốt:** Precision > Recall. Thà bỏ sót một lỗi còn hơn sửa sai một từ đúng. Giữ nguyên giọng nói tự nhiên của người dùng — không chuẩn hóa về văn phong formal.

---

## Sơ đồ pipeline tổng thể

```
INPUT: Raw ASR transcript
        │
        ▼
[STAGE 0] Pre-processing & Detection
        │  ├── 0A. Normalize encoding & whitespace
        │  ├── 0B. Detect regional accent (miền Nam?)
        │  └── 0C. Detect topic context (tài chính / mua sắm / trải nghiệm...)
        │
        ▼
[STAGE 1] Token Locking — Đánh dấu vùng không được sửa
        │  ├── 1A. Lock số điện thoại, mã giao dịch, OTP, mã số
        │  └── 1B. Lock timestamp, speaker label
        │
        ▼
[STAGE 2] Lỗi ASR nặng — Sửa trước khi làm gì khác
        │  ├── 2A. Brand & App lexicon replacement
        │  ├── 2B. Code-switching correction
        │  └── 2C. Giọng miền Nam — Tầng 1 (auto-fix không cần context)
        │
        ▼
[STAGE 3] Số & Đơn vị
        │  ├── 3A. Lỗi "năm" vs số 5
        │  └── 3B. Đơn vị tiền tệ
        │
        ▼
[STAGE 4] Từ cuối câu & Filler
        │  ├── 4A. Xóa filler word
        │  ├── 4B. Sửa cảm thán từ bị detect sai
        │  └── 4C. Self-correction pattern
        │
        ▼
[STAGE 5] Giọng miền Nam — Tầng 2 & 3
        │  ├── 5A. Context-based fix (cặp từ ambiguous)
        │  └── 5B. Giữ nguyên từ vựng địa phương đúng
        │
        ▼
[STAGE 6] Sentence Boundary & Punctuation
        │  ├── 6A. Detect ranh giới câu bên trong utterance
        │  └── 6B. Thêm dấu câu
        │
        ▼
[STAGE 7] Tên người
        │  ├── 7A. Trigger pattern detection
        │  ├── 7B. Whitelist matching & capitalize
        │  └── 7C. Session name registry
        │
        ▼
[STAGE 8] Context-based substitution
        │  └── 8A. Từ bị nhầm do mất context (quê/quay...)
        │
        ▼
[STAGE 9] Final QA & Tagging
        │  ├── 9A. Tag các vùng ambiguous còn lại
        │  └── 9B. Flag để human review
        │
        ▼
OUTPUT: Cleaned transcript
```

---

## STAGE 0 — Pre-processing & Detection

### 0A. Normalize encoding & whitespace

Thực hiện trước tất cả mọi thứ. Bất kỳ lỗi encoding nào sẽ phá vỡ toàn bộ pipeline sau.

- Chuẩn hóa encoding về UTF-8, loại bỏ null bytes và control characters
- Thống nhất line endings: `\r\n` → `\n`
- Collapse multiple spaces → single space
- Trim leading/trailing whitespace mỗi dòng
- Chuẩn hóa dấu câu Unicode: dấu ngoặc "curly" → thẳng, dấu gạch ngang — → -

### 0B. Detect giọng miền Nam

Scan toàn bộ transcript, đếm số lần xuất hiện của signal words. Nếu ≥3 signal → bật **regional ruleset**.

**Signal words miền Nam:**
`hổng, hem, hông, dzậy, tui, ổng, bả, ảnh (đại từ), chỉ (đại từ), dìa, dzô, dới, nhen, nghen, hen, mắc (đắt), mần, biểu, coi (xem), kiếm (tìm)`

**Output của bước này:** flag `IS_SOUTHERN = true/false` dùng cho Stage 2C và Stage 5.

### 0C. Detect topic context

Dùng sliding window 10 câu để xác định topic đang được nói đến. Topic ảnh hưởng đến nhiều rule sau (đặc biệt Stage 3B tiền tệ và Stage 8 context substitution).

**Các topic cần detect cho Zalopay:**

| Topic | Signal words |
|---|---|
| Thanh toán / giao dịch | chuyển khoản, thanh toán, nạp, rút, số dư, tài khoản, giao dịch, QR |
| Mua sắm online | mua, đặt hàng, order, ship, giao hàng, hoàn tiền, voucher |
| Trải nghiệm app | app, mở, bấm, màn hình, lỗi, bug, crash, update |
| Gia đình / cá nhân | về quê, nhà, gia đình, bố mẹ, anh chị em |
| Giá cả / tiền | giá, tiền, rẻ, mắc, đắt, bao nhiêu, phí |

**Output:** tag topic cho mỗi đoạn, dùng ở các stage sau.

---

## STAGE 1 — Token Locking

Đánh dấu các vùng token **tuyệt đối không được sửa** ở bất kỳ stage nào sau đó. Đây là bước quan trọng nhất để tránh false positive.

### 1A. Lock số nhạy cảm

Các pattern cần lock ngay:

- **Số điện thoại:** `[0][0-9]{9}` (10 chữ số bắt đầu bằng 0)
- **Mã giao dịch:** chuỗi số/chữ ≥8 ký tự liên tiếp không có khoảng trắng
- **OTP:** 4–6 chữ số đứng sau "mã", "OTP", "xác nhận"
- **Số tài khoản:** 9–14 chữ số liên tiếp
- **Mã số thẻ:** 16 chữ số, thường có dấu gạch hoặc khoảng trắng mỗi 4 số
- **Năm lịch:** 4 chữ số từ 1900–2099 (lock để Stage 3A không nhầm)

**Cách lock:** Bọc trong tag nội bộ `{{LOCKED: token}}` — tag này sẽ được unwrap ở bước cuối cùng sau khi toàn bộ pipeline chạy xong.

### 1B. Lock metadata

- Speaker labels: `[A]:`, `[B]:`, `AGENT:`, `USER:`, `INT:` (interviewer)
- Timestamps: `[00:01:23]`, `(0:01)` và các format tương tự
- Tags đã có sẵn từ diarization: `[INAUDIBLE]`, `[CROSSTALK]`

---

## STAGE 2 — Lỗi ASR nặng

Sửa các lỗi ảnh hưởng lớn nhất trước, vì kết quả của stage này là input cho các stage sau.

### 2A. Brand & App Lexicon Replacement

**Tham chiếu:** File `zalopay_brand_lexicon.md`

Thứ tự ưu tiên khi replace:

1. **Zalopay và các tính năng nội bộ** — ưu tiên cao nhất
2. **Ví điện tử & ngân hàng** (MoMo, VNPay, Vietcombank...)
3. **App & platform phổ biến** (Shopee, TikTok, Grab...)
4. **Brand FnB, siêu thị, rạp phim...**

**Nguyên tắc áp dụng:**
- Match không phân biệt hoa/thường
- Với brand tên ngắn hoặc âm dễ nhầm (Be, Go): **bắt buộc có context confirm** trước khi replace
- Slang brand (Dép Lào, Phở Bò, Tóp Tóp): exact string match, không fuzzy

**Bảo vệ sau replace:** Sau khi replace xong brand, lock các token brand vừa được sửa để Stage 3, 4 không đụng vào.

### 2B. Code-switching Correction

**Chạy theo thứ tự:**

**CS1 — Exact phonetic match (auto-fix):**
Các Việt hóa âm đặc trưng → replace về từ tiếng Anh gốc.

| Nhóm | Ví dụ |
|---|---|
| Marketing | vau chờ → voucher, cát bắt → cashback, căm pen → campaign |
| Social | lai xờ trim → livestream, trân đing → trending |
| Tech | ắp đết → update, cờ rét → crash, linh → link (cần context) |
| Payment | tốp áp → top-up, rì phăn → refund, chéc keo → checkout |
| E-commerce | ô đờ → order, phờ ri síp → freeship |

**CS2 — Phonetic match + context confirm:**
Chỉ replace khi context window ±5 token xác nhận.

| ASR output | Replace thành | Cần context |
|---|---|---|
| seo | sale | giảm, giá, mua, đợt |
| linh | link | gửi, bấm, click, mở, copy |
| ba lần | balance | số dư, kiểm tra, tài khoản |
| cơn ten | content | mạng xã hội, đăng, creator |

**CS3 — Tag gap do drop từ:**
Câu có logic gap sau khi đã áp CS1+CS2 → tag `[CS_TERM]`, không tự điền.

**CS4 — Chuẩn hóa hoa/thường:**
- Từ tiếng Anh thường → viết thường: voucher, livestream, cashback
- Viết tắt → viết hoa: OTP, PIN, QR, COD

### 2C. Giọng miền Nam — Tầng 1 (chỉ chạy nếu `IS_SOUTHERN = true`)

**Auto-fix không cần context — ASR output không phải từ hợp lệ:**

**Phụ âm đầu V → D/Dz:**

| ASR detect | Sửa thành |
|---|---|
| dìa, dzề, dia, dề | về |
| dô, dzô, giô | vào |
| dới, dzới | với |
| dzui, dui | vui |
| dzậy, dậy, giậy | vậy |
| dzừa (context không phải trái cây) | vừa |

**Phụ âm cuối không hợp lệ:**

| ASR detect | Sửa thành |
|---|---|
| thíc, thích (sai dấu) | thích |
| íc | ích |
| mộk | một |
| tốk | tốt |
| giử | giữ |
| nhửng | những |

**Thanh điệu — từ không tồn tại:**
Nếu ASR output không có trong từ điển tiếng Việt nhưng thêm/đổi dấu hỏi↔ngã thì tạo ra từ hợp lệ → auto-fix.
Ví dụ: "giử" (không tồn tại) → "giữ"; "nhửng" (không tồn tại) → "những"

---

## STAGE 3 — Số & Đơn vị

### 3A. Lỗi "năm" vs số 5

**Chạy theo thứ tự ưu tiên:**

**Rule 1 — Năm lịch (an toàn nhất):**
`5 + [1900–2099]` → `năm + [số]`
Ví dụ: "5 2023" → "năm 2023"

**Rule 2 — Cụm cố định (exact match):**

| ASR output | Sửa thành |
|---|---|
| 5 ngoái | năm ngoái |
| 5 nay | năm nay |
| 5 sau / 5 trước | năm sau / năm trước |
| đầu 5 / cuối 5 / giữa 5 | đầu năm / cuối năm / giữa năm |
| 5 học | năm học |

**Rule 3 — Cấp bậc học vấn:**
`[sinh viên / học sinh / năm học / khóa học / học kỳ] + 5 + [1–6]`
→ Replace số 5 đứng giữa bằng "năm"
Ví dụ: "sinh viên 5 4" → "sinh viên năm 4"
**Ngoại lệ:** "lớp 5" → giữ nguyên (lớp năm tiểu học)

**Rule 4 — Đơn vị thời gian:**
`[một/hai/ba/vài/mấy/nhiều/cả/nửa/hơn/gần/khoảng] + 5`
→ Replace "5" bằng "năm", **nếu** không có đơn vị tiền/đo lường theo sau
Ví dụ: "vài 5 trước" → "vài năm trước"
Nhưng: "1 5 triệu" → KHÔNG sửa bằng rule này (chuyển sang Rule T tiền tệ)

**Rule 5 — Merge "15" (flag only, không auto-fix):**
"15" đứng sau: kinh nghiệm, làm việc, công tác, sống → tag `[POSSIBLE: một năm]` để human review

### 3B. Đơn vị tiền tệ

**Xác nhận context tiền tệ trước:** Các từ trong ±5 token phải có: đồng, tiền, giá, phí, thanh toán, chuyển, nạp, rút, số dư, mua, bán, giao dịch.

**Rule T6 — Lỗi chồng lỗi năm/5 + tiền (chạy trước):**
"1 5 triệu" / "1,5 triệu" (tách sai) → "một triệu rưỡi"
"5 triệu", "5 trăm nghìn" trong context tiền → giữ nguyên, không sửa (đây là "năm triệu" đúng)

**Rule T1 — Số dạng X.000.00Y:**
Số có dạng `[N].000.00[1-9]` trong context tiền → decompose:
- 1.000.008 → "một triệu tám"
- 2.000.003 → "hai triệu ba"
- 1.000.005 → "một triệu năm" *(cẩn thận: "năm" ở đây là số 5, không phải đơn vị thời gian)*

**Rule T2 — Chuẩn hóa "rưỡi":**

| ASR output | Sửa thành |
|---|---|
| rưởi, rưới, rưỡy, ruoi | rưỡi |
| 0.5 / ,5 đứng sau đơn vị tiền | rưỡi |

Không convert "rưỡi" thành số — giữ nguyên dạng nói.

**Rule T3 — Chuẩn hóa "k":**
`[số] + [ka/kê/ke/cê/ca]` → `[số]k`
Ví dụ: "30 ka" → "30k", "200 kê" → "200k"

**Rule T4 — Slang tiền tệ miền Nam:**
Chỉ áp dụng khi `IS_SOUTHERN = true` **và** context là tiền tệ:

| ASR detect | Sửa thành | Giá trị |
|---|---|---|
| một cũ, một cú, một cụ | một củ | 1.000.000đ |
| một chay, một trái | một chai | 1.000.000đ |
| một lịt, một lịch | một lít | 100.000đ |
| nữa củ, nửa cũ | nửa củ | 500.000đ |

**Rule T5 — Số thô có dấu chấm phân cách:**
Chỉ convert nếu context tiền tệ rõ ràng. Format output: **giữ dạng nói tự nhiên** (Option A).

| Số | Output |
|---|---|
| 1.000.000 | một triệu đồng |
| 1.800.000 | một triệu tám trăm nghìn đồng |
| 300.000 | ba trăm nghìn đồng |
| 50.000 | năm mươi nghìn đồng |

Nếu không đủ confident → giữ nguyên số thô, không convert.

---

## STAGE 4 — Từ cuối câu & Filler

### 4A. Xóa filler word

**Xóa hoàn toàn khi đứng độc lập đầu câu hoặc giữa câu, không mang nghĩa:**
`Ờ, Ừ, Ừm, Ý, Í, Thì là, Tức là, Kiểu như là, Kiểu là, Thì`

**Xóa khi lặp liên tiếp ≥3 lần:**
"ạ ạ ạ" → "ạ" | "ừ ừ ừ" → (xóa nếu filler, giữ nếu backchanneling)

**Giữ lại:**
- "ạ" cuối câu đơn lẻ — thể hiện lịch sự trong CSKH/phỏng vấn
- Utterance filler của **interviewer** ("ừ", "vâng", "uh huh") → tag `[BACKCHANNEL]`, không xóa

### 4B. Sửa cảm thán từ bị detect sai

| ASR detect | Sửa thành | Điều kiện |
|---|---|---|
| hoa (cuối câu) | ha | Sau động từ hoặc dấu phẩy, không phải danh từ |
| ác, ách, ắc (cuối câu) | á | Cuối câu cảm thán/nhấn mạnh |
| nhà, nia, na (cuối câu) | nha | Sau lời đề nghị/hướng dẫn |
| nghe (cuối câu, không phải động từ) | nhé | Cuối câu mời/đề nghị |
| thối, thui (cuối câu) | thôi | Cuối câu kết thúc ý |
| chữ (cuối câu khẳng định) | chứ | Sau mệnh đề khẳng định |

**Nhóm giữ nguyên có điều kiện:**

| Từ | Giữ khi | Xóa/sửa khi |
|---|---|---|
| ha | Cuối câu hỏi/mời xác nhận | Đầu câu mới sau dấu phẩy (→ xóa) |
| á | Cuối câu nhấn mạnh | Giữa câu như filler (→ xóa) |
| thôi | Cuối câu kết thúc ý | "Thôi thì" đầu câu (→ xóa "thôi thì") |
| đó | Cuối câu chỉ định | "Đó là" đầu mệnh đề (→ giữ nguyên cụm) |

### 4C. Self-correction pattern

Nhận diện và xử lý các pattern người nói tự sửa:

**Pattern 1 — Explicit restart:**
`"tôi... tức là tôi..."` → xóa phần trước "tức là", giữ từ "tức là" trở đi
Tương tự: "không không ý tôi là...", "à mà thôi...", "ý tôi muốn nói là..."
→ Xóa tất cả trước dấu hiệu correction, giữ phần sau

**Pattern 2 — Kéo dài âm / lặp từ:**
3+ lần lặp cùng token liên tiếp → giữ 1, xóa phần còn lại
Ví dụ: "tôi tôi tôi" → "tôi" | "rất rất rất" → "rất"

**Pattern 3 — False start (utterance ngắn bất thường):**
Utterance < 3 từ, không phải câu hoàn chỉnh, ngay trước utterance dài hơn cùng speaker
→ Merge vào utterance tiếp theo nếu cùng speaker
→ Tag `[INCOMPLETE]` nếu bị ngắt bởi người khác

---

## STAGE 5 — Giọng miền Nam Tầng 2 & 3

*Chỉ chạy nếu `IS_SOUTHERN = true`*

### 5A. Context-based fix — Cặp thanh điệu ambiguous

Chỉ sửa khi **cả hai điều kiện** đều thỏa: (1) từ ASR detect là từ ít phổ biến hơn trong context đó, (2) context window ±3 token xác nhận nghĩa.

| Cặp nhầm | Phân biệt |
|---|---|
| bão / bảo | "bão" + lớn/mạnh/đến → thời tiết; "bảo" + ai/rằng → nói |
| nghĩ / nghỉ | "nghĩ" + rằng/là/thấy → suy nghĩ; "nghỉ" + ngơi/làm/việc → nghỉ ngơi |
| bán / bánh | "bán" + hàng/được → động từ; "bánh" + mì/kem/ngọt → thực phẩm |
| cách / các | "cách" + làm/dùng/nào → phương thức; "các" + bạn/anh/cái → số nhiều |
| sạch / sạc | "sạch" + sẽ/bóng → tính từ; "sạc" + pin/điện → kỹ thuật |

Nếu không đủ confident → **giữ nguyên ASR output**, không sửa.

### 5B. Giữ nguyên từ vựng địa phương

Các từ sau khi ASR detect **đúng** → **không chuẩn hóa về từ phổ thông:**

- Đại từ: tui, ổng, bả, chỉ, ảnh, tụi
- Phủ định: hổng, hem, hông
- Tính từ: mắc (đắt), dzữ
- Động từ: kêu (gọi), biểu (bảo), coi (xem), mần (làm), kiếm (tìm)
- Cảm thán cuối câu: nhen, nghen, hen, nè, vậy nè

*Lý do: Transcript phỏng vấn cần bảo toàn giọng nói tự nhiên. Từ địa phương là thông tin demographic có giá trị cho UX research.*

**Chỉ sửa khi ASR detect sai âm của từ địa phương:**

| ASR detect sai | Sửa thành |
|---|---|
| hổn (có), hổn thể | hổng (có), hổng thể |
| hem thấy → hèm thấy | hem thấy |
| nhen → nhân, nghén | nhen |
| chèn ơi → chén ơi, chẻn ơi | chèn ơi |

---

## STAGE 6 — Sentence Boundary & Punctuation

### 6A. Detect ranh giới câu bên trong utterance

**Tín hiệu mạnh → thêm dấu chấm:**
- Kết thúc bằng: "rồi", "xong", "xong rồi", "xong xuôi", "vậy đó", "như vậy", "kiểu vậy"
- Kết thúc bằng "ạ" sau ý hoàn chỉnh

**Tín hiệu mạnh → thêm dấu chấm hỏi:**
- Kết thúc bằng: "không?", "chưa?", "hả?", "ha?", "phải không?", "đúng không?", "vậy đúng không?"

**Tín hiệu trung bình → thêm dấu phẩy:**
- Trước: "thì", "mà", "nhưng mà", "với lại", "nên là", "cho nên", "vì vậy"

**Pattern đặc thù phỏng vấn — chuỗi "rồi... rồi... rồi...":**
"Rồi" đứng **đầu** mệnh đề mới → tách câu, giữ "rồi" ở đầu câu mới
"Rồi" đứng **cuối** câu → thêm dấu chấm

**Nguyên tắc:** Nếu không đủ confident → **không thêm dấu câu**, để trống. Model NLP xử lý được câu không dấu tốt hơn câu dấu sai.

### 6B. Chuẩn hóa dấu câu

- Viết hoa chữ đầu câu sau khi đã xác định ranh giới câu
- Xóa dấu câu lặp: "..." → "." | "??" → "?" | "!!" → "!"
- Chuẩn hóa dấu phẩy trước cảm thán từ cuối câu: "vậy , ha" → "vậy ha" (bỏ khoảng cách thừa)

---

## STAGE 7 — Tên người

### 7A. Trigger pattern detection

Scan toàn transcript, ghi nhận tất cả vị trí có trigger. Độ tin cậy từ cao xuống thấp:

**Trigger cao (High confidence):**
- `tôi là [X]` / `mình là [X]` / `em là [X]` / `tên tôi là [X]`
- `em tên [X]` / `tôi tên [X]`
- `anh [X] ơi` / `chị [X] ơi` / `em [X] ơi`
- `alo [X] ơi` / `dạ [X] ơi`

**Trigger trung bình (Medium confidence — cần whitelist confirm):**
- `anh [X]` / `chị [X]` / `em [X]` (không có "ơi")
- `gặp [X]` / `nhờ [X]` / `hỏi [X]`
- `bạn tôi là [X]` / `đồng nghiệp [X]`

**Trigger thấp (Low — chỉ flag, không auto-capitalize):**
- Token match whitelist, đứng sau dấu phẩy đầu câu
- Token xuất hiện ≥3 lần trong transcript, match whitelist

### 7B. Whitelist matching & capitalize

Với mỗi trigger, extract token X (1–3 từ tiếp theo):

**Sub-list C — Tên đơn phổ biến nhất (check trước):**
Minh, Anh, Hương, Lan, Hà, Linh, Trang, Thảo, Mai, Nga, Hoa, Yến, Châu, Vy, Nhi, Thy, Uyên, Tuấn, Hùng, Đức, Nam, Khoa, Dũng, Phong, Long, Tú, Quân, Hải, Trung, Bình, Khang, Kiên

**Sub-list B — Tên đệm:**
Văn, Thị, Đức, Hữu, Quốc, Minh, Thanh, Thành, Xuân, Thu, Đình, Ngọc, Thùy, Phương, Bảo

**Sub-list A — Họ:**
Nguyễn, Trần, Lê, Phạm, Huỳnh, Hoàng, Phan, Vũ, Võ, Đặng, Bùi, Đỗ, Hồ, Ngô, Dương, Lý

**Kết quả:**
- Match với bất kỳ sub-list → **capitalize** token X
- Không match → tag `[POSSIBLE_NAME: X]` để human review

**Tên đơn dễ nhầm — chỉ capitalize khi có trigger rõ:**

| Tên | Từ thường trùng âm | Rule |
|---|---|---|
| Anh | anh (đại từ) | Chỉ capitalize sau "tên là", "gọi là", hoặc sau đại từ khác |
| Hoa | hoa (danh từ) | Chỉ capitalize sau đại từ xưng hô |
| Nam | nam (hướng/giới tính) | "anh Nam" → OK; "miền Nam", "nam giới" → không |
| Bình | bình (danh từ) | "anh Bình" → OK; "bình thường" → không |

### 7C. Session name registry

Sau khi detect được tên X trong transcript:
- Lưu vào **session registry**: `{token: "Thảo", role: "interviewee"}`
- Tất cả lần xuất hiện tiếp theo của "thảo" trong transcript → auto-capitalize, không cần trigger lại
- Nếu cùng token xuất hiện với vai trò khác nhau → flag ambiguous

---

## STAGE 8 — Context-based Substitution

Chạy sau cùng vì cần transcript đã được làm sạch ở các stage trước để context đủ rõ.

### 8A. Từ bị nhầm do mất context

**Cơ chế:** Với mỗi topic đã detect ở Stage 0C, áp dụng topic-specific lexicon.

| Topic | Từ dễ bị nhầm | Ưu tiên về |
|---|---|---|
| Gia đình / cá nhân | quay → **quê** (khi context "về nhà") | quê |
| Thanh toán | "ba lần" → **balance** (đã xử lý CS2) | — |
| App / kỹ thuật | "chét" → **crash** (đã xử lý CS1) | — |

**Bigram check:** Kiểm tra cặp từ có tự nhiên không.
- "về quay" → bất thường → flag
- "về quê" → tự nhiên → giữ
- "đi quay phim" → tự nhiên → giữ "quay"

**Nguyên tắc:** Chỉ sửa khi bigram kết quả tự nhiên hơn rõ ràng. Nếu cả hai đều tự nhiên → giữ nguyên ASR output.

---

## STAGE 9 — Final QA & Tagging

### 9A. Gán tag chuẩn

Trước khi output, đảm bảo tất cả vùng ambiguous đều được tag đúng:

| Tag | Ý nghĩa | Dùng khi |
|---|---|---|
| `[INAUDIBLE]` | Không nghe được | ASR bỏ trống hoặc confidence rất thấp |
| `[CS_TERM]` | Từ tiếng Anh bị drop | Gap logic do code-switching |
| `[CROSSTALK]` | Nhiều người nói cùng lúc | Phát hiện qua diarization |
| `[INCOMPLETE]` | Câu bị ngắt | False start bị người khác ngắt |
| `[BACKCHANNEL]` | Phản hồi lắng nghe của interviewer | Utterance filler của interviewer |
| `[POSSIBLE_NAME: X]` | Có thể là tên người | Token không match whitelist |
| `[POSSIBLE: X]` | Gợi ý sửa cần review | Rule T5 (merge 15), rule ambiguous |

### 9B. Human review queue

Tổng hợp tất cả các vị trí được flag thành một review list riêng, bao gồm:
- `[POSSIBLE_NAME: X]` — tên người chưa xác nhận
- `[POSSIBLE: X]` — số bị merge (một năm → 15)
- Token ambiguous từ CS2 không đủ context
- Cặp thanh điệu hỏi/ngã không đủ confident

**Unwrap locked tokens:** Bước cuối cùng, unwrap tất cả `{{LOCKED: token}}` về token gốc.

---

## Ma trận quyết định tổng quát

Với **bất kỳ token nào** nghi ngờ cần sửa, trả lời 3 câu hỏi theo thứ tự:

```
1. Token này có nằm trong vùng LOCKED không?
   → Có: bỏ qua, không làm gì
   → Không: tiếp tục

2. Có rule nào match chắc chắn (exact match, không cần context)?
   → Có: auto-fix
   → Không: tiếp tục

3. Có đủ context để quyết định không?
   → Có + confident: fix với context
   → Không chắc: giữ nguyên ASR output + tag để review
```

---

## Các chỉ số theo dõi chất lượng

Sau khi pipeline chạy, đo các chỉ số sau để detect drift và cần re-tune:

| Chỉ số | Định nghĩa | Target |
|---|---|---|
| Auto-fix rate | % token được auto-fix / tổng token | < 5% (quá cao = over-aggressive) |
| Flag rate | % token được flag để review | 1–3% (quá cao = rule quá yếu) |
| Human correction rate | % flag mà human xác nhận cần sửa | > 70% (precision của flag) |
| False positive rate | % auto-fix sai / tổng auto-fix | < 2% |

---

## Thứ tự cập nhật khi có rule mới

Khi phát hiện lỗi mới từ review, thêm rule theo quy trình:

1. **Collect** ≥10 mẫu lỗi cùng loại trước khi viết rule
2. **Classify** lỗi thuộc stage nào
3. **Check conflict** với các rule đang có
4. **Test** trên tập 50 transcript trước khi deploy
5. **Monitor** false positive rate trong 2 tuần đầu
6. **Document** vào file này với ngày thêm

---

## Tài liệu tham chiếu

| File | Nội dung |
|---|---|
| `zalopay_brand_lexicon.md` | Bảng từ điển brand & phonetic variants |
| `zalopay_product_lexicon.md` | Tính năng & dịch vụ Zalopay *(cần bổ sung)* |
| `zalopay_regional_lexicon.md` | Từ vựng địa phương miền Nam *(cần bổ sung)* |

---

*Phiên bản 1.0 — Cần review và cập nhật mỗi quý hoặc khi Zalopay ra tính năng mới.*
