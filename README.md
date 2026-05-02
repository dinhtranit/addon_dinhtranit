# Family Portal Addons

Bộ source này gồm các module Odoo phục vụ trải nghiệm portal/mobile cho gia đình hoặc nhóm nhỏ. Hệ thống tập trung vào ba mảng chính:

- `dt_core`: khung portal, hồ sơ cá nhân, media dùng chung, điều hướng và cấu hình quyền xem dữ liệu gia đình.
- `dt_expense`: ứng dụng tài chính cá nhân/gia đình, gồm số dư hiện tại, giao dịch thu chi, điều chỉnh, danh mục cha/con, tháng hạch toán, lịch sử giao dịch, thống kê và gợi ý tiêu đề.
- `dt_memoire`: dòng thời gian memories, album, tag, media và quyền xem theo cấu hình gia đình.

## Mục tiêu của bộ source
- Tối ưu cho portal/mobile, ít thao tác, ít màn hình thừa.
- Tách rõ phần cấu hình dùng lâu dài khỏi phần nhập dữ liệu hàng ngày.
- Dùng chung các thành phần nền như avatar, media, navigation, profile và quyền xem dữ liệu.
- Hỗ trợ mở rộng dần mà không cần refactor lớn, đặc biệt ở phần tài chính.

## Luồng sử dụng chính
1. Người dùng đăng nhập portal.
2. Vào `Tài chính` để xem số dư, nhập thu chi và xem lịch sử/statistics.
3. Vào `Danh mục` để tạo danh mục cha/con và quản lý gợi ý tiêu đề nhập nhanh.
4. Vào `Tôi` để chỉnh hồ sơ, avatar và cấu hình ai trong gia đình được xem thu chi hoặc memories của mình.
5. Vào `Memories` để xem/tạo các kỷ niệm nếu được cấp quyền.

## Điểm thiết kế quan trọng
- `my/apps` không còn là trang trung gian; route này redirect về tài chính để flow gọn hơn.
- Quyền xem dữ liệu gia đình nằm ở profile, do chủ dữ liệu quyết định.
- Giao dịch tài chính có cả `ngày giao dịch` và `tháng hạch toán` để xử lý bài toán lương cuối tháng tính cho tháng sau.
- Danh mục tài chính hỗ trợ cha/con, chỉ danh mục lá được chọn khi nhập giao dịch.
- Gợi ý tiêu đề gồm hai nguồn: cấu hình thủ công theo danh mục và lịch sử đã dùng gần đây/nhiều lần.

Đọc file `PROJECT_MODULES_OVERVIEW.md` để nắm nhanh từng module, sau đó xem `MODULE_GUIDE.md` và `README.md` trong từng module để hiểu chi tiết cấu trúc, dữ liệu và luồng hoạt động.
