# dt_expense

`dt_expense` là module tài chính chính của bộ addon. Mục tiêu của module là ghi nhận giao dịch nhanh trên điện thoại nhưng vẫn đủ dữ liệu để xem lịch sử, thống kê và mở rộng về sau.

## Chức năng chính
- Theo dõi số dư hiện tại.
- Ghi nhận giao dịch chi tiêu, thu nhập, điều chỉnh.
- Tự tính số dư từ lịch sử giao dịch.
- Hỗ trợ tháng hạch toán riêng để xử lý bài toán lương cuối tháng tính cho tháng sau.
- Quản lý danh mục cha/con.
- Quản lý gợi ý tiêu đề theo danh mục.
- Học từ lịch sử tiêu đề đã nhập.
- Cho phép xem dữ liệu của gia đình theo quyền do chủ dữ liệu cấp.

## Luồng sử dụng
1. Vào `Tài chính` để xem số dư và các chỉ số ngắn.
2. Bấm card số dư nếu muốn cập nhật số dư thực tế.
3. Bấm nút `+` để tạo giao dịch mới.
4. Vào `Danh mục` để quản lý cấu trúc danh mục và gợi ý tiêu đề.
5. Vào `Lịch sử giao dịch` để tìm kiếm, lọc, xem hoạt động hoặc thống kê.

## Mô hình dữ liệu
### `dt.expense.entry`
Một giao dịch gồm:
- `expense_date`: ngày giao dịch thật
- `accounting_month`: tháng hạch toán
- `entry_type`: expense / income / adjustment
- `category_id`
- `amount`
- `adjustment_direction`
- `name`, `note`
- `user_id`

### `dt.expense.category`
Danh mục tài chính:
- phân loại `expense` hoặc `income`
- hỗ trợ `parent_id` để tạo cha/con
- `is_leaf` giúp chỉ cho chọn danh mục lá
- `apply_next_month_rule` để tự gợi ý tháng sau

### `dt.expense.title.suggestion`
Các mẫu tiêu đề do người dùng tự cấu hình cho từng danh mục.

### `dt.expense.title.history`
Lịch sử tiêu đề đã dùng để autocomplete thông minh hơn.

## Giao diện portal
### Home
- card số dư hiện tại
- form cập nhật số dư ẩn/hiện theo card
- các chỉ số tháng hiện tại
- lối vào nhanh đến lịch sử và danh mục
- một vài giao dịch gần đây

### Form giao dịch
- tab loại giao dịch ở đầu form
- danh mục lọc theo loại đang chọn
- tiêu đề có autocomplete
- tiền nhập dạng text VND + gợi ý số 0
- tháng hạch toán chỉnh tay được

### Danh mục
- dạng list-first
- quản lý bằng menu 3 chấm
- danh mục cha/con
- trang riêng cho gợi ý tiêu đề

### Lịch sử giao dịch
- tab `Hoạt động` và `Thống kê`
- search trên header
- filter panel ẩn/hiện qua icon filter
- filter theo gia đình, thành viên, ngày, loại, danh mục
- tab thống kê có biểu đồ tròn

## Lưu ý mở rộng
- Muốn fuzzy search tốt hơn cho tiêu đề thì nâng cấp route autocomplete, không cần đổi model.
- Muốn thống kê sâu hơn có thể thêm trường `accounting_month_key` vào các báo cáo backend.
- Muốn family category dùng chung thật sự thì cần thêm tầng quyền riêng cho category; hiện tại category thuộc từng user.
