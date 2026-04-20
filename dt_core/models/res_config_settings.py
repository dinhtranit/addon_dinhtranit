# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    dt_storage_root_path = fields.Char(
        string="Family storage root",
        config_parameter="dt_core.storage_root_path",
        help="Đường dẫn gốc dự kiến cho kho file ngoài ở giai đoạn sau.",
    )
    dt_storage_folder_pattern = fields.Char(
        string="Folder pattern",
        config_parameter="dt_core.storage_folder_pattern",
        default="{module}/{date}/{record_code}",
        help="Mẫu thư mục cho giai đoạn đồng bộ file ngoài. Hỗ trợ token như {module}, {date}, {record_code}, {user_code}.",
    )
    dt_storage_flat_family_mode = fields.Boolean(
        string="Ưu tiên cây thư mục phẳng cho gia đình",
        config_parameter="dt_core.storage_flat_family_mode",
        default=True,
        help="Bật để sau này gom file theo date hoặc record code, không tách quá nhiều tầng theo user.",
    )
    dt_storage_future_sync_note = fields.Char(
        string="Ghi chú vận hành",
        config_parameter="dt_core.storage_future_sync_note",
        help="Ghi chú nội bộ cho kế hoạch đồng bộ cloud hoặc ổ cứng riêng trong giai đoạn sau.",
    )
