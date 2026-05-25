# PROJECT_MODULES_OVERVIEW.md

Tài liệu này mô tả trạng thái hiện tại của bộ addon `addon_dinhtranit` sau lần cập nhật giao diện mobile theo bộ design A/B và bổ sung nghiệp vụ nguồn tiền, sổ nợ, báo cáo riêng, quyền gia đình và media private.

## Nguyên tắc chung

- Dự án đang target **Odoo 19 Enterprise**.
- Ba module chính: `dt_core`, `dt_expense`, `dt_memoire`.
- Portal mobile dùng chung một shell ấm màu kem, typography serif cho tiêu đề/số tiền, bottom navigation 3 tab: **Tài chính**, **Kỷ niệm**, **Tôi**.
- Dữ liệu cũ không bị xóa. Khi cần bỏ chức năng cũ ở giao diện, dữ liệu vẫn được giữ bằng `active=False` hoặc giữ model/field cũ.
- Các route cũ quan trọng vẫn được giữ để tránh gãy link: `/my/apps/expenses`, `/my/apps/expenses/new`, `/my/apps/expenses/history`, `/my/apps/expenses/categories`, `/my/apps/memories`, `/my/profile`.
- Module `dt_expense` có migration/post-init để chuẩn hóa dữ liệu cũ: tháng hạch toán về ngày đầu tháng, backfill chủ danh mục, tạo nguồn tiền mặc định và gán `wallet_id` cho giao dịch cũ.

---

## 1. `dt_core` — nền tảng portal, quyền gia đình, media

### Mục đích

`dt_core` là module nền cho toàn bộ app gia đình. Module này cung cấp shell portal/mobile, profile, quản lý quyền xem dữ liệu giữa các user thật trong Odoo, và lớp media dùng chung cho ảnh/video.

### Thành phần chính

- `models/dt_app.py`: khai báo các app con hiển thị trong hệ thống.
- `models/dt_family_access.py`: model `dt.family.access`, lưu quan hệ **owner user** cho phép **viewer user** xem dữ liệu.
  - `allow_expense`: quyền xem tài chính/thu chi.
  - `allow_memory`: quyền xem kỷ niệm.
  - Hai quyền được kiểm tra riêng, đúng với yêu cầu “giữ 2 nhóm riêng”.
- `models/res_users.py`: helper quyền gia đình:
  - `get_family_candidate_users()` lấy user nội bộ thật trong Odoo để cấu hình gia đình.
  - `get_visible_expense_user_ids()` lấy danh sách owner mà user hiện tại được xem tài chính.
  - `get_visible_memory_user_ids()` lấy danh sách owner mà user hiện tại được xem kỷ niệm.
  - `can_view_expense_from(owner_user)` và `can_view_memory_from(owner_user)` là điểm kiểm tra quyền chính.
- `models/dt_media.py`: media dùng chung cho expense và memories.
  - File upload được lưu trong `ir.attachment` private, không public.
  - `dt.media` giữ metadata: owner, record liên kết, type image/video/file, cover, filename, mimetype, size.
  - `image_url()`, `stream_url()`, `download_url()` trả về route private `/my/family/media/<id>/content`.
- `controllers/media.py`: stream ảnh/video/file qua route riêng có kiểm tra quyền.
  - Kiểm tra `media.can_read(request.env.user)` trước khi trả bytes.
  - Hỗ trợ HTTP Range (`206 Partial Content`) để video có thể play/seek sau khi lưu.
  - Trả `Content-Type`, `Content-Disposition`, `Accept-Ranges`, `Content-Length`.
- `controllers/portal.py`: route profile.
  - `/my/profile`: màn “Tôi”, quản lý avatar/tên/phone/bio và các user gia đình.
  - `/my/profile/save`: lưu profile và quyền xem tài chính/kỷ niệm cho từng user thật.
  - `/my/profile/logout`: đăng xuất.
- `templates/dt_core_templates.xml`: shell portal và trang profile theo design.
- `static/src/css/dt_core_portal.scss`: theme nền, topbar, bottom nav, card, form, media.
- `static/src/js/dt_money_input.js`: format input tiền theo VND hiển thị `đ`.

### Lưu ý quyền media

`dt.media.can_read(user)` cho phép đọc nếu:

1. user là owner của media;
2. user thuộc nhóm system admin;
3. record liên kết có hàm `can_view(user)` và trả về `True`.

Vì vậy ảnh/video của giao dịch và kỷ niệm chỉ đọc được khi user có quyền xem record gốc.

---

## 2. `dt_expense` — tài chính gia đình

