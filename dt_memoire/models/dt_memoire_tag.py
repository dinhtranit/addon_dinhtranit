# -*- coding: utf-8 -*-
from odoo import fields, models


class DTMemoireTag(models.Model):
    _name = "dt.memoire.tag"
    _description = "DT Memoire Tag"
    _order = "name"

    name = fields.Char(required=True)
    color = fields.Integer(default=0)
