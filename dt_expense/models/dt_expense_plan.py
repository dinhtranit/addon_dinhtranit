# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FamilyExpensePlan(models.Model):
    _name = "dt.expense.plan"
    _description = "Family Expense Plan"
    _order = "create_date desc, id desc"

    name = fields.Char(required=True, string="Tên kế hoạch")
    code = fields.Char(copy=False, index=True, default="New")
    icon = fields.Char(default="🎯")
    image = fields.Image(string="Hình ảnh", max_width=256, max_height=256)
    note = fields.Text(string="Nội dung / Mô tả")
    budget_amount = fields.Monetary(currency_field="currency_id", string="Kinh phí mục tiêu")
    currency_id = fields.Many2one("res.currency", required=True, default=lambda self: self._default_currency_id())
    target_date = fields.Date(string="Ngày dự kiến hoàn thành")
    state = fields.Selection([
        ("active", "Đang thực hiện"),
        ("done", "Hoàn thành"),
        ("archived", "Lưu trữ"),
    ], default="active", required=True, index=True)
    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, index=True)
    entry_ids = fields.One2many("dt.expense.entry", "plan_id", string="Giao dịch")
    debt_ids = fields.One2many("dt.expense.debt", "plan_id", string="Khoản nợ")

    @api.model
    def _default_currency_id(self):
        vnd = self.env.ref("base.VND", raise_if_not_found=False)
        return (vnd or self.env.company.currency_id).id

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if vals.get("code", "New") == "New":
                vals["code"] = seq.next_by_code("dt.expense.plan") or "PLAN"
            vals.setdefault("user_id", self.env.user.id)
            vals.setdefault("currency_id", self._default_currency_id())
        return super().create(vals_list)

    @api.constrains("budget_amount")
    def _check_vnd_integer(self):
        vnd = self.env.ref("base.VND", raise_if_not_found=False)
        for plan in self:
            if vnd and plan.currency_id == vnd and plan.budget_amount != int(plan.budget_amount):
                raise ValidationError("Tiền VND không hỗ trợ số lẻ.")

    def can_manage(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        return bool(self.user_id == user or user.has_group("base.group_system"))
