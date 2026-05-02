# -*- coding: utf-8 -*-
from datetime import date

from odoo import SUPERUSER_ID, api


def _column_exists(cr, table_name, column_name):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = %s
           AND column_name = %s
        LIMIT 1
        """,
        (table_name, column_name),
    )
    return bool(cr.fetchone())


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if _column_exists(cr, "dt_expense_entry", "accounting_month"):
        cr.execute(
            """
            UPDATE dt_expense_entry
               SET accounting_month = date_trunc('month', COALESCE(accounting_month, expense_date, CURRENT_DATE))::date
             WHERE accounting_month IS NULL OR accounting_month <> date_trunc('month', accounting_month)::date
            """
        )
    if _column_exists(cr, "dt_expense_category", "user_id"):
        admin_id = env.ref("base.user_admin").id
        cr.execute("UPDATE dt_expense_category SET user_id = %s WHERE user_id IS NULL", (admin_id,))

    cr.execute("UPDATE res_currency SET symbol = %s WHERE name = %s", ("VNĐ", "VND"))
