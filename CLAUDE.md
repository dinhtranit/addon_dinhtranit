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
- **Config dev local (MacBook)**: `my_app.conf` (kèm repo này) — db `timeline_20260830`, port 8119; VSCode launch "Odoo: App 19".

> **Lưu ý:** Đây là dự án phụ / cá nhân, repo riêng `dinhtranit/addon_dinhtranit`, tách hẳn khỏi dự án chính Lovepop (`addons_lovepop/`). Mọi context về family/Dell nằm trong file này.

## Hạ tầng & vận hành (Dell OptiPlex Micro)

- **OS**: Ubuntu Server 24, SSH port 1601, user `dinhtranit` (sudoer)
- **VPN**: Tailscale — truy cập từ xa qua MacBook/iPhone
- **Domain**: family.mymywant.com (SSL qua Nginx)
- **LAN IP**: 192.168.1.10
- **SSD**: 256GB (OS) | **NVMe WD Black 1TB** (`/mnt/nas_data`) — filestore + logs + backup

| Service | Port | Ghi chú |
|---------|------|---------|
| Odoo 19 | 8069 | `/etc/systemd/system/odoo19.service` |
| PostgreSQL | 5432 | DB cho Odoo |
| Nginx | 80/443 | Reverse proxy + SSL |
| Immich | - | Lưu ảnh gia đình (Docker) |
| Tailscale | - | VPN |

### Tài khoản
- **Odoo login**: dinhtranit95@gmail.com / admin
- **DB Manager**: family.mymywant.com/web/database/manager
- **Ubuntu SSH**: `ssh dinhtranit@<tailscale-ip> -p 1601`

### MCP `dell-dinhtranit`
Claude có thể dùng: `shell`, `read_file`/`write_file`, `pg_query`, `odoo_log`, `services`, `restart_service`, `backup_db`, `list_addons`.

### Scripts deploy (kèm repo này)
- `deploy-category-sort.sh` — scp + SSH deploy `dt_expense` lên Dell (192.168.1.10)
- `fix-mcp-dell.sh` — sửa config MCP `dell-dinhtranit` trên Claude Desktop

### Luồng deploy
1. Viết code trên MacBook → 2. Deploy lên Dell bằng MCP `write_file` / rsync / `deploy-category-sort.sh` → 3. `restart_service odoo19` qua MCP → 4. Xem log qua `odoo_log`.

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
- **Cây danh mục**: `dt.expense.category` hỗ trợ `parent_id`. Cả danh mục cha lẫn danh mục lá đều chọn được khi tạo giao dịch.
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
- Chọn được cả danh mục cha lẫn danh mục lá trong form giao dịch, lưu không báo lỗi
- Autocomplete gộp cả gợi ý cấu hình tay và title history
- Xóa danh mục đã có giao dịch sẽ set inactive thay vì unlink cứng

## Vấn đề đã biết & thay đổi gần đây (cập nhật 2026-09-05)

Ghi chú này được Claude cập nhật sau khi đọc lại toàn bộ addon (dt_core, dt_expense, dt_memoire) và đối chiếu với git log/diff hiện tại — để tránh lặp lại các nhận định đã cũ.

- **Đã sửa**: Lỗi tạo trùng giao dịch khi bấm nhiều lần nút "Thêm giao dịch"/"Lưu giao dịch" (đặc biệt khi có đính kèm ảnh, request lâu, người dùng bấm lại). `dt_expense/static/src/js/dt_expense_form.js` (widget `DTExpenseForm`) nay có `_onFormSubmit` khoá nút bấm (`disabled`, class `is-loading`, đổi text thành "Đang lưu...") ngay khi submit và chặn các lần submit tiếp theo cho tới khi trang chuyển hướng; có `pageshow`/bfcache reset (`_resetSubmitState`) phòng trường hợp quay lại bằng nút Back. CSS tương ứng (`.dt-btn.is-loading`, `.dt-btn-spinner`, `@keyframes dt-btn-spin`) đã thêm vào `dt_expense/static/src/css/dt_expense_portal.scss`. **Lưu ý**: đây là fix phía client, chưa commit — vì Odoo cache/bundle asset frontend, cần chạy update module (`-u dt_expense`) hoặc "Regenerate Assets" (chế độ debug) hoặc restart service `odoo19` thì mới thấy hiệu lực trên trình duyệt.
- **Đã xác nhận hoạt động đúng, không cần sửa**: Route `expense_save` trong `dt_expense/controllers/portal.py` đã tự động `redirect` về `/my/apps/expenses/history` sau khi lưu giao dịch mới (trừ trường hợp giao dịch gắn với `plan_id` thì quay về trang plan tương ứng — đây là chủ đích, không phải lỗi).
- **Đã sửa (trước session này)**: Conflict marker git (`<<<<<<< Updated upstream` / `=======` / `>>>>>>> Stashed changes`) từng gây `SyntaxError` trong `dt_expense/controllers/portal.py` — đã được dọn sạch, không còn dấu vết trong code hiện tại.
- **Vẫn còn tồn tại, cần quyết định giữ hay bỏ**: `dt_expense/models/dt_expense_category.py` → `can_manage()` có điều kiện hardcode `user.login == 'dinhtranit95@gmail.com'` cho phép user này luôn quản lý được mọi danh mục, kể cả không sở hữu. Đây là một "backdoor" theo email cụ thể — nên xác nhận có chủ đích giữ lại hay refactor sang cơ chế nhóm/quyền chuẩn.
- **Tính năng mới chưa review kỹ**: `dt_expense/models/dt_expense_plan.py` (model `dt.expense.plan`, thêm ở commit `45f2c0c` "Add expense plans, wallet transfer, and lock borrowed funds") — chưa đọc chi tiết logic; form giao dịch (`portal_expense_form`) đã có sẵn dropdown chọn `plan_id` và `dt_expense/controllers/portal.py` đã hỗ trợ tham số `plan_id` khi tạo mới.
- **Trạng thái hạ tầng**: Lệnh kiểm tra service qua MCP `dell-dinhtranit` báo `odoo`/`odoo18` là `inactive` — đây là false alarm vì tool đang kiểm tra sai tên unit; service thật đang chạy là `odoo19.service` (xem log traffic real-time qua `odoo_log` để xác nhận server vẫn sống, đừng kết luận "server down" chỉ từ kết quả `services`).
