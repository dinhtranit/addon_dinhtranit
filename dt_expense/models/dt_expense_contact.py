# -*- coding: utf-8 -*-
from odoo import fields, models, api


class DtExpenseContact(models.Model):
    _name = "dt.expense.contact"
    _description = "Personal Contact for Expense"
    _order = "name asc, id asc"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    name = fields.Char(required=True, string="Tên")
    phone = fields.Char(string="Số điện thoại")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("uniq_user_name", "UNIQUE(user_id, name)", "Liên hệ đã tồn tại trong danh sách của bạn."),
    ]

    def name_get(self):
        return [(r.id, r.name) for r in self]