### Mục đích

`dt_expense` quản lý tài chính gia đình trên portal mobile: nhập giao dịch, danh mục, nguồn tiền, sổ nợ, lịch sử và báo cáo chi tiêu riêng. Giao diện kết hợp design B cho dashboard/form/danh mục và design A cho lịch sử/báo cáo tinh gọn.

### Model chính

#### `dt.expense.entry`

Model giao dịch tài chính.

Loại giao dịch (`entry_type`):

- `expense`: chi tiêu thật, bắt buộc chọn danh mục lá loại chi tiêu.
- `income`: thu nhập thật, bắt buộc chọn danh mục lá loại thu nhập.
- `adjustment`: điều chỉnh số dư, không dùng danh mục.
- `debt`: giao dịch tiền phát sinh từ sổ nợ, không nhập trực tiếp từ form giao dịch thường.

Field quan trọng:

- `expense_date`: ngày phát sinh.
- `accounting_month`: tháng hạch toán, luôn normalize về ngày đầu tháng.
- `category_id`: danh mục lá cho thu/chi.
- `wallet_id`: nguồn tiền bị ảnh hưởng.
- `debt_id`, `debt_flow`: liên kết và luồng tiền của nghiệp vụ nợ.
- `user_id`: người nhập/chủ giao dịch. Portal form không cho nhập field này; luôn là user hiện tại.
- `media_count`, `cover_media_id`: ảnh/video hóa đơn qua `dt.media`.

Luồng tính số dư (`get_balance_effect()`):

- `income`: cộng tiền.
- `expense`: trừ tiền.
- `adjustment`: cộng/trừ theo `adjustment_direction`.
- `debt`:
  - `borrow_in`: mình mượn người khác → tiền vào ví.
  - `lend_out`: cho người khác mượn → tiền ra khỏi ví.
  - `collect_lend`: thu hồi khoản cho mượn → tiền vào ví.
  - `repay_borrow`: trả khoản mình mượn → tiền ra khỏi ví.

Dashboard/lịch sử tách rõ:

- **Thu** chỉ tính `entry_type='income'`.
- **Chi** chỉ tính `entry_type='expense'`.
- **Ròng/số dư** tính toàn bộ cash effect, bao gồm điều chỉnh và nợ.

#### `dt.expense.category`

Danh mục cha/con cho thu/chi.

- `category_type`: `expense` hoặc `income`.
- `parent_id`, `child_ids`, `is_leaf`.
- Giao dịch thường chỉ được chọn danh mục lá.
- `apply_next_month_rule`: nếu bật, giao dịch cuối tháng tự hạch toán sang tháng sau.
- `user_id`: người tạo; category mặc định thuộc admin (`base.user_admin`) để user dùng chung.

#### `dt.expense.wallet`

Nguồn tiền thật của từng user: ví tiền mặt, Momo, ngân hàng...

Field chính:

- `name`, `icon`, `sequence`.
- `user_id`: chủ nguồn tiền.
- `opening_balance`, `opening_date`.
- `balance`: số dư tính bằng `opening_balance + sum(balance_effect của entry active thuộc wallet)`.
- `entry_count`, `balance_label`.

Helper:

- `get_default_wallet(user)`: lấy hoặc tạo nguồn tiền mặc định “Tiền mặt”.
- `ensure_default_wallets_for_users()`: tạo nguồn tiền mặc định cho user nội bộ.

#### `dt.expense.debt`

Sổ nợ thay cho phần ngân sách cũ.

Hai loại nợ:

- `lend`: **cho người ta mượn**, người khác đang nợ mình.
- `borrow`: **mình mượn người ta**, mình đang nợ người khác.

Field chính:

- `debt_type`, `counterparty`, `amount`, `paid_amount`, `remaining_amount`.
- `wallet_id`: nguồn tiền phát sinh.
- `debt_date`, `due_date`.
- `state`: `open`, `paid`, `cancelled`.
- `initial_entry_id`, `entry_ids`: các giao dịch cash-flow của khoản nợ.

Hành vi tự động:

- Khi tạo khoản nợ:
  - `lend` sinh entry `debt/lend_out` để trừ tiền khỏi ví.
  - `borrow` sinh entry `debt/borrow_in` để cộng tiền vào ví.
- Khi ghi nhận thanh toán:
  - `lend` sinh entry `debt/collect_lend`.
  - `borrow` sinh entry `debt/repay_borrow`.
- Khi hủy nợ: không xóa dữ liệu, đặt debt và entry liên quan về inactive.

### Controller portal chính

