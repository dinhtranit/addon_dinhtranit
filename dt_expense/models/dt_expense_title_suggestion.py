# -*- coding: utf-8 -*-
from odoo import fields, models


class FamilyExpenseTitleSuggestion(models.Model):
    _name = "dt.expense.title.suggestion"
    _description = "Expense Title Suggestion"
    _order = "sequence, id"

    category_id = fields.Many2one("dt.expense.category", required=True, ondelete="cascade", index=True)
    name = fields.Char(required=True, string="Tiêu đề gợi ý")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    user_id = fields.Many2one(related="category_id.user_id", store=True)
