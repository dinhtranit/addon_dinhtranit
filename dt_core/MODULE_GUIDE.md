# dt_core module guide

## 1. Mục đích
`dt_core` là module nền của toàn bộ project Family. Module này cung cấp các thành phần dùng chung cho các app portal/mobile như app launcher, portal shell, profile người dùng, lớp media dùng lại, style chung và JS nhập tiền dùng lại.

Nếu chỉ đọc nhanh một module để hiểu project đang tổ chức portal theo hướng nào, nên đọc `dt_core` trước.

## 2. Vai trò trong kiến trúc tổng thể
`dt_core` chịu trách nhiệm cho 4 nhóm chính:
1. **App registry**: định nghĩa app nào được hiện ở `/my/apps`.
2. **Portal shell**: layout topbar, bottom nav, vùng nội dung chung.
3. **Profile cá nhân**: trang hồ sơ, cập nhật avatar, tên, điện thoại, bio và logout.
4. **Media + asset dùng chung**: model `dt.media`, SCSS portal, JS format input tiền.

Các module như `dt_expense` và `dt_memoire` không dựng UI portal từ đầu mà dựa vào shell và asset của module này.

## 3. Thành phần chính

### 3.1 Model
#### `dt.app`
Registry các app portal hiển thị ở `/my/apps`.

Field quan trọng:
- `name`: tên app
- `code`: mã app
- `route`: URL mở app
- `icon`: emoji/icon hiển thị
- `description`: mô tả ngắn
- `sequence`: thứ tự hiển thị
- `is_active`: bật/tắt app trên launcher

#### `dt.media`
Lớp media dùng chung cho nhiều app.

Mục đích:
- chuẩn hóa việc lưu file ảnh/video qua `ir.attachment`
- làm lớp trung gian để expense và memoire dùng chung cơ chế đính kèm file
- giữ chỗ cho định hướng đồng bộ ra kho media ngoài trong tương lai

Các nhóm field chính:
- thông tin file: tên file, mimetype, kích thước, loại media
- liên kết record đích: `res_model`, `res_id`
- ownership: `owner_user_id`
- thứ tự/cover: `sequence`, `is_cover`
- thông tin attachment và metadata kỹ thuật

#### `res.partner` extension
Bổ sung các field phục vụ app Family:
- `dt_member_code`: mã thành viên
- `dt_bio`: giới thiệu ngắn

#### `res.config.settings` extension
Chuẩn bị sẵn chỗ để cấu hình chiến lược lưu media sau này.

### 3.2 Controller
#### `dt_core.controllers.login_redirect`
Chịu trách nhiệm đổi hướng vào app sau khi login.

Hành vi chính:
- user đã đăng nhập vào `/` sẽ được chuyển về `/my/apps`
- public user sẽ được đưa về `/web/login`

#### `dt_core.controllers.portal`
Route portal dùng chung:
- `/my/apps`: app launcher
- `/my/profile`: trang profile
- `/my/profile/save`: lưu tên, điện thoại, bio, avatar
- `/my/profile/logout`: logout rõ ràng rồi chuyển về `/web/login`

### 3.3 Template / UI
File chính: `dt_core/templates/dt_core_templates.xml`

Template quan trọng:
- `portal_shell`: layout gốc của các màn portal
- `portal_apps_home`: màn hình chọn app
- `portal_profile`: hồ sơ cá nhân

### 3.4 Asset frontend
#### `dt_core/static/src/css/dt_core_portal.scss`
Style chung cho toàn bộ portal mobile-first.

#### `dt_core/static/src/js/dt_money_input.js`
Component JS reusable cho input tiền.

Cách dùng:
- gắn `data-money-input="1"` lên input
- có thể cấu hình gợi ý nhanh bằng `data-money-suggestions="1000,10000,100000,1000000"`

Hành vi:
- tự bỏ ký tự không phải số
- tự format kiểu Việt bằng dấu chấm ngăn cách hàng nghìn
- tự sinh nút gợi ý bấm nhanh các mức tiền lớn
- cho phép giữ dấu âm nếu sau này cần dùng cho trường hợp đặc biệt

## 4. Những gì đã làm ở lần sửa này
1. Thêm nút **Đăng xuất** rõ ràng trong `my/profile` vì phần header/nav gốc đã bị ẩn.
2. Bỏ các link tắt ở profile như `Xem memories`, `Tạo memory mới`, `Tạo khoản chi mới` để profile chỉ còn đúng vai trò thông tin cá nhân.
3. Thêm **đổi avatar** trực tiếp trong form profile bằng upload ảnh.
4. Tạo route logout riêng `/my/profile/logout` để không phụ thuộc menu hệ thống.
5. Bổ sung asset `dt_money_input.js` để `dt_expense` và các module sau này có thể dùng lại input tiền có gợi ý số 0.

## 5. Cách module này được module khác dùng lại
- `dt_expense` dùng `portal_shell` cho toàn bộ giao diện portal.
- `dt_expense` dùng `dt_money_input.js` cho các ô nhập tiền.
- `dt_expense` và `dt_memoire` cùng dùng `dt.media` để quản lý file đính kèm.

## 6. Chỗ nên đọc đầu tiên nếu cần mở rộng
1. `controllers/portal.py`
2. `models/dt_media.py`
3. `templates/dt_core_templates.xml`
4. `static/src/js/dt_money_input.js`

## 7. Ghi chú vận hành
- `dt.media` hiện vẫn lưu chính thức bằng attachment của Odoo.
- Bug media upload tổng quát của project **chưa được xử lý trong đợt này**; chỉ phần upload avatar của profile đã được làm trong scope hiện tại.


## Cập nhật JS frontend

- Widget gợi ý nhập tiền đã được chuyển sang chuẩn website widget của Odoo bằng `publicWidget` (`@web/legacy/js/public/public_widget`).
- Selector áp dụng: `input[data-money-input="1"]`.
- Lý do: bám đúng lifecycle assets/frontend của Odoo portal, ổn định hơn so với cách tự bind bằng `DOMContentLoaded`.
