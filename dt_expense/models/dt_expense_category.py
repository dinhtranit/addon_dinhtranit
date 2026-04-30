# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FamilyExpenseCategory(models.Model):
    _name = "dt.expense.category"
    _description = "Family Expense Category"
    _order = "category_type, sequence, id"

    name = fields.Char(required=True)
    code = fields.Char(copy=False, index=True, default="New")
    icon = fields.Char(default="💸")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    category_type = fields.Selection(
        [("expense", "Chi tiêu"), ("income", "Thu nhập")],
        string="Nhóm giao dịch",
        required=True,
        default="expense",
        index=True,
    )
    scope = fields.Selection(
        [("shared", "Dùng chung"), ("private", "Riêng tôi")],
        string="Phạm vi sử dụng",
        required=True,
        default="shared",
        index=True,
    )
    user_id = fields.Many2one("res.users", string="Chủ sở hữu", help="Để trống để dùng chung cho cả gia đình / công ty.")
    note = fields.Char()
    entry_count = fields.Integer(compute="_compute_entry_count")

    @api.depends("name")
    def _compute_entry_count(self):
        groups = self.env["dt.expense.entry"].read_group([("category_id", "in", self.ids)], ["category_id"], ["category_id"])
        mapped = {group["category_id"][0]: group["category_id_count"] for group in groups if group.get("category_id")}
        for category in self:
            category.entry_count = mapped.get(category.id, 0)

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        normalized_vals = []
        for vals in vals_list:
            vals = self._normalize_scope_vals(dict(vals))
            if vals.get("code", "New") == "New":
                vals["code"] = seq.next_by_code("dt.expense.category") or "FamilyCAT"
            normalized_vals.append(vals)
        return super().create(normalized_vals)

    def write(self, vals):
        return super().write(self._normalize_scope_vals(dict(vals)))

    def _normalize_scope_vals(self, vals):
        scope = vals.get("scope")
        if scope == "shared":
            vals["user_id"] = False
        elif scope == "private" and not vals.get("user_id"):
            vals["user_id"] = self.env.user.id
        elif "user_id" in vals and vals.get("user_id"):
            vals.setdefault("scope", "private")
        elif "user_id" in vals and not vals.get("user_id"):
            vals.setdefault("scope", "shared")
        vals.setdefault("category_type", "expense")
        vals.setdefault("scope", "shared")
        return vals

    def get_scope_label(self):
        self.ensure_one()
        return dict(self._fields["scope"].selection).get(self.scope or "shared", "Dùng chung")

    def get_category_type_label(self):
        self.ensure_one()
        return dict(self._fields["category_type"].selection).get(self.category_type or "expense", "Chi tiêu")

    def can_access(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        return bool(self.scope == "shared" or self.user_id == user)

    def can_manage(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        return bool(user.has_group("base.group_system") or self.create_uid == user)

    def get_suggestions(self):
        self.ensure_one()
        return self.env["dt.expense.title.suggestion"].search([("category_id", "=", self.id)], order="sequence, is_manual desc, usage_count desc, id desc")
