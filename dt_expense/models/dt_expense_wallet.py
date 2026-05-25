# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FamilyExpenseWallet(models.Model):
    _name = "dt.expense.wallet"
    _description = "Family Expense Money Source"
    _order = "sequence, id"
    _rec_name = "display_name"

    name = fields.Char(required=True, string="Tên nguồn tiền")
    code = fields.Char(copy=False, index=True, default="New")
    display_name = fields.Char(compute="_compute_display_name", store=True)
    icon = fields.Char(default="💳")
    sequence = fields.Integer(default=10)
    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, index=True, string="Chủ ví")
    partner_id = fields.Many2one("res.partner", related="user_id.partner_id", store=True)
    company_id = fields.Many2one("res.company", related="user_id.company_id", store=True, index=True)
    currency_id = fields.Many2one("res.currency", required=True, default=lambda self: self._default_currency_id())
    opening_balance = fields.Monetary(currency_field="currency_id", default=0.0, string="Số dư đầu kỳ")
    opening_date = fields.Date(default=fields.Date.context_today)
    note = fields.Char()
    active = fields.Boolean(default=True)
    entry_count = fields.Integer(compute="_compute_entry_count")
    balance = fields.Monetary(compute="_compute_balance", currency_field="currency_id")
    balance_label = fields.Char(compute="_compute_balance")

    @api.model
    def _default_currency_id(self):
        vnd = self.env.ref("base.VND", raise_if_not_found=False)
        return (vnd or self.env.company.currency_id).id

    @api.depends("name", "user_id")
    def _compute_display_name(self):
        for wallet in self:
            wallet.display_name = "%s · %s" % (wallet.name or "Nguồn tiền", wallet.user_id.name or "")

    @api.depends("name")
    def _compute_entry_count(self):
        groups = self.env["dt.expense.entry"].read_group([("wallet_id", "in", self.ids)], ["wallet_id"], ["wallet_id"])
        mapped = {group["wallet_id"][0]: group["wallet_id_count"] for group in groups if group.get("wallet_id")}
        for wallet in self:
            wallet.entry_count = mapped.get(wallet.id, 0)

    @api.depends("opening_balance", "user_id")
    def _compute_balance(self):
        entry_model = self.env["dt.expense.entry"].sudo()
        for wallet in self:
            entries = entry_model.search([("wallet_id", "=", wallet.id), ("active", "=", True)])
            balance = float(wallet.opening_balance or 0.0) + sum(entry.get_balance_effect() for entry in entries)
            wallet.balance = balance
            wallet.balance_label = entry_model._format_money(balance)

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if vals.get("code", "New") == "New":
                vals["code"] = seq.next_by_code("dt.expense.wallet") or "WALLET"
            vals.setdefault("user_id", self.env.user.id)
            vals.setdefault("currency_id", self._default_currency_id())
        return super().create(vals_list)

    @api.constrains("opening_balance")
    def _check_vnd_integer(self):
        vnd = self.env.ref("base.VND", raise_if_not_found=False)
        for wallet in self:
            if vnd and wallet.currency_id == vnd and wallet.opening_balance != int(wallet.opening_balance):
                raise ValidationError("Tiền VND không hỗ trợ số lẻ.")

    @api.model
    def get_default_wallet(self, user=None):
        user = user or self.env.user
        if isinstance(user, int):
            user = self.env["res.users"].sudo().browse(user)
        wallet = self.sudo().search([("user_id", "=", user.id), ("active", "=", True)], order="sequence, id", limit=1)
        if wallet:
            return wallet
        return self.sudo().create({
            "name": "Tiền mặt",
            "icon": "💵",
            "sequence": 1,
            "user_id": user.id,
            "currency_id": self._default_currency_id(),
        })

    @api.model
    def ensure_default_wallets_for_users(self, users=None):
        users = users or self.env["res.users"].sudo().search([("share", "=", False), ("active", "=", True)])
        for user in users:
            self.get_default_wallet(user)

    def can_manage(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        return bool(self.user_id == user or user.has_group("base.group_system"))
