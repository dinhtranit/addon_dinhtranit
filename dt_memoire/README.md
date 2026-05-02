# dt_memoire

`dt_memoire` là module ghi lại memory/kỷ niệm theo dòng thời gian. Module này chia sẻ một số thành phần nền với `dt_core`, đặc biệt là avatar, shell portal, media và quyền xem gia đình.

## Chức năng chính
- Tạo memory theo ngày.
- Gắn nội dung, địa điểm, cảm xúc, album, tag.
- Đính kèm ảnh/video qua `dt.media`.
- Hiển thị timeline memories.
- Chi tiết memory với media đi kèm.
- Quyền xem dựa trên privacy của memory và cấu hình gia đình của chủ dữ liệu.

## Các thành phần chính
- `dt.memoire.diary`: model memory chính.
- `dt.memoire.album`: nhóm memory theo album.
- `dt.memoire.tag`: thẻ gắn memory.
- portal controller để feed, detail, create, edit, delete.

## Liên hệ với `dt_core`
- Dùng shell portal chung.
- Dùng `dt.media` để lưu media.
- Dùng helper `can_view_memory_from` từ cấu hình gia đình để quyết định người dùng hiện tại có được quyền xem dữ liệu của người khác không.