File: `dt_expense/controllers/portal.py`.

Route chính:

- `/my/apps/expenses`, `/my/expenses`: dashboard tài chính.
- `/my/apps/expenses/new`: nhập giao dịch thu/chi/điều chỉnh.
- `/my/apps/expenses/<id>/edit`: sửa giao dịch thường của chính mình.
- `/my/apps/expenses/save`: lưu giao dịch; user nhập luôn là `request.env.user`.
- `/my/apps/expenses/balance/save`: cập nhật số dư thực tế bằng entry điều chỉnh cho nguồn tiền.
- `/my/apps/expenses/categories`: danh mục cha/con.
- `/my/apps/expenses/wallets`: nguồn tiền.
- `/my/apps/expenses/debts`: sổ nợ.
- `/my/apps/expenses/history`: lịch sử giao dịch, filter theo scope/cá nhân/gia đình, loại, ví, danh mục.
- `/my/apps/expenses/history/entries`: endpoint load thêm lịch sử.
- `/my/apps/expenses/reports`: báo cáo chi tiêu tách riêng.
- `/my/apps/expenses/title_suggestions`: autocomplete tiêu đề theo danh mục.

### Template portal chính

File: `dt_expense/templates/dt_expense_templates.xml`.

- `portal_expense_home`: dashboard kiểu design B.
  - Số dư hiện tại.
  - Shortcut: nhập GD, biến động/báo cáo, sổ nợ, nguồn tiền.
  - Thu/chi tháng.
  - Tổng theo thành viên gia đình được phép xem.
  - Preview báo cáo chi tiêu thay cho “gần đây”.
  - Tile nợ: cho mượn / mình mượn.
- `portal_expense_form`: form ghi chép GD.
  - Segment chi tiêu/thu nhập/điều chỉnh.
  - Quick categories.
  - Số tiền, mô tả, ngày, người chi readonly, nguồn tiền, ghi chú, ảnh/video hóa đơn.
- `portal_expense_categories`: danh mục cha/con kiểu card.
- `portal_expense_wallets`, `portal_expense_wallet_form`: nguồn tiền.
- `portal_expense_debts`, `portal_expense_debt_form`: sổ nợ và ghi nhận thanh toán.
- `portal_expense_history`: lịch sử giao dịch với media thumbnail nếu có.
- `portal_expense_report`: báo cáo chi tiêu riêng, donut chart bằng CSS conic-gradient và breakdown theo danh mục.

### JS/CSS

- `static/src/js/dt_expense_form.js`:
  - đổi tab thu/chi/điều chỉnh;
  - ẩn/hiện category theo loại giao dịch;
  - cập nhật tháng hạch toán theo rule danh mục;
  - autocomplete tiêu đề;
  - toggle form cập nhật số dư;
  - điều hướng tháng và infinite scroll lịch sử.
- `static/src/css/dt_expense_portal.scss`: style dashboard, form, card danh mục, báo cáo, nguồn tiền, sổ nợ, lịch sử.

### Migration và giữ dữ liệu cũ

- `hooks.py`:
  - `_set_vnd_symbol`: đổi symbol VND sang `đ`.
  - `_normalize_accounting_month`: đảm bảo tháng hạch toán là ngày đầu tháng.
  - `_backfill_category_owner`: category cũ thiếu owner sẽ về admin.
  - `_backfill_wallets`: tạo nguồn tiền mặc định và gán `wallet_id` cho giao dịch cũ.
- `migrations/19.0.2.0.0/post-migrate.py`: gọi lại logic migrate khi update module.

Không có script nào xóa giao dịch cũ. Giao dịch cũ được gắn vào ví mặc định để số dư vẫn tính đúng.

---

## 3. `dt_memoire` — kỷ niệm gia đình

### Mục đích

`dt_memoire` quản lý nhật ký/kỷ niệm gia đình: timeline, detail, tạo/sửa memory, album/tag/cảm xúc và media ảnh/video.

### Model chính

#### `dt.memoire.diary`

Field chính:

- `title`, `story`, `memory_date`, `location`.
- `emotion`, `category`.
- `privacy`: giữ field cũ (`private`, `family`, `shared`, `public`) để không mất dữ liệu.
- `album_id`, `tag_ids`.
- `user_id`: chủ kỷ niệm.
- `media_count`, `image_count`, `video_count`, `cover_media_id`.

Quyền xem:

- Owner hoặc system admin luôn xem được.
- `privacy='private'`: chỉ owner/admin xem.
- Các privacy còn lại dùng cấu hình gia đình trong `dt.family.access` với `allow_memory=True`.
- Form portal hiện có checkbox **Chỉ mình mình thấy**; nếu bật lưu `privacy='private'`, nếu không lưu `privacy='family'`.

