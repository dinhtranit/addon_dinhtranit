# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import date
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FamilyExpenseEntry(models.Model):
    _name = "dt.expense.entry"
    _description = "Family Expense Entry"
    _order = "expense_date desc, id desc"
    _rec_name = "display_name"

    name = fields.Char(string="Tiêu đề")
    code = fields.Char(copy=False, index=True, default="New")
    display_name = fields.Char(compute="_compute_display_name")
    expense_date = fields.Date(required=True, default=fields.Date.context_today, index=True)
    accounting_month = fields.Date(required=True, default=lambda self: self._default_accounting_month(), index=True)
    entry_type = fields.Selection([
        ("expense", "Chi tiêu"),
        ("income", "Thu nhập"),
        ("adjustment", "Điều chỉnh"),
    ], string="Loại giao dịch", required=True, default="expense", index=True)
    category_id = fields.Many2one("dt.expense.category", string="Danh mục", ondelete="restrict", index=True)
    amount = fields.Monetary(string="Số tiền", required=True, currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", string="Tiền tệ", required=True, default=lambda self: self._default_currency_id())
    adjustment_direction = fields.Selection([("increase", "Tăng số dư"), ("decrease", "Giảm số dư")], string="Hướng điều chỉnh", required=True, default="increase")
    note = fields.Text()
    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, index=True)
    partner_id = fields.Many2one("res.partner", related="user_id.partner_id", store=True)
    company_id = fields.Many2one("res.company", related="user_id.company_id", store=True, index=True)
    active = fields.Boolean(default=True)
    expense_year = fields.Char(compute="_compute_date_parts", store=True, index=True)
    expense_month_key = fields.Char(compute="_compute_date_parts", store=True, index=True)
    accounting_month_key = fields.Char(compute="_compute_date_parts", store=True, index=True)
    media_count = fields.Integer(compute="_compute_media_metrics")
    cover_media_id = fields.Many2one("dt.media", compute="_compute_media_metrics")
    signed_amount = fields.Monetary(compute="_compute_amount_helpers", currency_field="currency_id", string="Ảnh hưởng số dư")
    amount_label = fields.Char(compute="_compute_amount_helpers")
    amount_css_class = fields.Char(compute="_compute_amount_helpers")
    balance_effect = fields.Monetary(compute="_compute_amount_helpers", currency_field="currency_id")
    amount_display = fields.Char(compute="_compute_amount_helpers")

    @api.model
    def _default_currency_id(self):
        vnd = self.env.ref("base.VND", raise_if_not_found=False)
        return (vnd or self.env.company.currency_id).id

    @api.model
    def _default_accounting_month(self):
        today = fields.Date.context_today(self)
        return today.replace(day=1)

    @api.model
    def _normalize_month_start(self, value):
        if not value:
            value = fields.Date.context_today(self)
        if isinstance(value, str):
            value = fields.Date.from_string(value)
        return value.replace(day=1)

    @api.model
    def _apply_accounting_month_rule(self, vals):
        vals = dict(vals)
        expense_date = vals.get("expense_date") or fields.Date.context_today(self)
        if isinstance(expense_date, str):
            expense_date = fields.Date.from_string(expense_date)
        category = False
        category_id = vals.get("category_id")
        if category_id:
            category = self.env["dt.expense.category"].browse(category_id)
        accounting_month = vals.get("accounting_month")
        if accounting_month:
            vals["accounting_month"] = self._normalize_month_start(accounting_month)
            return vals
        month_value = expense_date.replace(day=1)
        if category and category.apply_next_month_rule and expense_date.day >= 28:
            if expense_date.month == 12:
                month_value = date(expense_date.year + 1, 1, 1)
            else:
                month_value = date(expense_date.year, expense_date.month + 1, 1)
        vals["accounting_month"] = month_value
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        default_currency_id = self._default_currency_id()
        normalized_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            if vals.get("code", "New") == "New":
                vals["code"] = seq.next_by_code("dt.expense.entry") or "FamilyEXP"
            vals.setdefault("entry_type", "expense")
            vals.setdefault("adjustment_direction", "increase")
            vals.setdefault("currency_id", default_currency_id)
            vals = self._apply_accounting_month_rule(vals)
            normalized_vals_list.append(vals)
        records = super().create(normalized_vals_list)
        records._track_title_history()
        return records

    def write(self, vals):
        vals = dict(vals)
        if vals.get("entry_type") and vals["entry_type"] != "adjustment":
            vals.setdefault("adjustment_direction", "increase")
        if any(key in vals for key in ("expense_date", "category_id", "accounting_month")):
            vals = self._apply_accounting_month_rule(vals)
        result = super().write(vals)
        self._track_title_history()
        return result

    @api.depends("name", "category_id", "expense_date", "entry_type")
    def _compute_display_name(self):
        labels = dict(self._fields["entry_type"].selection)
        for record in self:
            title = record.name or (record.category_id.name if record.category_id else labels.get(record.entry_type or "expense", "Giao dịch"))
            date_label = record.expense_date.strftime("%d/%m/%Y") if record.expense_date else ""
            record.display_name = f"{title} - {date_label}" if date_label else title

    @api.depends("expense_date", "accounting_month")
    def _compute_date_parts(self):
        for record in self:
            if record.expense_date:
                record.expense_year = record.expense_date.strftime("%Y")
                record.expense_month_key = record.expense_date.strftime("%Y-%m")
            else:
                record.expense_year = False
                record.expense_month_key = False
            record.accounting_month_key = record.accounting_month.strftime("%Y-%m") if record.accounting_month else False

    @api.depends("amount", "entry_type", "adjustment_direction", "currency_id")
    def _compute_amount_helpers(self):
        for record in self:
            effect = record.get_balance_effect()
            record.signed_amount = effect
            record.balance_effect = effect
            record.amount_label = record._format_money(effect, show_plus=True)
            record.amount_display = record.amount_label
            if effect < 0:
                record.amount_css_class = "dt-amount-negative"
            elif effect > 0:
                record.amount_css_class = "dt-amount-positive"
            else:
                record.amount_css_class = ""

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
        vnd = self.env.ref("base.VND", raise_if_not_found=False)
        for record in self:
            if record.amount < 0:
                raise ValidationError("Số tiền phải lớn hơn hoặc bằng 0.")
            if vnd and record.currency_id == vnd and record.amount != int(record.amount):
                raise ValidationError("Tiền VND không hỗ trợ số lẻ. Vui lòng nhập số nguyên.")

    @api.constrains("category_id", "entry_type")
    def _check_category_type(self):
        for record in self:
            entry_type = record.entry_type or "expense"
            if entry_type in ("expense", "income"):
                if not record.category_id:
                    raise ValidationError("Khoản chi và khoản thu phải có danh mục.")
                if record.category_id.category_type and record.category_id.category_type != entry_type:
                    raise ValidationError("Danh mục đã chọn không khớp với loại giao dịch.")
                if not record.category_id.is_leaf:
                    raise ValidationError("Chỉ được chọn danh mục lá khi tạo giao dịch.")
            elif record.category_id:
                raise ValidationError("Khoản điều chỉnh không sử dụng danh mục.")

    def _track_title_history(self):
        history_model = self.env["dt.expense.title.history"].sudo()
        for record in self:
            title = (record.name or "").strip()
            if not title or not record.category_id or record.entry_type == "adjustment":
                continue
            normalized = re.sub(r"\s+", " ", title.lower()).strip()
            history = history_model.search([
                ("user_id", "=", record.user_id.id),
                ("category_id", "=", record.category_id.id),
                ("normalized_name", "=", normalized),
            ], limit=1)
            vals = {
                "user_id": record.user_id.id,
                "category_id": record.category_id.id,
                "name": title,
                "normalized_name": normalized,
                "last_used_at": fields.Datetime.now(),
            }
            if history:
                vals["used_count"] = history.used_count + 1
                history.write(vals)
            else:
                vals["used_count"] = 1
                history_model.create(vals)

    def get_balance_effect(self):
        self.ensure_one()
        amount = float(self.amount or 0.0)
        entry_type = self.entry_type or "expense"
        if entry_type == "income":
            return amount
        if entry_type == "adjustment":
            return amount if (self.adjustment_direction or "increase") == "increase" else -amount
        return -amount

    @api.model
    def compute_current_balance(self, users=None):
        if users is None:
            users = self.env.user
        if isinstance(users, models.BaseModel):
            user_ids = users.ids
        elif isinstance(users, list):
            user_ids = users
        else:
            user_ids = [users.id]
        entries = self.search([("user_id", "in", user_ids)])
        return sum(entry.get_balance_effect() for entry in entries)

    @api.model
    def create_balance_adjustment(self, target_amount, user=None, note=""):
        user = user or self.env.user
        target_amount = int(round(target_amount or 0.0))
        current_balance = int(round(self.compute_current_balance(users=user)))
        delta = target_amount - current_balance
        if not delta:
            return False
        return self.create({
            "name": "Điều chỉnh số dư hiện tại",
            "expense_date": fields.Date.context_today(self),
            "entry_type": "adjustment",
            "adjustment_direction": "increase" if delta > 0 else "decrease",
            "amount": abs(delta),
            "user_id": user.id,
            "currency_id": self._default_currency_id(),
            "note": (note or "").strip() or f"Đặt số dư từ {self._format_money(current_balance)} về {self._format_money(target_amount)}.",
        })

    def get_media_items(self):
        self.ensure_one()
        return self.env["dt.media"].sudo().search([("res_model", "=", self._name), ("res_id", "=", self.id)], order="is_cover desc, sequence, id")

    def can_view(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        return user.can_view_expense_from(self.user_id)

    def get_icon(self):
        self.ensure_one()
        if self.category_id and self.category_id.icon:
            return self.category_id.icon
        return {"expense": "💸", "income": "💰", "adjustment": "⚖️"}.get(self.entry_type or "expense", "💸")

    def get_entry_icon(self):
        self.ensure_one()
        return self.get_icon()

    def get_entry_type_label(self):
        self.ensure_one()
        return dict(self._fields["entry_type"].selection).get(self.entry_type or "expense", "Giao dịch")

    @api.model
    def parse_money_text(self, raw_value):
        raw_value = (raw_value or "").strip()
        if not raw_value:
            return 0.0
        negative = raw_value.startswith("-")
        sanitized = raw_value.replace("₫", "").replace("đ", "").replace("Đ", "").replace("VND", "").replace("vnd", "").replace("VNĐ", "").replace("vnđ", "")
        digits = re.sub(r"\D+", "", sanitized)
        amount = int(digits or 0)
        return float(-amount if negative else amount)

    @api.model
    def _format_money(self, amount, show_plus=False):
        rounded = int(round(amount or 0.0))
        prefix = ""
        if rounded < 0:
            prefix = "-"
        elif show_plus and rounded > 0:
            prefix = "+"
        body = f"{abs(rounded):,}".replace(",", ".")
        return f"{prefix}{body} VNĐ"

    @api.model
    def format_amount_for_input(self, amount):
        rounded = int(round(amount or 0.0))
        prefix = "-" if rounded < 0 else ""
        body = f"{abs(rounded):,}".replace(",", ".")
        return prefix + body
