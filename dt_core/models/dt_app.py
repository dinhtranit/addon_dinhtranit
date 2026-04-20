# -*- coding: utf-8 -*-
from odoo import fields, models


class FamilyApp(models.Model):
    _name = "dt.app"
    _description = "Family Portal App"
    _order = "sequence, id"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    route = fields.Char(required=True)
    icon = fields.Char(default="📱")
    description = fields.Text()
    sequence = fields.Integer(default=10)
    is_active = fields.Boolean(default=True)
    badge = fields.Char()
