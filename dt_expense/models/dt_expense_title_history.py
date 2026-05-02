# -*- coding: utf-8 -*-
from odoo import fields, models


class FamilyExpenseTitleHistory(models.Model):
    _name = "dt.expense.title.history"
    _description = "Expense Title History"
    _order = "used_count desc, last_used_at desc, id desc"
    _sql_constraints = [
        ("dt_expense_title_history_unique", "unique(user_id, category_id, normalized_name)", "Lịch sử tiêu đề đã tồn tại."),
    ]

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    category_id = fields.Many2one("dt.expense.category", required=True, ondelete="cascade", index=True)
    name = fields.Char(required=True)
    normalized_name = fields.Char(required=True, index=True)
    used_count = fields.Integer(default=1)
    last_used_at = fields.Datetime(default=fields.Datetime.now)
