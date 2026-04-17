# -*- coding: utf-8 -*-
from odoo import api, fields, models


class DTMemoireAlbum(models.Model):
    _name = "dt.memoire.album"
    _description = "DT Album Kỷ Niệm"
    _order = "sequence, id"

    name = fields.Char(required=True)
    code = fields.Char(copy=False, index=True, default="New")
    description = fields.Text()
    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    diary_count = fields.Integer(compute="_compute_diary_count")

    @api.depends("name")
    def _compute_diary_count(self):
        groups = self.env["dt.memoire.diary"].read_group([("album_id", "in", self.ids)], ["album_id"], ["album_id"])
        mapped = {g["album_id"][0]: g["album_id_count"] for g in groups if g.get("album_id")}
        for album in self:
            album.diary_count = mapped.get(album.id, 0)

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if vals.get("code", "New") == "New":
                vals["code"] = seq.next_by_code("dt.memoire.album") or "DTALB"
        return super().create(vals_list)
