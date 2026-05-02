# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DTFamilyAccess(models.Model):
    _name = "dt.family.access"
    _description = "Family Viewer Permission"
    _order = "owner_user_id, viewer_user_id"
    _rec_name = "display_name"
    _sql_constraints = [
        ("dt_family_access_unique", "unique(owner_user_id, viewer_user_id)", "Người xem này đã được cấu hình rồi."),
    ]

    owner_user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True, string="Chủ dữ liệu")
    viewer_user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True, string="Người được xem")
    allow_expense = fields.Boolean(string="Cho xem thu chi")
    allow_memory = fields.Boolean(string="Cho xem memories")
    active = fields.Boolean(default=True)
    display_name = fields.Char(compute="_compute_display_name")

    @api.depends("owner_user_id", "viewer_user_id")
    def _compute_display_name(self):
        for record in self:
            owner = record.owner_user_id.name or ""
            viewer = record.viewer_user_id.name or ""
            record.display_name = f"{owner} → {viewer}" if owner or viewer else "Quyền gia đình"

    @api.constrains("owner_user_id", "viewer_user_id")
    def _check_not_self(self):
        for record in self:
            if record.owner_user_id and record.viewer_user_id and record.owner_user_id == record.viewer_user_id:
                raise ValidationError("Không cần cấu hình xem chính mình.")
