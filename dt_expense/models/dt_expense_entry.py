# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DTExpenseEntry(models.Model):
    _name = "dt.expense.entry"
    _description = "DT Expense Entry"
    _order = "expense_date desc, id desc"
    _rec_name = "display_name"

    name = fields.Char(string="Tiêu đề")
    code = fields.Char(copy=False, index=True, default="New")
    display_name = fields.Char(compute="_compute_display_name")
    expense_date = fields.Date(required=True, default=fields.Date.context_today, index=True)
    category_id = fields.Many2one("dt.expense.category", required=True, ondelete="restrict", index=True)
    amount = fields.Monetary(required=True, currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", required=True, default=lambda self: self.env.company.currency_id)
    note = fields.Text()
    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, index=True)
    partner_id = fields.Many2one("res.partner", related="user_id.partner_id", store=True)
    active = fields.Boolean(default=True)
    expense_year = fields.Char(compute="_compute_date_parts", store=True, index=True)
    expense_month_key = fields.Char(compute="_compute_date_parts", store=True, index=True)
    expense_week_key = fields.Char(compute="_compute_date_parts", store=True, index=True)
    media_count = fields.Integer(compute="_compute_media_metrics")
    cover_media_id = fields.Many2one("dt.media", compute="_compute_media_metrics")

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if vals.get("code", "New") == "New":
                vals["code"] = seq.next_by_code("dt.expense.entry") or "DTEXP"
        return super().create(vals_list)

    @api.depends("name", "category_id", "expense_date")
    def _compute_display_name(self):
        for record in self:
            title = record.name or (record.category_id.name if record.category_id else "Chi tiêu")
            date_label = record.expense_date.strftime("%d/%m/%Y") if record.expense_date else ""
            record.display_name = f"{title} - {date_label}" if date_label else title

    @api.depends("expense_date")
    def _compute_date_parts(self):
        for record in self:
            if record.expense_date:
                iso_year, iso_week, _ = record.expense_date.isocalendar()
                record.expense_year = record.expense_date.strftime("%Y")
                record.expense_month_key = record.expense_date.strftime("%Y-%m")
                record.expense_week_key = f"{iso_year}-W{iso_week:02d}"
            else:
                record.expense_year = False
                record.expense_month_key = False
                record.expense_week_key = False

    def _compute_media_metrics(self):
        groups = defaultdict(list)
        if self.ids:
            media_rows = self.env["dt.media"].sudo().search([("res_model", "=", self._name), ("res_id", "in", self.ids)], order="is_cover desc, sequence, id")
            for media in media_rows:
                groups[media.res_id].append(media)
        for record in self:
            media_rows = groups.get(record.id, [])
            record.media_count = len(media_rows)
            record.cover_media_id = media_rows[0] if media_rows else False

    @api.constrains("amount")
    def _check_amount(self):
        for record in self:
            if record.amount < 0:
                raise ValidationError("Số tiền chi tiêu phải lớn hơn hoặc bằng 0.")

    def get_media_items(self):
        self.ensure_one()
        return self.env["dt.media"].sudo().search([("res_model", "=", self._name), ("res_id", "=", self.id)], order="is_cover desc, sequence, id")
