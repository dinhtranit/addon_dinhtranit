# -*- coding: utf-8 -*-
from datetime import date, datetime

from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import pager as portal_pager


class FamilyMemoirePortal(http.Controller):

    def _base_values(self, **extra):
        values = {
            "page_name": extra.get("page_name", "memories"),
            "page_title": extra.get("page_title", "Mái ấm của mình"),
            "page_subtitle": extra.get("page_subtitle", ""),
            "back_url": extra.get("back_url", "/my/apps/expenses"),
        }
        values.update(extra)
        return values

    def _timeline_domain(self, user, mine=False, search="", category=""):
        visible_user_ids = [user.id] if mine else user.get_visible_memory_user_ids()
        domain = [("active", "=", True), ("user_id", "in", visible_user_ids)]
        if search:
            domain += [("title", "ilike", search)]
        if category:
            domain += [("category", "=", category)]
        return domain

    def _form_values(self, diary=False):
        user = request.env.user
        diary = diary.sudo() if diary else False
        return self._base_values(
            page_title="Tạo kỷ niệm" if not diary else "Sửa kỷ niệm",
            page_subtitle="Ghi lại một khoảnh khắc",
            diary=diary,
            tags=request.env["dt.memoire.tag"].sudo().search([]),
            albums=request.env["dt.memoire.album"].sudo().search([("user_id", "=", user.id)], order="sequence, name"),
            family_viewers=user.get_family_memory_viewers(),
            default_date=(diary.memory_date.isoformat() if diary and diary.memory_date else date.today().isoformat()),
            back_url=("/my/apps/memories/%s" % diary.id) if diary else "/my/apps/memories",
        )

    @http.route(["/my/apps/memories", "/my/memories"], type="http", auth="user", website=True)
    def memories_feed(self, page=1, search="", category="", mine="", **kw):
        user = request.env.user
        per_page = 10
        mine_bool = mine in ("1", "true", "True")
        domain = self._timeline_domain(user, mine=mine_bool, search=search, category=category)
        Diary = request.env["dt.memoire.diary"].sudo()
        visible_diaries = Diary.search(domain, order="is_pinned desc, memory_date desc, id desc").filtered(lambda diary: diary.can_view(user))
        total = len(visible_diaries)
        pager = portal_pager(url="/my/apps/memories", total=total, page=page, step=per_page, url_args={"search": search, "category": category, "mine": "1" if mine_bool else ""})
        diaries = visible_diaries[pager["offset"]:pager["offset"] + per_page]
        return request.render("dt_memoire.portal_memories_feed", self._base_values(
            page_title="Lưu giữ kỷ niệm", show_bottom_nav=True,
            page_subtitle="Nhật ký gia đình",
            diaries=diaries,
            pager=pager,
            total=total,
            search=search,
            category=category,
            mine=mine_bool,
            categories=[("family", "Gia đình"), ("travel", "Du lịch"), ("birthday", "Sinh nhật"), ("daily", "Hằng ngày"), ("school", "Học tập"), ("other", "Khác")],
            back_url="/my/apps/expenses",
        ))

    @http.route("/my/apps/memories/mine", type="http", auth="user", website=True)
    def memories_mine(self, **kw):
        return request.redirect("/my/apps/memories?mine=1")

    @http.route("/my/apps/memories/<int:diary_id>", type="http", auth="user", website=True)
    def memory_detail(self, diary_id, **kw):
        diary = request.env["dt.memoire.diary"].sudo().browse(diary_id)
        if not diary.exists() or not diary.can_view(request.env.user):
            return request.redirect("/my/apps/memories")
        diary.write({"view_count": diary.view_count + 1})
        return request.render("dt_memoire.portal_memory_detail", self._base_values(page_title=diary.title, page_subtitle=diary.memory_date.strftime("%d/%m/%Y") if diary.memory_date else "", diary=diary, back_url="/my/apps/memories"))

    @http.route("/my/apps/memories/new", type="http", auth="user", website=True)
    def memory_new(self, **kw):
        return request.render("dt_memoire.portal_memory_form", self._form_values(False))

    @http.route("/my/apps/memories/<int:diary_id>/edit", type="http", auth="user", website=True)
    def memory_edit(self, diary_id, **kw):
        diary = request.env["dt.memoire.diary"].sudo().browse(diary_id)
        if not diary.exists() or diary.user_id.id != request.env.user.id:
            return request.redirect("/my/apps/memories")
        return request.render("dt_memoire.portal_memory_form", self._form_values(diary))

    @http.route("/my/apps/memories/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def memory_save(self, diary_id=None, title="", story="", memory_date="", location="", emotion="joyful", category="daily", private_only="", album_id=None, **kw):
        user = request.env.user
        privacy = "private" if private_only == "on" else "family"
        vals = {
            "title": (title or "").strip() or "Kỷ niệm mới",
            "story": story or "",
            "location": (location or "").strip(),
            "emotion": emotion,
            "category": category,
            "privacy": privacy,
            "shared_partner_ids": [(6, 0, [])],
            "user_id": user.id,
        }
        if memory_date:
            try:
                vals["memory_date"] = datetime.strptime(memory_date, "%Y-%m-%d").date()
            except ValueError:
                pass
        vals["album_id"] = int(album_id) if album_id and album_id != "0" else False
        tag_ids = request.httprequest.form.getlist("tag_ids")
        vals["tag_ids"] = [(6, 0, [int(tag_id) for tag_id in tag_ids if tag_id])] if tag_ids else [(6, 0, [])]
        Diary = request.env["dt.memoire.diary"].sudo()
        if diary_id:
            diary = Diary.browse(int(diary_id))
            if not diary.exists() or diary.user_id.id != user.id:
                return request.redirect("/my/apps/memories")
            diary.write(vals)
        else:
            diary = Diary.create(vals)
        request.env["dt.media"].sudo().create_from_uploads(request.httprequest.files.getlist("media_files"), diary, owner_user=user, mark_first_cover=True)
        return request.redirect(f"/my/apps/memories/{diary.id}")

    @http.route("/my/apps/memories/<int:diary_id>/delete", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def memory_delete(self, diary_id, **kw):
        diary = request.env["dt.memoire.diary"].sudo().browse(diary_id)
        if diary.exists() and diary.user_id.id == request.env.user.id:
            request.env["dt.media"].sudo().search([("res_model", "=", diary._name), ("res_id", "=", diary.id)]).unlink()
            diary.unlink()
        return request.redirect("/my/apps/memories")

    @http.route("/my/apps/memories/media/<int:media_id>/delete", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def memory_media_delete(self, media_id, diary_id=None, **kw):
        media = request.env["dt.media"].sudo().browse(media_id)
        if media.exists() and media.owner_user_id.id == request.env.user.id and media.res_model == "dt.memoire.diary":
            diary = request.env[media.res_model].sudo().browse(media.res_id)
            if diary.exists() and diary.user_id.id == request.env.user.id:
                media.unlink()
                if diary_id:
                    return request.redirect(f"/my/apps/memories/{int(diary_id)}/edit")
        return request.redirect("/my/apps/memories")
