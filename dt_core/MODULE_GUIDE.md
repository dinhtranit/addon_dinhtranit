# dt_core - Module Guide

## Vai trò
Khung portal dùng chung cho các app Family.

## Thành phần chính
- `portal_shell`: layout mobile với topbar + bottom nav
- `my/profile`: cập nhật thông tin, đổi avatar, logout
- route `/my/apps`: hiện không còn là màn app home chính; đã redirect về `/my/apps/expenses` để giảm rối UX

## Các phần chịu trách nhiệm
### Controller `dt_core/controllers/portal.py`
- build base values chung cho portal
- xử lý trang profile
- lưu avatar / thông tin người dùng
- logout
- redirect `/my/apps`

### Template `dt_core/templates/dt_core_templates.xml`
- shell chung cho toàn bộ portal
- profile page
- bottom nav tài chính / timeline / tôi

## Ghi chú
`portal_apps_home` vẫn còn trong code để tương thích, nhưng route chính đã redirect sang app tài chính.
