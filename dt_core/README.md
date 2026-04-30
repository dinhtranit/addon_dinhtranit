# dt_core

Module nền cho toàn bộ project Family.

Đọc nhanh:
- `MODULE_GUIDE.md`: mô tả đầy đủ model, controller, template, asset và thay đổi đã làm
- `controllers/portal.py`: route `/my/apps`, `/my/profile`, `/my/profile/save`, `/my/profile/logout`
- `models/dt_media.py`: media layer dùng chung
- `static/src/js/dt_money_input.js`: input tiền reusable

Các thay đổi chính ở đợt này:
- thêm nút đăng xuất rõ ràng trong profile
- thêm đổi avatar
- bỏ shortcut memories/expense khỏi profile
- thêm component JS gợi ý nhập tiền để module khác tái sử dụng
