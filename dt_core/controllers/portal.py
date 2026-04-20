# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class FamilyPortalCore(http.Controller):

    def _base_values(self, **extra):
        apps = request.env["dt.app"].sudo().search([("is_active", "=", True)], order="sequence, id")
        values = {
            "app_cards": apps,
            "current_user": request.env.user,
            "page_name": extra.get("page_name", "apps"),
            "page_title": extra.get("page_title", "Family Apps"),
            "page_subtitle": extra.get("page_subtitle", ""),
            "back_url": extra.get("back_url", ""),
        }
        values.update(extra)
        return values

    @http.route(["/my/apps", "/dt/apps"], type="http", auth="user", website=True)
    def apps_home(self, **kw):
        return request.render("dt_core.portal_apps_home", self._base_values(
            page_name="apps",
            page_title="Family Apps",
            page_subtitle="Chọn app để vào đúng chức năng trên điện thoại.",
        ))

    @http.route("/my/profile", type="http", auth="user", website=True)
    def my_profile(self, **kw):
        user = request.env.user
        return request.render("dt_core.portal_profile", self._base_values(
            page_name="profile",
            page_title="Trang cá nhân",
            page_subtitle="Cập nhật nhanh thông tin cá nhân và mã thành viên.",
            profile_partner=user.partner_id,
            back_url="/my/apps",
        ))

    @http.route("/my/profile/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def save_profile(self, name="", phone="", bio="", **kw):
        user = request.env.user
        clean_name = (name or "").strip() or user.name
        user.sudo().write({"name": clean_name})
        user.partner_id.sudo().write({
            "name": clean_name,
            "phone": (phone or "").strip(),
            "dt_bio": (bio or "").strip(),
        })
        return request.redirect("/my/profile")
