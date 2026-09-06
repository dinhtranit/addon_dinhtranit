# -*- coding: utf-8 -*-
"""Grant the "Family Admin" group to the account that used to be hardcoded by
email inside dt.expense.category.can_manage(). Runs exactly once when dt_core
is updated to this version, on every database (staging, then production) -
after that the group membership lives in the database like any normal
permission and this script never runs again.
"""
from odoo import api, SUPERUSER_ID

FAMILY_ADMIN_LOGIN = "dinhtranit95@gmail.com"


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    group = env.ref("dt_core.group_family_admin", raise_if_not_found=False)
    user = env["res.users"].search([("login", "=", FAMILY_ADMIN_LOGIN)], limit=1)
    if group and user:
        user.write({"group_ids": [(4, group.id)]})
