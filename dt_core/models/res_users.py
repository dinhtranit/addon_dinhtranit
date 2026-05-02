# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    dt_family_access_ids = fields.One2many("dt.family.access", "owner_user_id", string="Cấu hình gia đình")
    dt_family_viewer_access_ids = fields.One2many("dt.family.access", "viewer_user_id", string="Quyền được xem")

    def _has_admin_rights(self):
        self.ensure_one()
        return self.has_group("base.group_system")

    def get_allowed_expense_viewer_ids(self):
        self.ensure_one()
        return self.env["dt.family.access"].sudo().search([
            ("owner_user_id", "=", self.id),
            ("allow_expense", "=", True),
            ("active", "=", True),
        ]).mapped("viewer_user_id").ids

    def get_allowed_memory_viewer_ids(self):
        self.ensure_one()
        return self.env["dt.family.access"].sudo().search([
            ("owner_user_id", "=", self.id),
            ("allow_memory", "=", True),
            ("active", "=", True),
        ]).mapped("viewer_user_id").ids

    def can_view_expense_from(self, owner_user):
        self.ensure_one()
        owner_user = owner_user.sudo() if owner_user else self.env.user
        if self == owner_user:
            return True
        return bool(self.env["dt.family.access"].sudo().search_count([
            ("owner_user_id", "=", owner_user.id),
            ("viewer_user_id", "=", self.id),
            ("allow_expense", "=", True),
            ("active", "=", True),
        ], limit=1))

    def can_view_memory_from(self, owner_user):
        self.ensure_one()
        owner_user = owner_user.sudo() if owner_user else self.env.user
        if self == owner_user:
            return True
        return bool(self.env["dt.family.access"].sudo().search_count([
            ("owner_user_id", "=", owner_user.id),
            ("viewer_user_id", "=", self.id),
            ("allow_memory", "=", True),
            ("active", "=", True),
        ], limit=1))

    def get_visible_expense_user_ids(self):
        self.ensure_one()
        allowed_owner_ids = self.env["dt.family.access"].sudo().search([
            ("viewer_user_id", "=", self.id),
            ("allow_expense", "=", True),
            ("active", "=", True),
        ]).mapped("owner_user_id").ids
        return list(dict.fromkeys([self.id] + allowed_owner_ids))

    def get_visible_memory_user_ids(self):
        self.ensure_one()
        allowed_owner_ids = self.env["dt.family.access"].sudo().search([
            ("viewer_user_id", "=", self.id),
            ("allow_memory", "=", True),
            ("active", "=", True),
        ]).mapped("owner_user_id").ids
        return list(dict.fromkeys([self.id] + allowed_owner_ids))
