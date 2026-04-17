# -*- coding: utf-8 -*-
from odoo import api, fields, models


class DTExpenseCategory(models.Model):
    _name = "dt.expense.category"
    _description = "DT Expense Category"
    _order = "sequence, id"

    name = fields.Char(required=True)
    code = fields.Char(copy=False, index=True, default="New")
    icon = fields.Char(default="💸")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    user_id = fields.Many2one("res.users", string="Chủ sở hữu", help="Để trống để dùng chung cho cả nhà.")
    note = fields.Char()
    entry_count = fields.Integer(compute="_compute_entry_count")

    @api.depends("name")
    def _compute_entry_count(self):
        groups = self.env["dt.expense.entry"].read_group([("category_id", "in", self.ids)], ["category_id"], ["category_id"])
        mapped = {g["category_id"][0]: g["category_id_count"] for g in groups if g.get("category_id")}
        for category in self:
            category.entry_count = mapped.get(category.id, 0)

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if vals.get("code", "New") == "New":
                vals["code"] = seq.next_by_code("dt.expense.category") or "DTCAT"
        return super().create(vals_list)
