# -*- coding: utf-8 -*-
import mimetypes
import re
from pathlib import Path

from odoo import api, fields, models


class FamilyMedia(models.Model):
    _name = "dt.media"
    _description = "Family Shared Media"
    _order = "sequence, id"

    name = fields.Char(required=True)
    code = fields.Char(copy=False, index=True, default="New")
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    owner_user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, index=True)
    owner_partner_id = fields.Many2one("res.partner", related="owner_user_id.partner_id", store=True)
    attachment_id = fields.Many2one("ir.attachment", required=True, ondelete="cascade")
    media_type = fields.Selection(
        [("image", "Image"), ("video", "Video"), ("file", "File")],
        required=True,
        default="image",
        index=True,
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
        """Create media rows from portal uploads.

        Files are stored once in private Odoo attachments. The public `/web/content` URL is
        intentionally not exposed because it often fails for portal/private attachments. The
        portal uses `/my/family/media/<id>/content`, which checks family permission first and
        then streams image/video bytes with Range support.
        """
        owner_user = owner_user or self.env.user
        created = self.browse()
        if not record or not record.exists():
            return created
        existing_count = self.sudo().search_count([
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
                # `raw` takes the bytes straight through. Using `datas` would base64-encode
                # here only for Odoo to decode it again, which on a phone photo means two
                # extra copies of several MB for nothing.
                "raw": content,
                "mimetype": mimetype,
                "res_model": record._name,
                "res_id": record.id,
                "public": False,
                "type": "binary",
            })
            created |= self.sudo().create({
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
            })
        return created

    @api.model
    def create_staged_upload(self, upload, res_model, owner_user=None):
        """Store one upload straight away, before the record it belongs to exists.

        The portal starts uploading a photo the moment it is picked, in parallel with
        the user still typing the amount and description. The media row is therefore
        created "unattached" (``res_id = 0``) and later claimed by ``attach_staged``
        once the entry is saved. Rows that are never claimed are swept up here on the
        next upload, so an abandoned form leaves nothing behind for long.
        """
        owner_user = owner_user or self.env.user
        if not upload:
            return self.browse()
        content = upload.read()
        if not content:
            return self.browse()
        self._sweep_stale_staged(owner_user)
        filename = getattr(upload, "filename", None) or "upload"
        mimetype = getattr(upload, "mimetype", None) or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        media_type = "image" if mimetype.startswith("image/") else "video" if mimetype.startswith("video/") else "file"
        attachment = self.env["ir.attachment"].sudo().create({
            "name": filename,
            "raw": content,
            "mimetype": mimetype,
            "res_model": res_model,
            "res_id": 0,
            "public": False,
            "type": "binary",
        })
        return self.sudo().create({
            "name": self._clean_label(Path(filename).stem) or filename,
            "res_model": res_model,
            "res_id": 0,
            "owner_user_id": owner_user.id,
            "attachment_id": attachment.id,
            "media_type": media_type,
            "original_filename": filename,
            "mimetype": mimetype,
            "file_size": len(content),
            "sequence": 10,
        })

    @api.model
    def attach_staged(self, media_ids, record, owner_user=None, mark_first_cover=False):
        """Claim previously staged uploads for ``record``, keeping the order given."""
        owner_user = owner_user or self.env.user
        if not record or not record.exists() or not media_ids:
            return self.browse()
        wanted = [int(value) for value in media_ids if str(value).strip().isdigit()]
        if not wanted:
            return self.browse()
        staged = self.sudo().search([
            ("id", "in", wanted),
            ("res_model", "=", record._name),
            ("res_id", "=", 0),
            ("owner_user_id", "=", owner_user.id),
        ])
        if not staged:
            return self.browse()
        by_id = {media.id: media for media in staged}
        # Preserve the order the browser sent, not database order.
        ordered = [by_id[mid] for mid in wanted if mid in by_id]
        existing_count = self.sudo().search_count([
            ("res_model", "=", record._name),
            ("res_id", "=", record.id),
        ])
        seq_base = (existing_count + 1) * 10
        claimed = self.browse()
        for idx, media in enumerate(ordered):
            media.write({
                "res_id": record.id,
                "sequence": seq_base + idx,
                "is_cover": mark_first_cover and idx == 0 and existing_count == 0,
            })
            media.attachment_id.sudo().write({"res_id": record.id})
            claimed |= media
        return claimed

    @api.model
    def _sweep_stale_staged(self, owner_user, max_age_hours=24):
        """Drop this user's staged uploads that were never attached to a record."""
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), hours=max_age_hours)
        stale = self.sudo().search([
            ("res_id", "=", 0),
            ("owner_user_id", "=", owner_user.id),
            ("create_date", "<", cutoff),
        ])
        if stale:
            stale.unlink()

    @api.model
    def search_for_record(self, record):
        if not record or not record.exists():
            return self.browse()
        return self.sudo().search([
            ("res_model", "=", record._name),
            ("res_id", "=", record.id),
        ], order="is_cover desc, sequence, id")

    def can_read(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        if user.has_group("base.group_system") or self.owner_user_id == user:
            return True
        if not self.res_model or not self.res_id:
            return False
        try:
            record_model = self.env[self.res_model].sudo()
        except KeyError:
            return False
        record = record_model.browse(self.res_id)
        if not record.exists():
            return False
        if hasattr(record, "can_view"):
            return bool(record.can_view(user))
        return False

    def image_url(self):
        self.ensure_one()
        return "/my/family/media/%s/content" % self.id

    def stream_url(self):
        self.ensure_one()
        return "/my/family/media/%s/content" % self.id

    def download_url(self):
        self.ensure_one()
        return "/my/family/media/%s/content?download=1" % self.id

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
