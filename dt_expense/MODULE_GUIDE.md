# Hướng dẫn module `dt_expense`

## 1. Tư duy thiết kế
Module này ưu tiên hai mục tiêu cùng lúc:
- nhập giao dịch hằng ngày thật nhanh
- vẫn đủ cấu trúc để xem báo cáo đúng nghiệp vụ cá nhân/gia đình

Vì vậy nhiều chỗ được tách thành dữ liệu nền thay vì nhét logic vào giao diện.

## 2. Điểm nghiệp vụ quan trọng
### `tháng hạch toán`
Một giao dịch có thể thuộc tháng báo cáo khác với ngày giao dịch thật. Đây là nền để xử lý lương cuối tháng tính cho tháng sau.

### Rule cuối tháng → tháng sau
Rule này đặt ở danh mục (`apply_next_month_rule`). Khi một danh mục có bật cờ này, giao dịch phát sinh cuối tháng sẽ tự gợi ý `accounting_month` sang tháng sau.

### Danh mục cha/con
Danh mục cha chỉ dùng để nhóm và thống kê. Chỉ danh mục lá mới được chọn khi tạo giao dịch.

### Quyền xem gia đình
Khi chọn scope `Gia đình`, module không dùng cờ public/private trên giao dịch mà dựa vào `dt.family.access` trong `dt_core`.

## 3. Controller chính
### Home
- `/my/apps/expenses`
- hiển thị số dư, tóm tắt tháng, lối vào nhanh, giao dịch gần đây

### Giao dịch
- `/my/apps/expenses/new`
- `/my/apps/expenses/<id>/edit`
- `/my/apps/expenses/save`
- `/my/apps/expenses/<id>/delete`
- `/my/apps/expenses/balance/save`

### Danh mục và gợi ý
- `/my/apps/expenses/categories`
- `/my/apps/expenses/categories/new`
- `/my/apps/expenses/categories/<id>/edit`
- `/my/apps/expenses/categories/<id>/suggestions`
- các route save/delete tương ứng

### Lịch sử và autocomplete
- `/my/apps/expenses/history`
- `/my/apps/expenses/title_suggestions`

## 4. Frontend JS
### `dt_expense_form.js`
Chịu trách nhiệm cho:
- chuyển tab loại giao dịch
- ẩn/hiện field danh mục và adjustment
- đồng bộ tháng hạch toán theo ngày + rule danh mục
- autocomplete tiêu đề
- toggle card số dư
- toggle panel filter

## 5. Những chỗ cần test sau khi nâng cấp
- tạo giao dịch theo cả ba tab
- lương cuối tháng tự gợi ý sang tháng sau
- filter `Gia đình` có hiện đúng member và giao dịch
- danh mục cha/con chỉ chọn được lá
- autocomplete trả cả suggestion cấu hình tay và title history
- xóa danh mục đã có giao dịch sẽ inactive thay vì unlink cứng