### Controller portal

File: `dt_memoire/controllers/portal.py`.

Route chính:

- `/my/apps/memories`, `/my/memories`: feed kỷ niệm.
- `/my/apps/memories/mine`: redirect filter của tôi.
- `/my/apps/memories/<id>`: detail.
- `/my/apps/memories/new`: tạo memory.
- `/my/apps/memories/<id>/edit`: sửa memory của chính mình.
- `/my/apps/memories/save`: lưu memory và upload media.
- `/my/apps/memories/<id>/delete`: xóa memory của chính mình.
- `/my/apps/memories/media/<media_id>/delete`: xóa media của chính mình.

### Template/CSS

- `templates/dt_memoire_templates.xml`:
  - Feed “Mái ấm của mình” theo design A.
  - Card memory có cover image/video từ route media private.
  - Detail hiển thị cover, story, badges, gallery media.
  - Form tạo/sửa có upload ảnh/video, title, emotion, ngày, location, category, album, chia sẻ theo cấu hình gia đình và checkbox chỉ mình mình thấy.
- `static/src/css/dt_memoire_portal.scss`: grid feed, card, detail, form, upload preview.

---

## 4. Luồng media ảnh/video

Media dùng chung cho `dt_expense` và `dt_memoire`.

1. Portal form nhận file từ input `media_files`.
2. Controller gọi `request.env['dt.media'].sudo().create_from_uploads(...)`.
3. File được lưu vào `ir.attachment` private (`public=False`).
4. `dt.media` được tạo và liên kết với record gốc bằng `res_model/res_id`.
5. UI hiển thị bằng route `/my/family/media/<media_id>/content`.
6. Route stream kiểm tra quyền `can_read` trước khi trả ảnh/video.
7. Video dùng `Range` header nên browser có thể đọc metadata/play/seek.

Khi cần debug lỗi media, kiểm tra theo thứ tự:

- Record `dt.media` có đúng `res_model`, `res_id`, `attachment_id` không.
- `attachment.datas` có dữ liệu không.
- User đang xem có quyền `can_view` record gốc không.
- Response của `/my/family/media/<id>/content` có `Content-Type` đúng MIME không.

---

## 5. Gợi ý đọc code lần sau

1. Đọc `dt_core/models/res_users.py` và `dt_core/models/dt_family_access.py` trước để hiểu quyền gia đình.
2. Đọc `dt_core/models/dt_media.py` và `dt_core/controllers/media.py` để hiểu cách ảnh/video được lưu và stream.
3. Đọc `dt_expense/models/dt_expense_entry.py`, `dt_expense_wallet.py`, `dt_expense_debt.py` để hiểu toàn bộ logic tiền.
4. Đọc `dt_expense/controllers/portal.py` để hiểu cách dashboard/history/report lấy dữ liệu gia đình và scope.
5. Đọc `dt_memoire/models/dt_memoire_diary.py` để hiểu rule privacy/kỷ niệm.
6. Đọc `PROJECT_MODULES_OVERVIEW.md` này trước khi sửa tiếp để tránh phá migration hoặc đổi ý nghĩa dữ liệu cũ.


## Cập nhật giao diện và luồng giao dịch - patch mới

- Form tạo giao dịch hiển thị khối **Danh mục** thay vì “Hay dùng”. Các danh mục được sắp theo số lần sử dụng giảm dần, nhưng vẫn là danh mục thật.
- Nút **Khác** trong form giao dịch mở danh sách tất cả danh mục để chọn. Cuối danh sách mới có nút **Tạo mới** để thêm danh mục.
- Trường **Người chi** bị ẩn ở form tạo/sửa vì luôn là user đang đăng nhập. Trường này chỉ hiển thị ở màn xem chi tiết giao dịch và màn xem gia đình.
- Giao dịch của chính user có thể sửa/xóa từ lịch sử hoặc màn chi tiết. Khi xem bằng scope `family`, màn chi tiết là read-only.
- Bottom navigation chỉ hiển thị ở ba màn chính: `/my/apps/expenses`, `/my/apps/memories`, `/my/profile`; các màn con dùng back button. Thanh nav nằm sát đáy, không padding/margin ngoài và không bo góc.
- Upload ảnh/video dùng nhãn **Tải file** thay cho nút mặc định của browser. Media đã lưu được hiển thị lớn/rõ hơn trong form sửa và màn chi tiết.
