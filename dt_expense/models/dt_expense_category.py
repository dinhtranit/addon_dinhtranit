# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FamilyExpenseCategory(models.Model):
    _name = "dt.expense.category"
    _description = "Family Expense Category"
    _order = "category_type, sequence, id"

    name = fields.Char(required=True)
    code = fields.Char(copy=False, index=True, default="New")
    icon = fields.Char(default="💸")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    category_type = fields.Selection([
        ("expense", "Chi tiêu"),
        ("income", "Thu nhập"),
    ], string="Nhóm giao dịch", required=True, default="expense", index=True)
    parent_id = fields.Many2one("dt.expense.category", string="Danh mục cha", domain="[('id','!=',id),('category_type','=',category_type)]", ondelete="restrict")
    child_ids = fields.One2many("dt.expense.category", "parent_id", string="Danh mục con")
    is_leaf = fields.Boolean(compute="_compute_is_leaf", store=True)
    apply_next_month_rule = fields.Boolean(string="Tính cho tháng sau", help="Nếu bật, giao dịch cuối tháng thuộc danh mục này sẽ được tự gợi ý hạch toán sang tháng sau.")
    user_id = fields.Many2one("res.users", string="Người tạo", required=True, default=lambda self: self.env.user, index=True)
    note = fields.Char()
    entry_count = fields.Integer(compute="_compute_entry_count")
    suggestion_count = fields.Integer(compute="_compute_suggestion_count")

    @api.depends("child_ids")
    def _compute_is_leaf(self):
        for category in self:
            category.is_leaf = not bool(category.child_ids.filtered(lambda c: c.active))

    @api.depends("name")
    def _compute_entry_count(self):
        groups = self.env["dt.expense.entry"].read_group([("category_id", "in", self.ids)], ["category_id"], ["category_id"])
        mapped = {group["category_id"][0]: group["category_id_count"] for group in groups if group.get("category_id")}
        for category in self:
            category.entry_count = mapped.get(category.id, 0)

    @api.depends("name")
    def _compute_suggestion_count(self):
        groups = self.env["dt.expense.title.suggestion"].read_group([("category_id", "in", self.ids)], ["category_id"], ["category_id"])
        mapped = {group["category_id"][0]: group["category_id_count"] for group in groups if group.get("category_id")}
        for category in self:
            category.suggestion_count = mapped.get(category.id, 0)

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        normalized_vals = []
        for vals in vals_list:
            vals = dict(vals)
            if vals.get("code", "New") == "New":
                vals["code"] = seq.next_by_code("dt.expense.category") or "FamilyCAT"
            vals.setdefault("user_id", self.env.user.id)
            normalized_vals.append(vals)
        return super().create(normalized_vals)

    @api.constrains("parent_id", "category_type")
    def _check_parent_type(self):
        for record in self:
            if record.parent_id and record.parent_id.category_type != record.category_type:
                raise ValidationError("Danh mục cha phải cùng loại giao dịch.")

    def get_category_type_label(self):
        self.ensure_one()
        return dict(self._fields["category_type"].selection).get(self.category_type or "expense", "Chi tiêu")

    def can_manage(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        return bool(self.user_id == user or user.has_group("base.group_system"))
