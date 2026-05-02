# Tổng quan module

## 1. `dt_core`
Module nền cho toàn bộ hệ thống portal.

### Chức năng chính
- Tạo shell giao diện portal/mobile dùng chung.
- Quản lý thanh header, avatar, bottom navigation và back button.
- Quản lý hồ sơ cá nhân: tên, điện thoại, bio, avatar.
- Quản lý media chung (`dt.media`) để các module khác đính kèm ảnh/video.
- Quản lý quyền xem dữ liệu gia đình qua model `dt.family.access`.
- Redirect `my/apps` về ứng dụng tài chính để loại bỏ màn trung gian rối.

### Thành phần chính
- `controllers/portal.py`: route profile, lưu hồ sơ, cấu hình gia đình, logout.
- `models/dt_media.py`: model media dùng chung.
- `models/dt_family_access.py`: quan hệ ai được xem dữ liệu của ai.
- `models/res_users.py`: helper để truy vấn danh sách owner/viewer theo từng loại dữ liệu.
- `templates/dt_core_templates.xml`: shell portal và trang profile.

## 2. `dt_expense`
Ứng dụng tài chính cho cá nhân/gia đình.

### Chức năng chính
- Quản lý giao dịch `chi tiêu`, `thu nhập`, `điều chỉnh`.
- Tính số dư hiện tại từ lịch sử giao dịch.
- Cho phép cập nhật số dư thực tế bằng cách sinh giao dịch điều chỉnh.
- Quản lý `tháng hạch toán` tách khỏi ngày giao dịch.
- Rule tự động cho danh mục có cờ “cuối tháng tính sang tháng sau”.
- Danh mục cha/con, chỉ chọn danh mục lá trong giao dịch.
- Trang `Lịch sử giao dịch` gồm tab `Hoạt động` và `Thống kê`.
- Search, filter, family scope, member scope.
- Gợi ý tiêu đề cấu hình tay + học từ lịch sử.

### Thành phần chính
- `models/dt_expense_entry.py`: model giao dịch.
- `models/dt_expense_category.py`: model danh mục cha/con.
- `models/dt_expense_title_suggestion.py`: gợi ý tiêu đề cấu hình tay.
- `models/dt_expense_title_history.py`: lịch sử tiêu đề đã dùng.
- `controllers/portal.py`: home, form giao dịch, danh mục, suggestions, lịch sử, autocomplete.
- `static/src/js/dt_expense_form.js`: tab loại giao dịch, filter panel, autocomplete tiêu đề, toggle số dư.
- `templates/dt_expense_templates.xml`: toàn bộ giao diện portal cho tài chính.

## 3. `dt_memoire`
Ứng dụng ghi memory/dòng thời gian.

### Chức năng chính
- Quản lý memory, album, tag, cảm xúc, nội dung, media.
- Hiển thị timeline memories.
- Quyền xem memories được ràng qua cấu hình gia đình ở `dt_core`, ngoài privacy có sẵn của từng memory.

### Thành phần chính
- `models/dt_memoire_diary.py`: memory chính.
- `controllers/portal.py`: timeline, detail, create/edit/delete memory.
- `templates/dt_memoire_templates.xml`: giao diện timeline và form memory.

## Gợi ý đọc mã nguồn
1. Đọc `dt_core` trước để hiểu shell portal, hồ sơ và quyền xem dữ liệu.
2. Đọc `dt_expense` để hiểu luồng tài chính, vì đây là module có nhiều logic nghiệp vụ nhất.
3. Đọc `dt_memoire` để hiểu cách dùng chung media và quyền xem theo cấu hình gia đình.
