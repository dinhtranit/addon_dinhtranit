# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    dt_member_code = fields.Char(string="Member Code", copy=False, index=True)
    dt_bio = fields.Text(string="Giới thiệu ngắn")

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("dt_member_code"):
                vals["dt_member_code"] = seq.next_by_code("dt.partner.member.code") or "/"
        return super().create(vals_list)
