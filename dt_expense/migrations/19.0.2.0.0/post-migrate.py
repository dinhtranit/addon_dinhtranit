# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    hooks = __import__("odoo.addons.dt_expense.hooks", fromlist=["migrate_existing_data"])
    hooks.migrate_existing_data(cr, env.registry)
