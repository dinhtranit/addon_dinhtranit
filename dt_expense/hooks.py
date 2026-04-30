# -*- coding: utf-8 -*-
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

    if _column_exists(cr, "dt_expense_category", "scope"):
        cr.execute(
            """
            UPDATE dt_expense_category
               SET category_type = COALESCE(category_type, 'expense'),
                   scope = COALESCE(scope, CASE WHEN user_id IS NULL THEN 'shared' ELSE 'private' END)
            """
        )

    if _column_exists(cr, "dt_expense_category", "visibility_scope") and _column_exists(cr, "dt_expense_category", "scope"):
        cr.execute(
            """
            UPDATE dt_expense_category
               SET scope = COALESCE(scope, visibility_scope)
             WHERE visibility_scope IS NOT NULL
            """
        )

    if _column_exists(cr, "dt_expense_entry", "entry_type"):
        cr.execute(
            """
            UPDATE dt_expense_entry
               SET entry_type = COALESCE(entry_type, 'expense')
            """
        )

    if _column_exists(cr, "dt_expense_entry", "privacy"):
        cr.execute(
            """
            UPDATE dt_expense_entry
               SET privacy = COALESCE(privacy, 'private')
            """
        )
        cr.execute(
            """
            UPDATE dt_expense_entry
               SET privacy = 'public'
             WHERE privacy = 'family'
            """
        )

    if _column_exists(cr, "dt_expense_entry", "adjustment_direction"):
        cr.execute(
            """
            UPDATE dt_expense_entry
               SET adjustment_direction = COALESCE(adjustment_direction, 'increase')
            """
        )

    if _column_exists(cr, "dt_expense_entry", "adjustment_sign") and _column_exists(cr, "dt_expense_entry", "adjustment_direction"):
        cr.execute(
            """
            UPDATE dt_expense_entry
               SET adjustment_direction = CASE
                   WHEN adjustment_sign = 'minus' THEN 'decrease'
                   WHEN adjustment_sign = 'plus' THEN 'increase'
                   ELSE COALESCE(adjustment_direction, 'increase')
               END
             WHERE adjustment_sign IS NOT NULL
            """
        )

    categories = env["dt.expense.category"].sudo().search([])
    for category in categories:
        vals = {}
        if category.scope == "shared" and category.user_id:
            vals["user_id"] = False
        elif category.scope == "private" and not category.user_id:
            vals["scope"] = "shared"
        if vals:
            category.write(vals)
