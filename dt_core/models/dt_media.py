# -*- coding: utf-8 -*-
import base64
import mimetypes
import re
from pathlib import Path

from odoo import api, fields, models


class DTMedia(models.Model):
    _name = "dt.media"
    _description = "DT Shared Media"
    _order = "sequence, id"

    name = fields.Char(required=True)
    code = fields.Char(copy=False, index=True, default="New")
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    owner_user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    owner_partner_id = fields.Many2one("res.partner", related="owner_user_id.partner_id", store=True)
    attachment_id = fields.Many2one("ir.attachment", required=True, ondelete="cascade")
    media_type = fields.Selection(
        [("image", "Image"), ("video", "Video"), ("file", "File")],
        required=True,
        default="image",
    )
    original_filename = fields.Char()
    mimetype = fields.Char()
    file_size = fields.Integer()
    note = fields.Char(string="Ghi chú")
    sequence = fields.Integer(default=10)
    is_cover = fields.Boolean(default=False)
    storage_state = fields.Selection(
        [
            ("disabled", "Disabled"),
            ("planned", "Planned"),
            ("exported", "Exported"),
            ("error", "Error"),
        ],
        default="disabled",
        help="Hiện tại chỉ lưu chuẩn Odoo. Trạng thái này để dành cho giai đoạn đồng bộ kho file ngoài sau này.",
    )
    planned_storage_path = fields.Char(
        help="Đường dẫn dự kiến cho kho file ngoài. Hiện chưa ghi file ra đây để tránh nhân đôi dung lượng.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        params = self.env["ir.config_parameter"].sudo()
        folder_pattern = params.get_param("dt_core.storage_folder_pattern") or "{module}/{date}/{record_code}"
        for vals in vals_list:
            if vals.get("code", "New") == "New":
                vals["code"] = seq.next_by_code("dt.media.code") or "MEDIA"
            vals.setdefault("storage_state", "disabled")
            vals.setdefault("planned_storage_path", self._build_planned_storage_path(vals, folder_pattern))
        return super().create(vals_list)

    def unlink(self):
        attachments = self.mapped("attachment_id").sudo()
        result = super().unlink()
        attachments.unlink()
        return result

    @api.model
    def create_from_uploads(self, uploads, record, owner_user=None, mark_first_cover=False):
        """Create shared media rows from portal uploads.

        Current design choice:
        - Keep Odoo attachments as the only real storage.
        - Do NOT copy files to an external folder yet, to avoid doubling disk usage.
        - planned_storage_path is only a future hint, based on settings, for the phase when
          the owner wants to sync to cloud or a separate disk.
        """
        owner_user = owner_user or self.env.user
        created = self.browse()
        existing_count = self.search_count([
            ("res_model", "=", record._name),
            ("res_id", "=", record.id),
        ])
        seq_base = (existing_count + 1) * 10
        for idx, upload in enumerate(uploads or []):
            if not upload:
                continue
            filename = getattr(upload, "filename", None) or f"{record._name.replace('.', '_')}_{record.id}_{idx + 1}"
            content = upload.read()
            if not content:
                continue
            mimetype = getattr(upload, "mimetype", None) or mimetypes.guess_type(filename)[0] or "application/octet-stream"
            media_type = "image" if mimetype.startswith("image/") else "video" if mimetype.startswith("video/") else "file"
            attachment = self.env["ir.attachment"].sudo().create({
                "name": filename,
                "datas": base64.b64encode(content),
                "mimetype": mimetype,
                "res_model": record._name,
                "res_id": record.id,
                "public": False,
                "type": "binary",
            })
            media_vals = {
                "name": self._clean_label(Path(filename).stem) or filename,
                "res_model": record._name,
                "res_id": record.id,
                "owner_user_id": owner_user.id,
                "attachment_id": attachment.id,
                "media_type": media_type,
                "original_filename": filename,
                "mimetype": mimetype,
                "file_size": len(content),
                "sequence": seq_base + idx,
                "is_cover": mark_first_cover and idx == 0 and existing_count == 0,
            }
            created |= self.create(media_vals)
        return created

    @api.model
    def search_for_record(self, record):
        return self.search([
            ("res_model", "=", record._name),
            ("res_id", "=", record.id),
        ], order="is_cover desc, sequence, id")

    def image_url(self):
        self.ensure_one()
        return f"/web/image/ir.attachment/{self.attachment_id.id}/datas"

    def stream_url(self):
        self.ensure_one()
        return f"/web/content/{self.attachment_id.id}?download=false"

    def download_url(self):
        self.ensure_one()
        return f"/web/content/{self.attachment_id.id}?download=true"

    def _build_planned_storage_path(self, vals, folder_pattern):
        res_model = vals.get("res_model") or "record"
        res_id = vals.get("res_id") or 0
        owner_user = self.env["res.users"].browse(vals.get("owner_user_id")) if vals.get("owner_user_id") else self.env.user
        record_code = vals.get("code") or f"{res_model.replace('.', '_')}_{res_id}"
        today = fields.Date.context_today(self)
        tokens = {
            "module": res_model.replace("dt.", "").replace(".", "/"),
            "date": today.isoformat(),
            "year": str(today.year),
            "month": f"{today.month:02d}",
            "record_code": record_code,
            "user_code": owner_user.partner_id.dt_member_code or "family",
            "media_type": vals.get("media_type") or "file",
        }
        path = folder_pattern
        for key, value in tokens.items():
            path = path.replace("{" + key + "}", value)
        path = re.sub(r"/+", "/", path).strip("/")
        return path

    @api.model
    def _clean_label(self, value):
        value = (value or "").strip()
        value = re.sub(r"[_\-]+", " ", value)
        value = re.sub(r"\s+", " ", value)
        return value[:120]
