# dt_expense module guide

## 1. Mục đích
`dt_expense` là app theo dõi tài chính cá nhân/gia đình trên portal. Sau lần sửa này module không còn chỉ là app “chi tiêu” đơn thuần mà đã trở thành app **giao dịch tài chính cá nhân** gồm:
- chi tiêu
- thu nhập
- điều chỉnh số dư
- số dư hiện tại tính động từ lịch sử giao dịch
- danh mục thu/chi dùng chung hoặc riêng
- báo cáo theo kỳ

## 2. Khái niệm nghiệp vụ hiện tại

### 2.1 Ba loại giao dịch
- **Chi tiêu**: làm giảm số dư.
- **Thu nhập**: làm tăng số dư.
- **Điều chỉnh**: dùng để đồng bộ số dư thực tế với số dư đang tính trong hệ thống.

### 2.2 Số dư hiện tại hoạt động thế nào
User không ghi đè số dư một cách âm thầm. Thay vào đó:
1. user nhập số dư hiện tại mong muốn
2. hệ thống lấy số dư đang tính từ toàn bộ lịch sử giao dịch của chính user đó
3. hệ thống tính chênh lệch
4. nếu có chênh lệch thì tự sinh 1 giao dịch `adjustment`
   - chênh lệch dương => `increase`
   - chênh lệch âm => `decrease`

Công thức thực tế:
- income => `+amount`
- expense => `-amount`
- adjustment increase => `+amount`
- adjustment decrease => `-amount`

`current_balance = tổng signed amount của tất cả giao dịch của user`

## 3. Model

### 3.1 `dt.expense.category`
Đây là model danh mục dùng chung cho cả khoản chi và khoản thu.

#### Field chính
- `name`, `code`, `icon`, `sequence`, `note`, `active`
- `category_type`: `expense` hoặc `income`
- `scope`: `shared` hoặc `private`
- `user_id`: chủ sở hữu nếu là danh mục riêng
- `entry_count`: số giao dịch đang dùng danh mục này

#### Ý nghĩa
- `category_type` quyết định danh mục này dùng cho khoản chi hay khoản thu.
- `scope = shared` nghĩa là mọi user portal trong cùng hệ thống có thể dùng danh mục đó.
- `scope = private` nghĩa là chỉ chủ sở hữu dùng danh mục đó.

#### Rule normalize
- `shared` => `user_id = False`
- `private` => `user_id = current user`

### 3.2 `dt.expense.entry`
Đây là model giao dịch chính.

#### Field chính
- `name`, `code`, `display_name`
- `expense_date`
- `entry_type`: `expense`, `income`, `adjustment`
- `adjustment_direction`: `increase`, `decrease`
- `privacy`: `private`, `public`
- `category_id`
- `amount`
- `currency_id`
- `user_id`, `partner_id`, `company_id`
- `signed_amount`: giá trị có dấu dùng để tính số dư
- `amount_label`: chuỗi hiển thị như `+1.000.000 đ` hoặc `-50.000 đ`
- `amount_css_class`: class phục vụ hiển thị số âm/dương
- `media_count`, `cover_media_id`
- các key thời gian: `expense_year`, `expense_month_key`, `expense_week_key`

#### Ý nghĩa privacy
- `private`: chỉ owner nhìn thấy
- `public`: user đang đăng nhập trong cùng gia đình / công ty có thể thấy trong dashboard và report family scope

Quan trọng: `public` ở đây **không** có nghĩa là public ra internet.

#### Rule validate
- `amount` phải lớn hơn hoặc bằng 0
- VND không cho số lẻ
- `expense` và `income` bắt buộc có category
- `adjustment` không được gắn category
- category phải khớp `category_type` với `entry_type`

#### Hàm quan trọng
- `get_balance_effect()`: trả về signed amount thực của giao dịch
- `compute_current_balance(user)`: tính số dư hiện tại của user
- `create_balance_adjustment(target_amount, user, note='')`: tạo giao dịch adjustment để đưa số dư về đúng giá trị mong muốn
- `parse_money_text()`: parse chuỗi tiền nhập từ portal
- `_format_money()`: format tiền kiểu Việt có hậu tố `đ`

## 4. Currency và format tiền
- record mới mặc định dùng **VND** nếu hệ thống có currency `base.VND`
- nếu không có `base.VND` thì fallback sang company currency
- format hiển thị ở portal theo kiểu Việt: `1.000.000 đ`
- parse được các đầu vào như:
  - `1000000`
  - `1.000.000`
  - dữ liệu sinh ra từ nút gợi ý nhanh
- scope lần này chỉ đảm bảo **record mới** đi theo VND; dữ liệu cũ không bị ép đổi hàng loạt

## 5. Controller / route portal
File chính: `dt_expense/controllers/portal.py`

### Route chính
- `/my/apps/expenses`
  - dashboard chính của app
  - hiển thị số dư hiện tại, tổng thu tháng, tổng chi tháng, ròng tháng
  - có form cập nhật số dư hiện tại
  - có danh sách giao dịch user có quyền xem
- `/my/apps/expenses/new`
  - form tạo giao dịch
  - nhận `entry_type` qua query string để mở sẵn mode chi / thu / điều chỉnh
- `/my/apps/expenses/<id>/edit`
  - sửa giao dịch do chính user tạo
- `/my/apps/expenses/save`
  - lưu giao dịch portal
- `/my/apps/expenses/balance/save`
  - nhận số dư mong muốn rồi tự tạo giao dịch adjustment khi cần
- `/my/apps/expenses/<id>/delete`
  - xóa giao dịch của chính mình
- `/my/apps/expenses/media/<id>/delete`
  - xóa file media của giao dịch
