# Hướng dẫn module `dt_memoire`

## Mục tiêu
Module này dùng để ghi lại kỷ niệm theo cách gần giống một timeline cá nhân/gia đình. Dữ liệu được trình bày nhẹ, giàu media và có phân quyền xem.

## Model chính
### `dt.memoire.diary`
Một memory gồm:
- tiêu đề
- ngày memory
- nội dung HTML
- địa điểm
- cảm xúc
- category
- privacy
- album, tag
- user tạo
- media đính kèm

## Quyền xem
Hiện module kết hợp hai lớp quyền:
1. cấu hình gia đình từ `dt_core` để xác định người xem có được xem dữ liệu của owner không
2. privacy nội tại của từng memory (`private`, `family`, `shared`, `public`)

Điều này giúp giữ tương thích với dữ liệu memories cũ nhưng vẫn đi theo mô hình family permission mới.

## Controller chính
- feed memories
- detail memory
- create/edit/delete memory
- delete media của memory

## Khi cần mở rộng
- Có thể bỏ privacy mức record nếu muốn chuyển hoàn toàn sang quyền ở profile.
- Có thể thêm timeline filter theo owner trong chế độ gia đình, tương tự `dt_expense`.
