# Project Modules Overview

Tài liệu này là điểm vào nhanh cho người bảo trì hoặc AI đọc code sau này. Mục tiêu là nắm được vai trò của từng module, các route chính, các model quan trọng và những thay đổi đã làm trong đợt sửa này mà không cần đọc toàn bộ source trước.

## 1. `dt_core`

### Vai trò
Module nền cho toàn bộ bộ app Family. Mọi app portal/mobile trong project đều dựa vào module này để lấy shell giao diện chung, app launcher, hồ sơ cá nhân, media dùng lại và asset frontend chung.

### Thứ nên đọc đầu tiên
- `dt_core/controllers/portal.py`
- `dt_core/models/dt_media.py`
- `dt_core/templates/dt_core_templates.xml`
- `dt_core/static/src/js/dt_money_input.js`

### Những gì đã làm trong đợt này
- thêm nút **Đăng xuất** rõ ràng trong `/my/profile`
- thêm **đổi avatar** ngay trong form profile
- bỏ các nút tắt sang memories / tạo memory / tạo khoản chi khỏi trang profile
- thêm component JS nhập tiền VND có gợi ý bấm nhanh các số 0 để module khác dùng lại

Xem chi tiết tại: `dt_core/MODULE_GUIDE.md`

## 2. `dt_expense`

### Vai trò
App thu chi cá nhân/gia đình. Sau lần sửa này module đã chuyển từ app “chi tiêu” đơn thuần thành app **giao dịch tài chính cá nhân** gồm:
- chi tiêu
- thu nhập
- điều chỉnh số dư
- số dư hiện tại tính động từ lịch sử giao dịch
- danh mục thu/chi dùng chung hoặc riêng
- quyền xem riêng tư hoặc public trong phạm vi gia đình / công ty

### Thứ nên đọc đầu tiên
- `dt_expense/models/dt_expense_entry.py`
- `dt_expense/models/dt_expense_category.py`
- `dt_expense/controllers/portal.py`
- `dt_expense/templates/dt_expense_templates.xml`
- `dt_expense/hooks.py`

### Những gì đã làm trong đợt này
- thêm **thu nhập** và **điều chỉnh số dư** vào cùng app
- thêm ô **Cập nhật số tiền hiện tại** trên dashboard; hệ thống tự tạo 1 giao dịch adjustment +/- để đưa số dư về đúng giá trị mong muốn
- danh mục thu nhập và chi tiêu dùng **chung một model category**, phân biệt bằng `category_type`
- thêm chọn **Riêng tư / Public trong gia đình-công ty** khi tạo giao dịch
- chuẩn hóa record mới theo **VND**, không dùng số lẻ
- thêm input tiền có format Việt và gợi ý bấm nhanh `1.000 / 10.000 / 100.000 / 1.000.000`
- thêm tài liệu module và migration hook để tương thích dữ liệu cũ

Xem chi tiết tại: `dt_expense/MODULE_GUIDE.md`

## 3. `dt_memoire`

### Vai trò
App timeline memories/kỷ niệm gia đình. Module này quản lý memory, album, tag, media và privacy của nội dung kỷ niệm.

### Thứ nên đọc đầu tiên
- `dt_memoire/models/dt_memoire_diary.py`
- `dt_memoire/controllers/portal.py`
- `dt_memoire/templates/dt_memoire_templates.xml`

### Những gì đã làm trong đợt này
- không đổi nghiệp vụ chính
- bổ sung tài liệu module để người đọc và AI hiểu nhanh cấu trúc hiện tại và mối liên hệ với `dt_core`

Xem chi tiết tại: `dt_memoire/MODULE_GUIDE.md`

## Ghi chú triển khai sau khi nhận code
- Copy các module vào addons path rồi upgrade tối thiểu:
  - `dt_core`
  - `dt_expense`
- Nếu muốn dữ liệu danh mục mẫu mới xuất hiện đầy đủ trong database cũ, cần upgrade `dt_expense`.
- `dt_expense` có `post_init_hook` để normalize các field mới từ dữ liệu cũ và tránh gán nhầm category private cũ cho superuser.
- Bug upload ảnh/video mà bạn đã nêu **chưa xử lý trong đợt này** theo đúng scope đã chốt trước khi sửa.


## Ghi chú frontend mới

- Các hành vi JS trên portal liên quan đến nhập tiền và form chi tiêu đã được chuyển sang `publicWidget` của Odoo để tránh lỗi không bind khi assets hoặc lifecycle frontend thay đổi.
