# Project Modules Overview

## dt_core
Khung portal chung cho bộ module.
- shell mobile
- profile, avatar, logout
- route `/my/apps` hiện redirect thẳng sang tài chính để giảm rối giao diện

## dt_expense
App tài chính hiện là app chính của bộ portal.
- bỏ vai trò "apps home" trong trải nghiệm chính
- số dư bấm card mới hiện form cập nhật
- danh mục chuyển sang list-first, create/edit theo panel bật/tắt
- có hệ gợi ý tiêu đề: cấu hình tay + học từ lịch sử
- autocomplete tiêu đề theo danh mục ngay trong form giao dịch

## dt_memoire
App timeline/memory vẫn độc lập, không chỉnh sâu trong đợt này.
