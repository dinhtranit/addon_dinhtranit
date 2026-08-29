# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FamilyExpenseDebt(models.Model):
    _name = "dt.expense.debt"
    _description = "Family Debt"
    _order = "debt_date desc, id desc"
    _rec_name = "display_name"

    name = fields.Char(required=True, string="Ghi chú")
    code = fields.Char(copy=False, index=True, default="New")
    display_name = fields.Char(compute="_compute_display_name", store=True)
    debt_type = fields.Selection([
        ("lend", "Cho mượn"),
        ("borrow", "Mình mượn"),
    ], required=True, default="lend", index=True, string="Loại nợ")
    counterparty = fields.Char(required=True, string="Người liên quan")
    amount = fields.Monetary(required=True, currency_field="currency_id", string="Số tiền gốc")
    paid_amount = fields.Monetary(compute="_compute_paid_amount", store=True, currency_field="currency_id", string="Đã tất toán")
    remaining_amount = fields.Monetary(compute="_compute_paid_amount", store=True, currency_field="currency_id", string="Còn lại")
    currency_id = fields.Many2one("res.currency", required=True, default=lambda self: self._default_currency_id())
    wallet_id = fields.Many2one("dt.expense.wallet", required=True, ondelete="restrict", string="Nguồn tiền")
    debt_date = fields.Date(required=True, default=fields.Date.context_today, index=True, string="Ngày phát sinh")
    due_date = fields.Date(string="Hạn trả")
    note = fields.Text()
    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, index=True)
    partner_id = fields.Many2one("res.partner", related="user_id.partner_id", store=True)
    company_id = fields.Many2one("res.company", related="user_id.company_id", store=True, index=True)
    state = fields.Selection([
        ("open", "Đang mở"),
        ("paid", "Đã tất toán"),
        ("cancelled", "Đã hủy"),
    ], default="open", required=True, index=True)
    active = fields.Boolean(default=True)
    initial_entry_id = fields.Many2one("dt.expense.entry", ondelete="set null", copy=False, string="Giao dịch phát sinh")
    entry_ids = fields.One2many("dt.expense.entry", "debt_id", string="Giao dịch nợ")

    @api.model
    def _default_currency_id(self):
        vnd = self.env.ref("base.VND", raise_if_not_found=False)
        return (vnd or self.env.company.currency_id).id

    @api.depends("debt_type", "counterparty", "amount")
    def _compute_display_name(self):
        labels = {"lend": "Cho mượn", "borrow": "Mình mượn"}
        for debt in self:
            debt.display_name = "%s · %s · %s" % (
                labels.get(debt.debt_type, "Nợ"),
                debt.counterparty or "-",
                self.env["dt.expense.entry"]._format_money(debt.amount or 0.0),
            )

    @api.depends("entry_ids", "entry_ids.amount", "entry_ids.debt_flow", "entry_ids.active", "amount")
    def _compute_paid_amount(self):
        for debt in self:
            paid = 0.0
            for entry in debt.entry_ids.filtered(lambda e: e.active and e.id != debt.initial_entry_id.id):
                if debt.debt_type == "lend" and entry.debt_flow == "collect_lend":
                    paid += float(entry.amount or 0.0)
                elif debt.debt_type == "borrow" and entry.debt_flow == "repay_borrow":
                    paid += float(entry.amount or 0.0)
            debt.paid_amount = paid
            debt.remaining_amount = max(float(debt.amount or 0.0) - paid, 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        wallet_model = self.env["dt.expense.wallet"].sudo()
        for vals in vals_list:
            if vals.get("code", "New") == "New":
                vals["code"] = seq.next_by_code("dt.expense.debt") or "DEBT"
            vals.setdefault("user_id", self.env.user.id)
            vals.setdefault("currency_id", self._default_currency_id())
            if not vals.get("wallet_id"):
                vals["wallet_id"] = wallet_model.get_default_wallet(vals.get("user_id")).id
        debts = super().create(vals_list)
        for debt in debts:
            debt._sync_initial_entry()
        debts._track_counterparty_history()
        return debts

    def write(self, vals):
        result = super().write(vals)
        if any(key in vals for key in ("debt_type", "counterparty", "amount", "wallet_id", "debt_date", "note", "state", "active")):
            for debt in self:
                if debt.state == "cancelled" or not debt.active:
                    if debt.initial_entry_id:
                        debt.initial_entry_id.sudo().write({"active": False})
                else:
                    debt._sync_initial_entry()
        if "counterparty" in vals:
            self._track_counterparty_history()
        return result

    def _track_counterparty_history(self):
        contact_model = self.env["dt.expense.contact"].sudo()
        for debt in self:
            name = (debt.counterparty or "").strip()
            if not name or name == "Người liên quan":
                continue
            contact = contact_model.search([
                ("user_id", "=", debt.user_id.id),
                ("name", "=ilike", name),
            ], limit=1)
            if contact:
                contact.write({"last_used_at": fields.Datetime.now(), "used_count": contact.used_count + 1})
            else:
                contact_model.create({"user_id": debt.user_id.id, "name": name})

    @api.constrains("amount")
    def _check_amount(self):
        vnd = self.env.ref("base.VND", raise_if_not_found=False)
        for debt in self:
            if debt.amount <= 0:
                raise ValidationError("Số tiền nợ phải lớn hơn 0.")
            if vnd and debt.currency_id == vnd and debt.amount != int(debt.amount):
                raise ValidationError("Tiền VND không hỗ trợ số lẻ.")

    def _initial_flow(self):
        self.ensure_one()
        return "lend_out" if self.debt_type == "lend" else "borrow_in"

    def _sync_initial_entry(self):
        entry_model = self.env["dt.expense.entry"].sudo()
        for debt in self:
            if debt.state == "cancelled" or not debt.active:
                continue
            vals = {
                "name": debt.name or debt.counterparty,
                "entry_type": "debt",
                "debt_flow": debt._initial_flow(),
                "debt_id": debt.id,
                "wallet_id": debt.wallet_id.id,
                "amount": debt.amount,
                "currency_id": debt.currency_id.id,
                "expense_date": debt.debt_date,
                "accounting_month": debt.debt_date.replace(day=1),
                "user_id": debt.user_id.id,
                "category_id": False,
                "note": debt.note or debt.display_name,
                "active": True,
            }
            if debt.initial_entry_id:
                debt.initial_entry_id.write(vals)
            else:
                initial = entry_model.create(vals)
                debt.sudo().with_context(skip_debt_sync=True).write({"initial_entry_id": initial.id})

    def register_payment(self, amount, payment_date=None, wallet=None, note=""):
        self.ensure_one()
        amount = abs(float(amount or 0.0))
        if not amount:
            return False
        if amount > self.remaining_amount:
            amount = self.remaining_amount
        if not amount:
            return False
        wallet = wallet or self.wallet_id
        payment_date = payment_date or fields.Date.context_today(self)
        flow = "collect_lend" if self.debt_type == "lend" else "repay_borrow"
        entry = self.env["dt.expense.entry"].sudo().create({
            "name": note or ("Thu hồi nợ" if self.debt_type == "lend" else "Trả nợ"),
            "entry_type": "debt",
            "debt_flow": flow,
            "debt_id": self.id,
            "wallet_id": wallet.id,
            "amount": amount,
            "currency_id": self.currency_id.id,
            "expense_date": payment_date,
            "accounting_month": payment_date.replace(day=1),
            "user_id": self.user_id.id,
            "category_id": False,
            "note": note or self.display_name,
        })
        self.invalidate_recordset(["paid_amount", "remaining_amount"])
        self._compute_paid_amount()
        if self.remaining_amount <= 0:
            self.sudo().write({"state": "paid"})
        return entry

    def action_cancel(self):
        for debt in self:
            debt.sudo().write({"state": "cancelled", "active": False})
            debt.entry_ids.sudo().write({"active": False})
        return True

    def can_manage(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        return bool(self.user_id == user or user.has_group("base.group_system"))

    def get_debt_type_label(self):
        self.ensure_one()
        return dict(self._fields["debt_type"].selection).get(self.debt_type or "lend", "Nợ")

    def get_media_items(self):
        self.ensure_one()
        return self.env["dt.media"].sudo().search([("res_model", "=", self._name), ("res_id", "=", self.id)], order="is_cover desc, sequence, id")
