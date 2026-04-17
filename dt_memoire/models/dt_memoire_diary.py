# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DTMemoireDiary(models.Model):
    _name = "dt.memoire.diary"
    _description = "DT Kỷ Niệm"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "memory_date desc, id desc"
    _rec_name = "title"

    title = fields.Char(required=True, tracking=True)
    code = fields.Char(copy=False, index=True, default="New")
    story = fields.Html(sanitize=True, sanitize_style=True)
    memory_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    location = fields.Char()
    emotion = fields.Selection([
        ("joyful", "😊 Vui vẻ"), ("loved", "❤️ Yêu thương"), ("grateful", "🙏 Biết ơn"),
        ("nostalgic", "🥺 Nhớ nhung"), ("proud", "🏆 Tự hào"), ("excited", "🎊 Háo hức"),
        ("peaceful", "🕊️ Bình yên"),
    ], default="joyful", tracking=True)
    category = fields.Selection([
        ("family", "🏠 Gia đình"), ("travel", "✈️ Du lịch"), ("birthday", "🎂 Sinh nhật"),
        ("daily", "📅 Hằng ngày"), ("school", "🎓 Học tập"), ("other", "📌 Khác"),
    ], default="daily")
    privacy = fields.Selection([
        ("private", "Chỉ mình tôi"), ("family", "Gia đình"), ("shared", "Chia sẻ chọn người"), ("public", "Công khai"),
    ], default="family", required=True, tracking=True)
    shared_partner_ids = fields.Many2many("res.partner", "dt_memoire_diary_partner_rel", "diary_id", "partner_id", string="Chia sẻ trực tiếp")
    album_id = fields.Many2one("dt.memoire.album", ondelete="set null")
    tag_ids = fields.Many2many("dt.memoire.tag", "dt_memoire_diary_tag_rel", "diary_id", "tag_id", string="Thẻ")
    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    partner_id = fields.Many2one("res.partner", related="user_id.partner_id", store=True)
    active = fields.Boolean(default=True)
    is_pinned = fields.Boolean(default=False)
    view_count = fields.Integer(default=0, readonly=True)
    memory_year = fields.Char(compute="_compute_date_parts", store=True)
    memory_month = fields.Char(compute="_compute_date_parts", store=True)
    memory_month_key = fields.Char(compute="_compute_date_parts", store=True, index=True)
    media_count = fields.Integer(compute="_compute_media_metrics")
    image_count = fields.Integer(compute="_compute_media_metrics")
    video_count = fields.Integer(compute="_compute_media_metrics")
    cover_media_id = fields.Many2one("dt.media", compute="_compute_media_metrics")

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if vals.get("code", "New") == "New":
                vals["code"] = seq.next_by_code("dt.memoire.diary") or "DTMEM"
        return super().create(vals_list)

    @api.depends("memory_date")
    def _compute_date_parts(self):
        month_names = {"01": "Tháng 1", "02": "Tháng 2", "03": "Tháng 3", "04": "Tháng 4", "05": "Tháng 5", "06": "Tháng 6", "07": "Tháng 7", "08": "Tháng 8", "09": "Tháng 9", "10": "Tháng 10", "11": "Tháng 11", "12": "Tháng 12"}
        for record in self:
            if record.memory_date:
                record.memory_year = record.memory_date.strftime("%Y")
                month_num = record.memory_date.strftime("%m")
                record.memory_month = month_names.get(month_num, "")
                record.memory_month_key = record.memory_date.strftime("%Y-%m")
            else:
                record.memory_year = False
                record.memory_month = False
                record.memory_month_key = False

    def _compute_media_metrics(self):
        groups = defaultdict(list)
        if self.ids:
            media_rows = self.env["dt.media"].sudo().search([("res_model", "=", self._name), ("res_id", "in", self.ids)], order="is_cover desc, sequence, id")
            for media in media_rows:
                groups[media.res_id].append(media)
        for record in self:
            media_rows = groups.get(record.id, [])
            record.media_count = len(media_rows)
            record.image_count = len([m for m in media_rows if m.media_type == "image"])
            record.video_count = len([m for m in media_rows if m.media_type == "video"])
            record.cover_media_id = media_rows[0] if media_rows else False

    @api.constrains("memory_date")
    def _check_memory_date(self):
        for record in self:
            if record.memory_date and record.memory_date > fields.Date.context_today(record):
                raise ValidationError("Ngày kỷ niệm không thể là ngày tương lai.")

    def get_media_items(self):
        self.ensure_one()
        return self.env["dt.media"].sudo().search([("res_model", "=", self._name), ("res_id", "=", self.id)], order="is_cover desc, sequence, id")

    def can_view(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        if self.user_id == user:
            return True
        if self.privacy == "public":
            return True
        if self.privacy == "family" and self.user_id.company_id == user.company_id:
            return True
        if self.privacy == "shared" and user.partner_id in self.shared_partner_ids:
            return True
        return False

    def get_emotion_icon(self):
        return {"joyful": "😊", "loved": "❤️", "grateful": "🙏", "nostalgic": "🥺", "proud": "🏆", "excited": "🎊", "peaceful": "🕊️"}.get(self.emotion, "📔")
