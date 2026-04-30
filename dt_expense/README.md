# dt_expense

App thu chi cá nhân/gia đình trên portal.

Đọc nhanh:
- `MODULE_GUIDE.md`: mô tả chi tiết nghiệp vụ, route, field, migration hook
- `models/dt_expense_entry.py`: logic giao dịch, số dư, VND, helper format/parse
- `models/dt_expense_category.py`: danh mục thu/chi dùng chung hoặc riêng
- `controllers/portal.py`: dashboard, form, báo cáo, danh mục
- `hooks.py`: normalize dữ liệu cũ khi update module

Các thay đổi chính ở đợt này:
- thêm thu nhập và điều chỉnh số dư
- thêm nơi nhập số tiền hiện tại
- thêm privacy private/public trong gia đình-công ty
- record mới mặc định VND, không cho số lẻ
- thêm input tiền có gợi ý bấm nhanh 1.000 / 10.000 / 100.000 / 1.000.000
