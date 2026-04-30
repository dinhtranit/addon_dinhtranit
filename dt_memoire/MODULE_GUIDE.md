# dt_memoire module guide

## 1. Mục đích
`dt_memoire` là app timeline kỷ niệm gia đình. Module này cho phép user lưu memory, album, tag, media và thiết lập mức độ riêng tư cho từng memory.

Trong kiến trúc tổng thể, đây là app nội dung/kỷ niệm, khác với `dt_expense` là app tài chính. Tuy vậy cả hai cùng dựa trên `dt_core` cho shell portal và media layer dùng chung.

## 2. Model chính

### 2.1 `dt.memoire.diary`
Bản ghi memory chính.

Field quan trọng:
- `title`, `code`
- `story`
- `memory_date`
- `location`
- `emotion`
- `category`
- `privacy`
- `shared_partner_ids`
- `album_id`, `tag_ids`
- `user_id`
- `is_pinned`, `view_count`
- `media_count`, `image_count`, `video_count`, `cover_media_id`

Rule quyền xem ở mức nghiệp vụ:
- owner luôn xem được
- `public`: ai có quyền truy cập portal/link phù hợp có thể xem
- `family`: user cùng company có thể xem
- `shared`: chỉ các partner được chia sẻ trực tiếp xem được

### 2.2 `dt.memoire.album`
Nhóm các memory theo album để dễ tổ chức timeline.

### 2.3 `dt.memoire.tag`
Tag tự do gắn cho memory để lọc và phân loại.

## 3. Controller / route portal
File chính: `dt_memoire/controllers/portal.py`

Route chính:
- `/my/apps/memories`
  - timeline các memory user có quyền xem
  - có search và filter
- `/my/apps/memories/<id>`
  - xem chi tiết memory
- `/my/apps/memories/new`
  - tạo memory mới
- `/my/apps/memories/<id>/edit`
  - sửa memory của chính mình
- `/my/apps/memories/save`
  - lưu memory portal
- route xóa memory và xóa media memory

## 4. Template / UI
File chính: `dt_memoire/templates/dt_memoire_templates.xml`

Màn hình chính:
- timeline memory
- form tạo/sửa memory
- trang chi tiết memory
- block album/tag/privacy/media

## 5. Media
`dt_memoire` không tự xây media layer riêng mà dùng chung `dt.media` từ `dt_core`.

Điều này có nghĩa là:
- logic đính kèm file của memoire và expense có gốc chung
- nếu sửa media layer ở `dt_core`, thường cả `dt_memoire` và `dt_expense` sẽ cùng bị ảnh hưởng hoặc cùng được hưởng lợi

## 6. Liên hệ với module khác
- dùng `portal_shell` của `dt_core`
- dùng `dt.media` của `dt_core`
- privacy của `dt_memoire` từng là nguồn tham chiếu ý tưởng để thiết kế privacy cho `dt_expense`

## 7. Những gì đã làm ở lần sửa này
- Không thay đổi nghiệp vụ chính của `dt_memoire` trong đợt này.
- Bổ sung tài liệu module để người đọc và AI nắm nhanh cấu trúc, vai trò và các điểm nên đọc đầu tiên.
- Giữ nguyên logic app memories hiện có để tránh đụng phạm vi chỉnh sửa đã thống nhất.

## 8. Chỗ nên đọc đầu tiên nếu cần mở rộng
1. `models/dt_memoire_diary.py`
2. `controllers/portal.py`
3. `templates/dt_memoire_templates.xml`
4. `views/dt_memoire_backend_views.xml`

## 9. Ghi chú
- Nếu sau này xử lý bug media upload chung, cần kiểm tra cả `dt_memoire` và `dt_expense` vì hai module cùng dùng `dt.media`.
- Trong đợt sửa hiện tại, `dt_memoire` chủ yếu được bổ sung tài liệu, chưa thay đổi logic kinh doanh.
