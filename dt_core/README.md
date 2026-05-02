# dt_core

`dt_core` là module nền của toàn bộ bộ addon. Module này không phải một app nghiệp vụ riêng lẻ mà là phần hạ tầng portal chung cho các app khác.

## Mục đích
- Tạo trải nghiệm portal/mobile nhất quán.
- Cung cấp layout, navigation, profile và avatar.
- Cung cấp model media để module khác đính kèm ảnh/video.
- Cung cấp cấu hình gia đình để quyết định ai được xem dữ liệu của mình.

## Những gì module này chứa
### 1. Shell portal
Template `portal_shell` tạo khung giao diện chung:
- header trên cùng
- nút quay lại
- tên trang + mô tả ngắn
- avatar góc phải
- bottom navigation cố định

### 2. Trang profile
Trang `/my/profile` cho phép:
- đổi avatar
- cập nhật tên, số điện thoại, bio
- cấu hình thành viên gia đình được xem dữ liệu của mình
- đăng xuất

### 3. Quyền xem dữ liệu gia đình
Model `dt.family.access` lưu cấu hình:
- chủ dữ liệu là ai
- ai được xem
- có được xem thu chi không
- có được xem memories không

Quyền này được dùng xuyên module. Ví dụ `dt_expense` gọi helper trên `res.users` để biết user hiện tại được phép xem giao dịch của ai.

### 4. Media dùng chung
Model `dt.media` được thiết kế làm lớp media trung gian. Các module khác chỉ cần trỏ `res_model` và `res_id` để dùng chung luồng upload/lưu/xóa media.

## Route chính
- `/my/apps` → redirect về `/my/apps/expenses`
- `/my/profile`
- `/my/profile/save`
- `/my/profile/logout`

## Khi nào cần sửa module này
- Muốn đổi navigation hoặc shell chung.
- Muốn thêm trường hồ sơ người dùng.
- Muốn đổi cơ chế quyền xem dữ liệu gia đình.
- Muốn sửa luồng upload avatar hoặc media dùng chung.