- `/my/apps/expenses/categories`
  - quản lý danh mục thu/chi
- `/my/apps/expenses/categories/save`
  - lưu danh mục mới hoặc cập nhật danh mục
- `/my/apps/expenses/reports`
  - báo cáo theo tuần / tháng / năm
  - có view scope `mine` hoặc `family`
  - có lọc theo loại giao dịch và danh mục

### Rule quyền xem trong portal
Domain giao dịch “nhìn thấy được” đang đi theo rule:
- owner luôn thấy giao dịch của mình
- ngoài owner, chỉ thấy giao dịch có `privacy = public` và cùng `company_id`

## 6. Template / UI portal
File chính: `dt_expense/templates/dt_expense_templates.xml`

### 6.1 Dashboard
Có các khối chính:
- card số dư hiện tại
- card tổng thu tháng này
- card tổng chi tháng này
- card ròng tháng này
- form `Cập nhật số tiền hiện tại`
- shortcut vào tạo chi tiêu, tạo thu nhập, báo cáo, danh mục
- danh sách giao dịch gần đây có thể xem

### 6.2 Form giao dịch
Hỗ trợ:
- chọn loại giao dịch
- chọn hướng điều chỉnh nếu là adjustment
- chọn ngày giao dịch
- chọn danh mục phù hợp loại giao dịch
- chọn quyền xem `Riêng tư / Public trong gia đình-công ty`
- nhập số tiền kiểu VND với gợi ý nhanh
- nhập tiêu đề, ghi chú, file đính kèm

### 6.3 Trang danh mục
Cho phép tạo danh mục với:
- loại `Thu nhập` hoặc `Chi tiêu`
- phạm vi `Dùng chung` hoặc `Riêng tôi`
- icon, thứ tự, ghi chú

### 6.4 Trang báo cáo
Hiển thị:
- tổng thu trong kỳ
- tổng chi trong kỳ
- tổng adjustment trong kỳ
- giá trị ròng trong kỳ
- bar theo danh mục
- bar theo thời gian
- danh sách giao dịch trong kỳ

## 7. Asset frontend

### `dt_expense/static/src/js/dt_expense_form.js`
JS đồng bộ trạng thái của form theo `entry_type`.

Nhiệm vụ:
- nếu chọn `adjustment` thì ẩn category, hiện `adjustment_direction`
- nếu chọn `expense` hoặc `income` thì hiện category và lọc option đúng `category_type`
- tránh việc chọn sai danh mục so với loại giao dịch

### Input tiền reusable
Module này dùng lại `dt_core/static/src/js/dt_money_input.js`.

Các ô đang dùng component này:
- ô nhập số dư hiện tại trên dashboard
- ô nhập số tiền ở form giao dịch

Rule gợi ý hiện tại:
- nhập `1` => gợi ý `1.000`, `10.000`, `100.000`, `1.000.000`
- nhập `25` => gợi ý `25.000`, `250.000`, `2.500.000`, `25.000.000`

## 8. Dữ liệu mẫu
File: `dt_expense/data/dt_expense_data.xml`

Đã có sẵn danh mục mẫu:
- chi tiêu: Ăn uống, Học hành, Con cái, Đi lại, Y tế
- thu nhập: Lương, Thưởng, Kinh doanh

## 9. Migration / tương thích dữ liệu cũ
File: `dt_expense/hooks.py`

`post_init_hook` hiện xử lý các tình huống sau:
- fill `category_type` và `scope` nếu dữ liệu cũ chưa có
- map field cũ `visibility_scope` sang `scope` nếu tồn tại
- fill `entry_type` mặc định thành `expense` nếu còn null
- fill `privacy` mặc định thành `private`
- map dữ liệu cũ `privacy = family` thành `privacy = public`
- fill `adjustment_direction` mặc định thành `increase`
- map field cũ `adjustment_sign` sang `adjustment_direction` nếu còn tồn tại
- normalize `user_id` của category theo `scope`; nếu gặp category cũ đang `private` nhưng không còn owner thì chuyển sang `shared` để tránh gán nhầm cho superuser

Mục tiêu của hook là giảm rủi ro khi update từ các bản code thử nghiệm trước đó.

## 10. Những gì đã làm ở lần sửa này
1. Biến app chi tiêu thành app **thu chi + điều chỉnh số dư**.
2. Thêm nơi nhập **số tiền hiện tại** ngay trên dashboard.
3. Thêm **thu nhập nhiều nguồn** bằng cách dùng chung model category với `category_type`.
4. Thêm chọn **Riêng tư / Public trong gia đình-công ty** cho từng giao dịch.
5. Chuẩn hóa record mới theo **VND**, không dùng số lẻ.
6. Thêm component nhập tiền có gợi ý số 0 để thao tác nhanh trên mobile.
7. Cập nhật dashboard và report để nhìn được số dư, thu, chi, ròng theo kỳ.
8. Đồng bộ backend view, controller, template, model và hook theo cùng một bộ field.
9. Bổ sung tài liệu module để AI/human đọc nhanh module mà không cần dò toàn bộ code.

## 11. Known gap / điều chưa làm trong đợt này
- Bug upload media mà user đã nêu **chưa sửa trong đợt này** vì đã thống nhất để xử lý ở vòng sau.
- Nếu dữ liệu cũ có nhiều currency khác nhau thì phép cộng tổng hiện chưa quy đổi chéo currency; đây là hành vi cũ được giữ nguyên để tránh làm thay đổi dữ liệu ngoài scope.

## 12. Chỗ nên đọc đầu tiên nếu cần mở rộng
1. `models/dt_expense_entry.py`
2. `models/dt_expense_category.py`
3. `controllers/portal.py`
4. `templates/dt_expense_templates.xml`
5. `hooks.py`
