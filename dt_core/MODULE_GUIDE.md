# Hướng dẫn module `dt_core`

## Vai trò trong hệ thống
`dt_core` là tầng nền, chịu trách nhiệm cho trải nghiệm chung và quyền dùng chung. Những thay đổi ở đây thường ảnh hưởng tới tất cả app portal.

## Model chính
### `dt.family.access`
Lưu một dòng quyền dạng:
- `owner_user_id`: người sở hữu dữ liệu
- `viewer_user_id`: người được xem
- `allow_expense`: có xem được thu chi không
- `allow_memory`: có xem được memories không

### `res.users` extension
Thêm các helper như:
- `get_visible_expense_user_ids()`
- `get_visible_memory_user_ids()`
- `can_view_expense_from(owner_user)`
- `can_view_memory_from(owner_user)`

### `res.partner` extension
Lưu các thông tin portal bổ sung như:
- mã thành viên
- bio ngắn

## Controller chính
### `FamilyPortalCore`
- dựng `base_values`
- redirect `my/apps`
- render profile
- lưu hồ sơ và cấu hình gia đình
- logout

## Template chính
### `portal_shell`
Khung chung cho giao diện portal.

### `portal_profile`
Trang hồ sơ, trong đó phần cấu hình gia đình là nơi chủ dữ liệu bật/tắt quyền xem của từng thành viên.

## Điểm cần lưu ý khi mở rộng
- Mọi app muốn có cơ chế family view nên tái dùng helper ở `res.users`, tránh tự viết domain riêng.
- Nếu muốn thêm loại quyền mới sau này, có thể thêm cột mới vào `dt.family.access` thay vì tạo thêm model khác.
- Nếu đổi navigation, nên kiểm tra tất cả `page_name` của các module để không lệch trạng thái active.
