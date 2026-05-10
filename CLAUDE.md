# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Tổng quan

Đây là bản cài **Odoo 19.0 Enterprise** kèm ứng dụng portal gia đình tùy chỉnh. Toàn bộ code tùy chỉnh nằm trong `/odoo/addon_dinhtranit/`, gồm ba module xây trên framework portal của Odoo.

## Các lệnh thường dùng

Tất cả lệnh dùng môi trường Python ảo tại `/odoo/venv/` và binary Odoo trong thư mục enterprise.

```bash
# Khởi động server Odoo
/odoo/venv/bin/python /odoo/enterprise/odoo-bin -c /odoo/config/odoo.conf

# Cài module lần đầu
/odoo/venv/bin/python /odoo/enterprise/odoo-bin -c /odoo/config/odoo.conf -d <dbname> -i dt_core,dt_expense,dt_memoire

# Cập nhật module sau khi sửa code (dùng thường xuyên nhất khi dev)
/odoo/venv/bin/python /odoo/enterprise/odoo-bin -c /odoo/config/odoo.conf -d <dbname> -u dt_expense --no-http

# Chạy test cho một module
/odoo/venv/bin/python /odoo/enterprise/odoo-bin -c /odoo/config/odoo.conf -d <dbname> --test-enable -i dt_expense --stop-after-init

# Shell tương tác để debug
/odoo/venv/bin/python /odoo/enterprise/odoo-bin shell -c /odoo/config/odoo.conf -d <dbname>

# Tạo khung module mới
/odoo/venv/bin/python /odoo/enterprise/odoo-bin scaffold new_module /odoo/addon_dinhtranit/
```

Lint dùng flake8, cấu hình tại `/odoo/enterprise/setup.cfg`.

## Cấu hình

- File cấu hình: `/odoo/config/odoo.conf`
- HTTP port: `8069` trên `0.0.0.0`
- Addon paths: `/odoo/enterprise/odoo/addons`, `/odoo/addon_dinhtranit`
- Filestore/data: `/mnt/nas_data/odoo_filestore`
- Log: `/mnt/nas_data/odoo_filestore/logs/odoo.log`
- Workers: `0` (chế độ single-threaded/gevent)

## Kiến trúc module tùy chỉnh

Ba module đều theo cấu trúc Odoo chuẩn: `models/`, `controllers/`, `templates/`, `views/`, `static/`, `security/`, `data/`.

### `dt_core` — Nền tảng portal

Module phụ thuộc của hai module còn lại. Không chứa logic nghiệp vụ riêng.

- **Shell template** (`templates/dt_core_templates.xml`): `portal_shell` — layout chung gồm header, nút quay lại, avatar và bottom navigation cố định. Các module khác đều extend template này.
- **Model quyền gia đình** (`models/dt_family_access.py`): `dt.family.access` lưu ai được xem dữ liệu của ai, phân theo loại (tài chính vs. memories). `models/res_users.py` cung cấp helper (`can_view_expense_from`, `can_view_memory_from`) cho các module khác dùng.
- **Model media dùng chung** (`models/dt_media.py`): `dt.media` là lớp đính kèm file chung; các module trỏ vào qua `res_model` + `res_id` thay vì tự viết lại luồng upload.
- **Routes**: `/my/apps` → redirect về `/my/apps/expenses`, `/my/profile`, `/my/profile/save`, `/my/profile/logout`.

### `dt_expense` — Ứng dụng tài chính

Module có nhiều logic nghiệp vụ nhất. Các quy tắc quan trọng:

- **`accounting_month` vs `expense_date`**: Mỗi giao dịch có cả ngày thật lẫn tháng hạch toán. Cơ chế này xử lý bài toán lương trả cuối tháng nhưng tính vào tháng sau.
- **`apply_next_month_rule`** trên `dt.expense.category`: Khi bật, giao dịch mới thuộc danh mục đó sẽ tự gợi ý `accounting_month` sang tháng tiếp theo.
- **Cây danh mục**: `dt.expense.category` hỗ trợ `parent_id`. Chỉ danh mục lá (`is_leaf=True`) mới được chọn khi tạo giao dịch.
- **Gợi ý tiêu đề** đến từ hai nguồn: `dt.expense.title.suggestion` (cấu hình tay theo danh mục) và `dt.expense.title.history` (học từ lịch sử đã nhập). Route autocomplete gộp cả hai.
- **Số dư** được tính từ lịch sử giao dịch. Cập nhật số dư thực tế sẽ tạo một giao dịch `adjustment`.
- **Phạm vi gia đình**: Khi lọc theo gia đình, module đọc `dt.family.access` từ `dt_core` — không dùng cờ riêng trên từng giao dịch.

File chính: `models/dt_expense_entry.py`, `models/dt_expense_category.py`, `controllers/portal.py`, `static/src/js/dt_expense_form.js`.

Routes portal: `/my/apps/expenses`, `/my/apps/expenses/new`, `/my/apps/expenses/<id>/edit`, `/my/apps/expenses/history`, `/my/apps/expenses/categories`, `/my/apps/expenses/title_suggestions`.

### `dt_memoire` — Dòng thời gian kỷ niệm

Đơn giản hơn `dt_expense`. Dùng lại shell của `dt_core`, `dt.media` cho đính kèm file, và helper quyền gia đình.

- **`dt.memoire.diary`**: Record memory chính gồm ngày, nội dung, địa điểm, cảm xúc, album, tag, mức privacy.
- **`dt.memoire.album`** và **`dt.memoire.tag`**: Model nhóm và gắn thẻ.
- Kiểm tra quyền: kết hợp privacy của memory với `can_view_memory_from` từ `dt_core`.

## Thêm module mới

1. Scaffold: `odoo-bin scaffold <name> /odoo/addon_dinhtranit/`
2. Thêm `"dt_core"` vào `depends` trong `__manifest__.py`.
3. Extend `portal_shell` trong template để dùng layout chung.
4. Dùng `dt.media` cho đính kèm file thay vì `ir.attachment` trực tiếp.
5. Gọi helper trên `res.users` từ `dt_core` để kiểm tra quyền xem gia đình.
6. Thêm đường dẫn module vào `addons_path` trong `odoo.conf` nếu tạo thư mục mới.

## Kiểm tra sau khi sửa `dt_expense`

- Tạo giao dịch theo cả ba tab (chi tiêu, thu nhập, điều chỉnh)
- Danh mục lương cuối tháng tự gợi ý `accounting_month` sang tháng sau
- Filter gia đình hiển thị đúng thành viên và giao dịch
- Danh mục cha không chọn được trong form giao dịch (chỉ chọn danh mục lá)
- Autocomplete gộp cả gợi ý cấu hình tay và title history
- Xóa danh mục đã có giao dịch sẽ set inactive thay vì unlink cứng
