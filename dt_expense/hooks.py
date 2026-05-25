# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", (table,))
    return bool(cr.fetchone()[0])


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s",
        (table, column),
    )
    return bool(cr.fetchone())


def _set_vnd_symbol(env):
    vnd = env.ref("base.VND", raise_if_not_found=False)
    if vnd and vnd.symbol != "đ":
        vnd.sudo().write({"symbol": "đ"})


def _normalize_accounting_month(cr):
    if not _table_exists(cr, "dt_expense_entry") or not _column_exists(cr, "dt_expense_entry", "accounting_month"):
        return
    cr.execute("""
        UPDATE dt_expense_entry
           SET accounting_month = date_trunc('month', COALESCE(accounting_month, expense_date, CURRENT_DATE))::date
         WHERE accounting_month IS NULL OR accounting_month <> date_trunc('month', accounting_month)::date
    """)


def _backfill_wallets(cr, env):
    if not _table_exists(cr, "dt_expense_entry") or not _column_exists(cr, "dt_expense_entry", "wallet_id"):
        return
    users = env["res.users"].sudo().search([("share", "=", False), ("active", "=", True)])
    cr.execute("SELECT DISTINCT user_id FROM dt_expense_entry WHERE user_id IS NOT NULL")
    entry_user_ids = [row[0] for row in cr.fetchall()]
    users |= env["res.users"].sudo().browse(entry_user_ids).exists()
    wallet_model = env["dt.expense.wallet"].sudo()
    for user in users:
        wallet = wallet_model.get_default_wallet(user)
        cr.execute(
            "UPDATE dt_expense_entry SET wallet_id=%s WHERE wallet_id IS NULL AND user_id=%s",
            (wallet.id, user.id),
        )


def _backfill_category_owner(cr, env):
    if not _table_exists(cr, "dt_expense_category") or not _column_exists(cr, "dt_expense_category", "user_id"):
        return
    admin = env.ref("base.user_admin", raise_if_not_found=False) or env.user
    cr.execute("UPDATE dt_expense_category SET user_id=%s WHERE user_id IS NULL", (admin.id,))


def migrate_existing_data(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _set_vnd_symbol(env)
    _backfill_category_owner(cr, env)
    _normalize_accounting_month(cr)
    _backfill_wallets(cr, env)


def post_init_hook(env_or_cr, registry=None):
    if registry is None:
        env = env_or_cr
    else:
        env = api.Environment(env_or_cr, SUPERUSER_ID, {})
    _set_vnd_symbol(env)
    env["dt.expense.wallet"].sudo().ensure_default_wallets_for_users()
    cr = env.cr
    _backfill_wallets(cr, env)
