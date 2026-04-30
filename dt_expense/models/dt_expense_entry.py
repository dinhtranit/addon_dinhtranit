# -*- coding: utf-8 -*-
from collections import defaultdict
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
    entry_type = fields.Selection(
        [
            ("expense", "Chi tiêu"),
            ("income", "Thu nhập"),
            ("adjustment", "Điều chỉnh"),
        ],
        string="Loại giao dịch",
        required=True,
        default="expense",
        index=True,
    )
    category_id = fields.Many2one("dt.expense.category", string="Danh mục", ondelete="restrict", index=True)
    amount = fields.Monetary(string="Số tiền", required=True, currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", string="Tiền tệ", required=True, default=lambda self: self._default_currency_id())
    privacy = fields.Selection(
        [
            ("private", "Riêng tư"),
            ("public", "Public trong gia đình / công ty"),
        ],
        string="Hiển thị",
        required=True,
        default="private",
        index=True,
    )
    adjustment_direction = fields.Selection(
        [("increase", "Tăng số dư"), ("decrease", "Giảm số dư")],
        string="Hướng điều chỉnh",
        required=True,
        default="increase",
    )
    note = fields.Text()
    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, index=True)
    partner_id = fields.Many2one("res.partner", related="user_id.partner_id", store=True)
    company_id = fields.Many2one("res.company", related="user_id.company_id", store=True, index=True)
    active = fields.Boolean(default=True)
    expense_year = fields.Char(compute="_compute_date_parts", store=True, index=True)
    expense_month_key = fields.Char(compute="_compute_date_parts", store=True, index=True)
    expense_week_key = fields.Char(compute="_compute_date_parts", store=True, index=True)
    media_count = fields.Integer(compute="_compute_media_metrics")
    cover_media_id = fields.Many2one("dt.media", compute="_compute_media_metrics")
    signed_amount = fields.Monetary(compute="_compute_amount_helpers", currency_field="currency_id", string="Ảnh hưởng số dư")
    amount_label = fields.Char(compute="_compute_amount_helpers")
    amount_css_class = fields.Char(compute="_compute_amount_helpers")
    # Backward compatible aliases from earlier drafts.
    balance_effect = fields.Monetary(compute="_compute_amount_helpers", currency_field="currency_id")
    amount_display = fields.Char(compute="_compute_amount_helpers")

    @api.model
    def _default_currency_id(self):
        vnd = self.env.ref("base.VND", raise_if_not_found=False)
        return (vnd or self.env.company.currency_id).id

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
            vals.setdefault("privacy", "private")
            vals.setdefault("adjustment_direction", "increase")
            vals.setdefault("currency_id", default_currency_id)
            normalized_vals_list.append(vals)
        records = super().create(normalized_vals_list)
        records._touch_title_history()
        return records

    def write(self, vals):
        vals = dict(vals)
        if vals.get("entry_type") and vals["entry_type"] != "adjustment":
            vals.setdefault("adjustment_direction", "increase")
        result = super().write(vals)
        self._touch_title_history()
        return result

    def _touch_title_history(self):
        suggestion_model = self.env["dt.expense.title.suggestion"]
        for record in self:
            if record.entry_type not in ("expense", "income") or not record.category_id:
                continue
            title = (record.name or "").strip()
            if not title:
                continue
            suggestion_model.touch_history(record.category_id, title, user=record.user_id)

    @api.depends("name", "category_id", "expense_date", "entry_type")
    def _compute_display_name(self):
        labels = dict(self._fields["entry_type"].selection)
        for record in self:
            title = record.name or (record.category_id.name if record.category_id else labels.get(record.entry_type or "expense", "Giao dịch"))
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
            media_rows = self.env["dt.media"].sudo().search([
                ("res_model", "=", self._name),
                ("res_id", "in", self.ids),
            ], order="is_cover desc, sequence, id")
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
            elif record.category_id:
                raise ValidationError("Khoản điều chỉnh không sử dụng danh mục.")

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
    def compute_current_balance(self, user=None):
        user = user or self.env.user
        entries = self.search([("user_id", "=", user.id)])
        return sum(entry.get_balance_effect() for entry in entries)

    @api.model
    def create_balance_adjustment(self, target_amount, user=None, note=""):
        user = user or self.env.user
        target_amount = int(round(target_amount or 0.0))
        current_balance = int(round(self.compute_current_balance(user=user)))
        delta = target_amount - current_balance
        if not delta:
            return False
        adjustment = self.create({
            "name": "Điều chỉnh số dư hiện tại",
            "expense_date": fields.Date.context_today(self),
            "entry_type": "adjustment",
            "adjustment_direction": "increase" if delta > 0 else "decrease",
            "amount": abs(delta),
            "privacy": "private",
            "user_id": user.id,
            "currency_id": self._default_currency_id(),
            "note": (note or "").strip() or (
                f"Đặt số dư từ {self._format_money(current_balance)} về {self._format_money(target_amount)}."
            ),
        })
        return adjustment


    def get_media_items(self):
        self.ensure_one()
        return self.env["dt.media"].sudo().search([
            ("res_model", "=", self._name),
            ("res_id", "=", self.id),
        ], order="is_cover desc, sequence, id")

    def can_view(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        if self.user_id == user:
            return True
        return bool(
            (self.privacy or "private") == "public"
            and self.company_id
            and user.company_id
            and self.company_id == user.company_id
        )

    def get_icon(self):
        self.ensure_one()
        if self.category_id and self.category_id.icon:
            return self.category_id.icon
        return {
            "expense": "💸",
            "income": "💰",
            "adjustment": "⚖️",
        }.get(self.entry_type or "expense", "💸")

    def get_entry_icon(self):
        self.ensure_one()
        return self.get_icon()

    def get_entry_type_label(self):
        self.ensure_one()
        return dict(self._fields["entry_type"].selection).get(self.entry_type or "expense", "Giao dịch")

    def get_privacy_label(self):
        self.ensure_one()
        return dict(self._fields["privacy"].selection).get(self.privacy or "private", "Riêng tư")

    @api.model
    def parse_money_text(self, raw_value):
        raw_value = (raw_value or "").strip()
        if not raw_value:
            return 0.0
        negative = raw_value.startswith("-")
        sanitized = raw_value.replace("₫", "").replace("đ", "").replace("VND", "").replace("vnd", "")
        digits = re.sub(r"\D+", "", sanitized)
        amount = int(digits or 0)
        return float(-amount if negative else amount)

    @api.model
    def parse_money_value(self, raw_value):
        return self.parse_money_text(raw_value)

    @api.model
    def _format_money(self, amount, show_plus=False):
        rounded = int(round(amount or 0.0))
        prefix = ""
        if rounded < 0:
            prefix = "-"
        elif show_plus and rounded > 0:
            prefix = "+"
        body = f"{abs(rounded):,}".replace(",", ".")
        return f"{prefix}{body} đ"

    @api.model
    def format_vnd_amount(self, amount, signed=False):
        return self._format_money(amount, show_plus=signed)

    @api.model
    def format_amount_for_input(self, amount):
        rounded = int(round(amount or 0.0))
        prefix = "-" if rounded < 0 else ""
        body = f"{abs(rounded):,}".replace(",", ".")
        return prefix + body

    @api.model
    def format_money_input(self, amount):
        return self.format_amount_for_input(amount)
