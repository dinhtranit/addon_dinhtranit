# dt_expense - Module Guide

## Mục tiêu hiện tại
Module này là app sổ thu chi cá nhân/gia đình trên portal mobile-first. Người dùng có thể:
- tạo giao dịch thu, chi, điều chỉnh
- xem số dư hiện tại theo VND
- quản lý danh mục thu/chi
- cấu hình gợi ý tiêu đề nhập nhanh theo danh mục
- để hệ thống học thêm từ lịch sử tiêu đề đã dùng
- xem báo cáo và lịch sử giao dịch

## Các model chính
### `dt.expense.entry`
Giao dịch tài chính.
- `entry_type`: `expense`, `income`, `adjustment`
- `privacy`: `private`, `public`
- `amount`: số tiền VND, không dùng phần lẻ
- `category_id`: bắt buộc cho thu/chi, bỏ trống cho adjustment
- tự tính `signed_amount`, `amount_label`, `amount_css_class`
- khi create/write sẽ tự cập nhật dữ liệu học gợi ý tiêu đề

### `dt.expense.category`
Danh mục giao dịch dùng chung cho chi tiêu và thu nhập.
- `category_type`: `expense` hoặc `income`
- `scope`: `shared` hoặc `private`
- `user_id`: chủ sở hữu nếu là private
- `create_uid`: vẫn được dùng để xác định người tạo thực tế, kể cả category shared
- quyền sửa/xóa portal hiện tại: creator hoặc admin hệ thống

### `dt.expense.title.suggestion`
Nguồn dữ liệu cho autocomplete tiêu đề.
- gợi ý cấu hình tay (`is_manual=True`)
- gợi ý học từ lịch sử (`is_manual=False`)
- có `usage_count`, `last_used_at`, `sequence`
- unique theo `(category_id, normalized_name)` để tránh trùng logic

## Luồng portal chính
### Trang chủ `/my/apps/expenses`
- card số dư bấm mới hiện form cập nhật
- lưu xong tạo adjustment để đưa số dư về giá trị thực tế
- không còn hiển thị form cập nhật số dư ngay từ đầu

### Form giao dịch `/my/apps/expenses/new`
- thứ tự nhập được tối ưu lại
- chọn danh mục -> gọi endpoint gợi ý tiêu đề
- gõ vào tiêu đề -> filter gợi ý theo query
- gợi ý lấy từ cấu hình thủ công + lịch sử đã dùng

### Trang danh mục `/my/apps/expenses/categories`
- mặc định hiện danh sách
- có nút tạo mới riêng để bung form
- sửa inline theo từng dòng danh mục
- có panel riêng quản lý gợi ý tiêu đề
- nếu xóa danh mục đã có giao dịch, hệ thống chuyển sang `active=False` để tránh lỗi ràng buộc

## Endpoint portal quan trọng
- `/my/apps/expenses/title-suggestions`
  - trả JSON list gợi ý theo `category_id` và `q`
- `/my/apps/expenses/categories/<id>/suggestions/save`
- `/my/apps/expenses/categories/<id>/suggestions/<suggestion_id>/delete`

## Frontend JS
### `dt_expense/static/src/js/dt_expense_form.js`
Đã chuyển sang chuẩn `publicWidget` của Odoo.
Bao gồm 2 nhóm hành vi:
- toggle panel số dư / panel tạo-sửa danh mục
- autocomplete tiêu đề giao dịch theo danh mục

## Mở rộng sau này
Nền tảng hiện tại đã sẵn sàng để nâng cấp thêm:
- fuzzy search gần đúng cho autocomplete
- ưu tiên mạnh hơn theo tần suất và thời gian dùng gần đây
- nhóm suggestion theo manual/history/recent
- học tiêu đề theo user và theo company sâu hơn
