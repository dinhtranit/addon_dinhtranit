# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import date, datetime, timedelta
from calendar import monthrange

from odoo import fields, http
from odoo.http import request
from odoo.addons.portal.controllers.portal import pager as portal_pager


class DTExpensePortal(http.Controller):

    def _base_values(self, **extra):
        apps = request.env["dt.app"].sudo().search([("is_active", "=", True)], order="sequence, id")
        values = {"app_cards": apps, "page_name": extra.get("page_name", "expenses"), "page_title": extra.get("page_title", "DT Expense"), "page_subtitle": extra.get("page_subtitle", ""), "back_url": extra.get("back_url", "/my/apps")}
        values.update(extra)
        return values

    def _category_domain(self, user):
        return ["|", ("user_id", "=", False), ("user_id", "=", user.id)]

    def _parse_anchor_date(self, anchor_date):
        if anchor_date:
            try:
                return datetime.strptime(anchor_date, "%Y-%m-%d").date()
            except ValueError:
                return date.today()
        return date.today()

    def _compute_period_range(self, period, anchor):
        if period == "week":
            start = anchor - timedelta(days=anchor.weekday())
            end = start + timedelta(days=6)
            label = f"Tuần {start.strftime('%d/%m')} - {end.strftime('%d/%m/%Y')}"
        elif period == "year":
            start = anchor.replace(month=1, day=1)
            end = anchor.replace(month=12, day=31)
            label = f"Năm {anchor.year}"
        else:
            start = anchor.replace(day=1)
            end = anchor.replace(day=monthrange(anchor.year, anchor.month)[1])
            label = f"Tháng {anchor.month}/{anchor.year}"
            period = "month"
        return period, start, end, label

    def _format_money(self, amount, currency):
        symbol = currency.symbol or currency.name or ""
        return (f"{amount:,.0f} {symbol}" if currency.position == "after" else f"{symbol} {amount:,.0f}").strip()

    def _build_category_bars(self, entries, currency):
        totals = defaultdict(float)
        categories = {}
        for entry in entries:
            if not entry.category_id:
                continue
            totals[entry.category_id.id] += entry.amount
            categories[entry.category_id.id] = entry.category_id
        grand_total = sum(totals.values()) or 1.0
        rows = []
        for category_id, amount in sorted(totals.items(), key=lambda item: item[1], reverse=True):
            category = categories.get(category_id)
            rows.append({"label": f"{category.icon or '💸'} {category.name}", "amount_label": self._format_money(amount, currency), "ratio": round(amount / grand_total * 100, 1)})
        return rows

    def _build_trend_bars(self, entries, period, start, end, currency):
        bucket = defaultdict(float)
        if period == "year":
            cursor = start
            while cursor <= end:
                bucket[cursor.strftime("%Y-%m")] = 0.0
                cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
            for entry in entries:
                bucket[entry.expense_date.strftime("%Y-%m")] += entry.amount
            max_value = max(bucket.values()) if bucket else 0.0
            return [{"label": key[-2:] + "/" + key[:4], "amount_label": self._format_money(amount, currency), "ratio": round((amount / max_value) * 100, 1) if max_value else 0} for key, amount in bucket.items()]
        cursor = start
        while cursor <= end:
            bucket[cursor.isoformat()] = 0.0
            cursor += timedelta(days=1)
        for entry in entries:
            bucket[entry.expense_date.isoformat()] += entry.amount
        max_value = max(bucket.values()) if bucket else 0.0
        rows = []
        for key, amount in bucket.items():
            d = datetime.strptime(key, "%Y-%m-%d").date()
            rows.append({"label": d.strftime("%d/%m"), "amount_label": self._format_money(amount, currency), "ratio": round((amount / max_value) * 100, 1) if max_value else 0})
        return rows

    @http.route("/my/apps/expenses", type="http", auth="user", website=True)
    def expense_home(self, page=1, **kw):
        user = request.env.user
        Entry = request.env["dt.expense.entry"]
        per_page = 10
        total = Entry.search_count([("user_id", "=", user.id)])
        pager = portal_pager(url="/my/apps/expenses", total=total, page=page, step=per_page)
        recent_entries = Entry.search([("user_id", "=", user.id)], order="expense_date desc, id desc", limit=per_page, offset=pager["offset"])
        today = fields.Date.context_today(Entry)
        month_key = today.strftime("%Y-%m")
        month_entries = Entry.search([("user_id", "=", user.id), ("expense_month_key", "=", month_key)])
        today_entries = Entry.search([("user_id", "=", user.id), ("expense_date", "=", today)])
        currency = user.company_id.currency_id or request.env.company.currency_id
        return request.render("dt_expense.portal_expense_home", self._base_values(page_title="Chi tiêu hằng ngày", page_subtitle="Nhập nhanh khoản chi và xem tổng quan tháng.", recent_entries=recent_entries, pager=pager, total=total, month_total_label=self._format_money(sum(month_entries.mapped('amount')), currency), today_total_label=self._format_money(sum(today_entries.mapped('amount')), currency), today_count=len(today_entries), category_count=request.env["dt.expense.category"].search_count(self._category_domain(user)), currency=currency))

    @http.route("/my/apps/expenses/new", type="http", auth="user", website=True)
    def expense_new(self, **kw):
        return request.render("dt_expense.portal_expense_form", self._base_values(page_title="Thêm chi tiêu", page_subtitle="Ngày mặc định là hôm nay, có thể đổi nếu nhập bù.", entry=False, categories=request.env["dt.expense.category"].search(self._category_domain(request.env.user), order="sequence, id"), default_date=date.today().isoformat(), back_url="/my/apps/expenses"))

    @http.route("/my/apps/expenses/<int:entry_id>/edit", type="http", auth="user", website=True)
    def expense_edit(self, entry_id, **kw):
        entry = request.env["dt.expense.entry"].browse(entry_id)
        if not entry.exists() or entry.user_id != request.env.user:
            return request.redirect("/my/apps/expenses")
        return request.render("dt_expense.portal_expense_form", self._base_values(page_title="Sửa chi tiêu", page_subtitle="Cập nhật số tiền, loại và chứng từ đính kèm.", entry=entry, categories=request.env["dt.expense.category"].search(self._category_domain(request.env.user), order="sequence, id"), default_date=entry.expense_date.isoformat() if entry.expense_date else date.today().isoformat(), back_url="/my/apps/expenses"))

    @http.route("/my/apps/expenses/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_save(self, entry_id=None, name="", expense_date="", category_id=None, amount="0", note="", **kw):
        user = request.env.user
        vals = {"name": (name or "").strip(), "note": (note or "").strip(), "user_id": user.id}
        vals["expense_date"] = datetime.strptime(expense_date, "%Y-%m-%d").date() if expense_date else date.today()
        vals["category_id"] = int(category_id) if category_id else False
        vals["amount"] = float((amount or "0").replace(",", ""))
        Entry = request.env["dt.expense.entry"]
        if entry_id:
            entry = Entry.browse(int(entry_id))
            if not entry.exists() or entry.user_id != user:
                return request.redirect("/my/apps/expenses")
            entry.write(vals)
        else:
            entry = Entry.create(vals)
        request.env["dt.media"].sudo().create_from_uploads(request.httprequest.files.getlist("media_files"), entry, owner_user=user, mark_first_cover=True)
        return request.redirect("/my/apps/expenses")

    @http.route("/my/apps/expenses/<int:entry_id>/delete", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_delete(self, entry_id, **kw):
        entry = request.env["dt.expense.entry"].browse(entry_id)
        if entry.exists() and entry.user_id == request.env.user:
            request.env["dt.media"].sudo().search([("res_model", "=", entry._name), ("res_id", "=", entry.id)]).unlink()
            entry.unlink()
        return request.redirect("/my/apps/expenses")

    @http.route("/my/apps/expenses/media/<int:media_id>/delete", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_media_delete(self, media_id, entry_id=None, **kw):
        media = request.env["dt.media"].sudo().browse(media_id)
        if media.exists() and media.owner_user_id == request.env.user and media.res_model == "dt.expense.entry":
            entry = request.env[media.res_model].browse(media.res_id)
            if entry.exists() and entry.user_id == request.env.user:
                media.unlink()
                if entry_id:
                    return request.redirect(f"/my/apps/expenses/{int(entry_id)}/edit")
        return request.redirect("/my/apps/expenses")

    @http.route("/my/apps/expenses/categories", type="http", auth="user", website=True)
    def expense_categories(self, **kw):
        user = request.env.user
        return request.render("dt_expense.portal_expense_categories", self._base_values(page_title="Loại chi tiêu", page_subtitle="Có thể thêm icon emoji để nhìn nhanh trên điện thoại.", categories=request.env["dt.expense.category"].search(self._category_domain(user), order="sequence, id"), back_url="/my/apps/expenses"))

    @http.route("/my/apps/expenses/categories/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_categories_save(self, category_id=None, name="", icon="💸", sequence="10", note="", **kw):
        vals = {"name": (name or "").strip() or "Loại mới", "icon": (icon or "💸").strip() or "💸", "note": (note or "").strip(), "user_id": request.env.user.id, "sequence": int(sequence or 10)}
        Category = request.env["dt.expense.category"]
        if category_id:
            category = Category.browse(int(category_id))
            if category.exists() and (not category.user_id or category.user_id == request.env.user):
                category.write(vals)
        else:
            Category.create(vals)
        return request.redirect("/my/apps/expenses/categories")

    @http.route("/my/apps/expenses/reports", type="http", auth="user", website=True)
    def expense_reports(self, period="month", anchor_date="", category_id="", **kw):
        user = request.env.user
        categories = request.env["dt.expense.category"].search(self._category_domain(user), order="sequence, id")
        anchor = self._parse_anchor_date(anchor_date)
        period, start, end, label = self._compute_period_range(period, anchor)
        domain = [("user_id", "=", user.id), ("expense_date", ">=", start), ("expense_date", "<=", end)]
        selected_category = False
        if category_id:
            selected_category = request.env["dt.expense.category"].browse(int(category_id))
            if selected_category.exists():
                domain.append(("category_id", "=", selected_category.id))
        entries = request.env["dt.expense.entry"].search(domain, order="expense_date desc, id desc")
        currency = user.company_id.currency_id or request.env.company.currency_id
        total_amount = sum(entries.mapped("amount"))
        return request.render("dt_expense.portal_expense_reports", self._base_values(page_title="Báo cáo chi tiêu", page_subtitle=label, back_url="/my/apps/expenses", categories=categories, entries=entries, period=period, anchor_date=anchor.isoformat(), selected_category=selected_category, total_label=self._format_money(total_amount, currency), average_label=self._format_money(total_amount / len(entries), currency) if entries else self._format_money(0, currency), category_bars=self._build_category_bars(entries, currency), trend_bars=self._build_trend_bars(entries, period, start, end, currency)))
