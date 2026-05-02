# -*- coding: utf-8 -*-
import base64

from odoo import http
from odoo.http import request


class FamilyPortalCore(http.Controller):

    def _base_values(self, **extra):
        apps = request.env["dt.app"].sudo().search([("is_active", "=", True)], order="sequence, id")
        values = {
            "app_cards": apps,
            "current_user": request.env.user,
            "page_name": extra.get("page_name", "expenses"),
            "page_title": extra.get("page_title", "Family"),
            "page_subtitle": extra.get("page_subtitle", ""),
            "back_url": extra.get("back_url", ""),
        }
        values.update(extra)
        return values

    @http.route(["/my/apps", "/dt/apps"], type="http", auth="user", website=True)
    def apps_home(self, **kw):
        return request.redirect("/my/apps/expenses")

    @http.route("/my/profile", type="http", auth="user", website=True)
    def my_profile(self, **kw):
        user = request.env.user
        family_users = request.env["res.users"].sudo().search([
            ("id", "!=", user.id),
            ("share", "=", False),
            ("active", "=", True),
        ], order="name")
        access_map = {}
        for access in user.sudo().dt_family_access_ids:
            access_map[access.viewer_user_id.id] = access
        return request.render("dt_core.portal_profile", self._base_values(
            page_name="profile",
            page_title="Trang cá nhân",
            page_subtitle="Cập nhật hồ sơ, cấu hình gia đình và đăng xuất.",
            profile_partner=user.partner_id,
            family_users=family_users,
            access_map=access_map,
            back_url="/my/apps/expenses",
        ))

    @http.route("/my/profile/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def save_profile(self, name="", phone="", bio="", **kw):
        user = request.env.user
        partner = user.partner_id.sudo()
        clean_name = (name or "").strip() or user.name
        user.sudo().write({"name": clean_name})
        partner_vals = {
            "name": clean_name,
            "phone": (phone or "").strip(),
            "dt_bio": (bio or "").strip(),
        }
        avatar_file = request.httprequest.files.get("avatar_file")
        if avatar_file:
            content = avatar_file.read()
            if content:
                encoded = base64.b64encode(content)
                if "image_1920" in partner._fields:
                    partner_vals["image_1920"] = encoded
                elif "avatar_1920" in partner._fields:
                    partner_vals["avatar_1920"] = encoded
        partner.write(partner_vals)

        access_model = request.env["dt.family.access"].sudo()
        all_users = request.env["res.users"].sudo().search([("id", "!=", user.id), ("share", "=", False), ("active", "=", True)])
        existing = {acc.viewer_user_id.id: acc for acc in user.sudo().dt_family_access_ids}
        for other_user in all_users:
            allow_expense = request.params.get(f"family_expense_{other_user.id}") == "on"
            allow_memory = request.params.get(f"family_memory_{other_user.id}") == "on"
            access = existing.get(other_user.id)
            if allow_expense or allow_memory:
                vals = {
                    "owner_user_id": user.id,
                    "viewer_user_id": other_user.id,
                    "allow_expense": allow_expense,
                    "allow_memory": allow_memory,
                    "active": True,
                }
                if access:
                    access.write(vals)
                else:
                    access_model.create(vals)
            elif access:
                access.unlink()
        return request.redirect("/my/profile")

    @http.route("/my/profile/logout", type="http", auth="user", website=True)
    def profile_logout(self, **kw):
        request.session.logout()
        return request.redirect("/web/login")
