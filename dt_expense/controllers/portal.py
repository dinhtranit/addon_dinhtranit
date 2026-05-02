# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import date, datetime
import json

from odoo import fields, http
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.http import request


class FamilyExpensePortal(http.Controller):

    def _base_values(self, **extra):
        values = {
            "page_name": extra.get("page_name", "expenses"),
            "page_title": extra.get("page_title", "Tài chính"),
            "page_subtitle": extra.get("page_subtitle", ""),
            "back_url": extra.get("back_url", "/my/apps/expenses"),
        }
        values.update(extra)
        return values

    def _entry_model(self):
        return request.env["dt.expense.entry"]

    def _category_model(self):
        return request.env["dt.expense.category"]

    def _suggestion_model(self):
        return request.env["dt.expense.title.suggestion"]

    def _history_model(self):
        return request.env["dt.expense.title.history"]

    def _safe_int(self, value, default=None):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _parse_date(self, value, default=None):
        if not value:
            return default
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return default

    def _normalize_month_start(self, value):
        dt = self._parse_date(value, date.today()) if isinstance(value, str) else value
        return dt.replace(day=1)

    def _format_money(self, amount, show_plus=False):
        return self._entry_model()._format_money(amount, show_plus=show_plus)

    def _format_input_money(self, amount):
        return self._entry_model().format_amount_for_input(amount)

    def _parse_money(self, value):
        return self._entry_model().parse_money_text(value)

    def _build_simple_pager(self, pager):
        if not pager:
            return {"pages": [], "prev_url": False, "next_url": False, "page_count": 0, "page": 1}
        if type(pager)== list:
            pager = pager[0]
        page_count = int(pager.get("page_count", 0) or 0)
        page = pager.get("page")
        page_num = int(page.get("num") or 1)
        url = pager.get("url") or ""
        def build_url(target_page):
            args = dict(pager.get("url_args") or {})
            args["page"] = target_page
            query = "&".join(f"{key}={value}" for key, value in args.items() if value not in (False, None, ""))
            return f"{url}?{query}" if query else url
        start = max(1, page_num - 2)
        end = min(page_count, start + 4)
        start = max(1, end - 4)
        pages = [{"number": num, "url": build_url(num), "is_current": num == page_num} for num in range(start, end + 1)]
        return {
            "pages": pages,
            "prev_url": build_url(page_num - 1) if page_num > 1 else False,
            "next_url": build_url(page_num + 1) if page_num < page_count else False,
            "page_count": page_count,
            "page": page_num,
        }

    def _category_domain(self, user, category_type=None, parent_only=False, leaf_only=False):
        admin_user = request.env.ref("base.user_admin")
        domain = [("user_id", "in", [user.id, admin_user.id]), ("active", "=", True)]
        if category_type:
            domain.append(("category_type", "=", category_type))
        if parent_only:
            domain.append(("parent_id", "=", False))
        if leaf_only:
            domain.append(("is_leaf", "=", True))
        return domain

    def _visible_user_ids(self, user, scope="mine"):
        return user.get_visible_expense_user_ids() if scope == "family" else [user.id]

    def _activity_domain(self, user, scope="mine", search="", member_id=None, date_from=None, date_to=None, entry_type=None, parent_id=None, category_id=None):
        domain = [("user_id", "in", self._visible_user_ids(user, scope))]
        if member_id:
            domain.append(("user_id", "=", member_id))
        if date_from:
            domain.append(("expense_date", ">=", date_from))
        if date_to:
            domain.append(("expense_date", "<=", date_to))
        if entry_type in ("expense", "income", "adjustment"):
            domain.append(("entry_type", "=", entry_type))
        if category_id:
            domain.append(("category_id", "=", category_id))
        elif parent_id:
            child_ids = self._category_model().search([("parent_id", "=", parent_id)]).ids
            domain.append(("category_id", "in", child_ids or [parent_id]))
        if search:
            domain += ["|", "|", "|", ("name", "ilike", search), ("note", "ilike", search), ("category_id.name", "ilike", search), ("user_id.name", "ilike", search)]
        return domain

    def _home_summary(self, user):
        entry_model = self._entry_model()
        today = fields.Date.context_today(entry_model)
        month_key = today.strftime("%Y-%m")
        my_entries = entry_model.search([("user_id", "=", user.id)], order="expense_date desc, id desc")
        month_entries = my_entries.filtered(lambda entry: entry.accounting_month_key == month_key)
        today_entries = my_entries.filtered(lambda entry: entry.expense_date == today)
        month_income_total = sum(abs(entry.amount or 0.0) for entry in month_entries if entry.entry_type == "income")
        month_expense_total = sum(abs(entry.amount or 0.0) for entry in month_entries if entry.entry_type == "expense")
        month_net_total = sum(entry.get_balance_effect() for entry in month_entries)
        current_balance = sum(entry.get_balance_effect() for entry in my_entries)
        return {
            "current_balance": current_balance,
            "current_balance_label": self._format_money(current_balance),
            "current_balance_input": self._format_input_money(current_balance),
            "month_income_label": self._format_money(month_income_total),
            "month_expense_label": self._format_money(month_expense_total),
            "month_net_label": self._format_money(month_net_total, show_plus=True),
            "today_count": len(today_entries),
        }

    def _entry_form_values(self, entry=False, active_tab="expense"):
        user = request.env.user
        entry = entry.sudo() if entry else False
        current_type = entry.entry_type if entry else active_tab
        categories = self._category_model().search(self._category_domain(user, leaf_only=True), order="category_type, sequence, id")
        categories_by_type = {
            "expense": categories.filtered(lambda c: c.category_type == "expense"),
            "income": categories.filtered(lambda c: c.category_type == "income"),
        }
        page_title = "Tạo giao dịch"
        if entry:
            page_title = "Sửa giao dịch"
        return self._base_values(
            page_title=page_title,
            page_subtitle="",
            entry=entry,
            active_tab=current_type,
            categories=categories,
            categories_by_type=categories_by_type,
            default_date=(entry.expense_date.isoformat() if entry and entry.expense_date else date.today().isoformat()),
            default_accounting_month=(entry.accounting_month.isoformat() if entry and entry.accounting_month else date.today().replace(day=1).isoformat()),
            amount_input_value=(self._format_input_money(entry.amount) if entry else ""),
            back_url="/my/apps/expenses",
        )

    def _build_statistics(self, entries, group_mode="parent"):
        totals = defaultdict(float)
        labels = {}
        income_total = expense_total = 0.0
        for entry in entries:
            if entry.entry_type == "income":
                income_total += abs(entry.amount or 0.0)
            elif entry.entry_type == "expense":
                expense_total += abs(entry.amount or 0.0)
            if not entry.category_id:
                continue
            bucket = entry.category_id.parent_id if (group_mode == "parent" and entry.category_id.parent_id) else entry.category_id
            totals[bucket.id] += abs(entry.amount or 0.0)
            labels[bucket.id] = f"{bucket.icon or '💸'} {bucket.name}"
        total_amount = sum(totals.values()) or 1.0
        colors = ["#4f46e5", "#06b6d4", "#22c55e", "#f59e0b", "#ef4444", "#a855f7", "#14b8a6", "#64748b"]
        angle = 0.0
        segments = []
        rows = []
        for idx, (bucket_id, amount) in enumerate(sorted(totals.items(), key=lambda item: item[1], reverse=True)):
            ratio = amount / total_amount
            next_angle = angle + ratio * 360.0
            color = colors[idx % len(colors)]
            segments.append(f"{color} {angle:.2f}deg {next_angle:.2f}deg")
            rows.append({"label": labels[bucket_id], "amount": self._format_money(amount), "ratio": round(ratio * 100, 1), "color": color})
            angle = next_angle
        return {
            "pie_style": "background: conic-gradient(%s);" % (", ".join(segments) if segments else "#e5e7eb 0deg 360deg"),
            "rows": rows,
            "income_total": self._format_money(income_total),
            "expense_total": self._format_money(expense_total),
            "net_total": self._format_money(income_total - expense_total, show_plus=True),
        }

    @http.route("/my/apps/expenses", type="http", auth="user", website=True)
    def expense_home(self, page=1, **kw):
        user = request.env.user
        entry_model = self._entry_model()
        per_page = 8
        domain = [("user_id", "=", user.id)]
        total = entry_model.search_count(domain)
        pager = portal_pager(url="/my/apps/expenses", total=total, page=page, step=per_page)
        recent_entries = entry_model.search(domain, order="expense_date desc, id desc", limit=per_page, offset=pager["offset"])
        summary = self._home_summary(user)
        values = self._base_values(page_title="Tài chính", page_subtitle="", recent_entries=recent_entries, pager=pager, total=total)
        values.update(summary)
        return request.render("dt_expense.portal_expense_home", values)

    @http.route("/my/apps/expenses/new", type="http", auth="user", website=True)
    def expense_new(self, entry_type="expense", **kw):
        active_tab = entry_type if entry_type in ("expense", "income", "adjustment") else "expense"
        return request.render("dt_expense.portal_expense_form", self._entry_form_values(entry=False, active_tab=active_tab))

    @http.route("/my/apps/expenses/<int:entry_id>/edit", type="http", auth="user", website=True)
    def expense_edit(self, entry_id, **kw):
        entry = self._entry_model().browse(entry_id)
        if not entry.exists() or entry.user_id != request.env.user:
            return request.redirect("/my/apps/expenses/history")
        return request.render("dt_expense.portal_expense_form", self._entry_form_values(entry=entry))

    @http.route("/my/apps/expenses/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_save(self, entry_id=None, entry_type="expense", adjustment_direction="increase", name="", expense_date="", accounting_month="", category_id=None, amount="0", note="", **kw):
        user = request.env.user
        entry_model = self._entry_model()
        entry_type = entry_type if entry_type in ("expense", "income", "adjustment") else "expense"
        vals = {
            "name": (name or "").strip(),
            "note": (note or "").strip(),
            "user_id": user.id,
            "entry_type": entry_type,
            "adjustment_direction": adjustment_direction if adjustment_direction in ("increase", "decrease") else "increase",
            "amount": abs(self._parse_money(amount)),
            "currency_id": entry_model._default_currency_id(),
            "expense_date": self._parse_date(expense_date, date.today()),
            "accounting_month": self._normalize_month_start(accounting_month or expense_date or date.today().isoformat()),
        }
        if entry_type == "adjustment":
            vals["category_id"] = False
        else:
            category = self._category_model().browse(self._safe_int(category_id)) if category_id else self._category_model().browse()
            admin_user = request.env.ref("base.user_admin")
            if not category.exists() or category.user_id.id not in [user.id, admin_user.id] or category.category_type != entry_type or not category.is_leaf:
                return request.redirect("/my/apps/expenses/new")
            vals["category_id"] = category.id
        if entry_id:
            entry = entry_model.browse(self._safe_int(entry_id))
            if not entry.exists() or entry.user_id != user:
                return request.redirect("/my/apps/expenses/history")
            entry.write(vals)
        else:
            entry = entry_model.create(vals)
        request.env["dt.media"].sudo().create_from_uploads(request.httprequest.files.getlist("media_files"), entry, owner_user=user, mark_first_cover=True)
        return request.redirect("/my/apps/expenses/history")

    @http.route("/my/apps/expenses/balance/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_balance_save(self, current_amount="0", **kw):
        self._entry_model().create_balance_adjustment(self._parse_money(current_amount), user=request.env.user)
        return request.redirect("/my/apps/expenses")

    @http.route("/my/apps/expenses/<int:entry_id>/delete", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_delete(self, entry_id, **kw):
        entry = self._entry_model().browse(entry_id)
        if entry.exists() and entry.user_id == request.env.user:
            request.env["dt.media"].sudo().search([("res_model", "=", entry._name), ("res_id", "=", entry.id)]).unlink()
            entry.unlink()
        return request.redirect("/my/apps/expenses/history")

    @http.route("/my/apps/expenses/categories", type="http", auth="user", website=True)
    def expense_categories(self, **kw):
        user = request.env.user
        categories = self._category_model().search(self._category_domain(user), order="category_type, sequence, id")
        roots_expense = categories.filtered(lambda c: c.category_type == "expense" and not c.parent_id)
        roots_income = categories.filtered(lambda c: c.category_type == "income" and not c.parent_id)
        return request.render("dt_expense.portal_expense_categories", self._base_values(page_title="Danh mục", page_subtitle="Quản lý danh mục cha/con và gợi ý tiêu đề nhập nhanh.", roots_expense=roots_expense, roots_income=roots_income, back_url="/my/apps/expenses"))

    @http.route("/my/apps/expenses/categories/new", type="http", auth="user", website=True)
    def expense_category_new(self, category_type="expense", **kw):
        user = request.env.user
        category_type = category_type if category_type in ("expense", "income") else "expense"
        parents = self._category_model().search(self._category_domain(user, category_type=category_type, parent_only=True), order="sequence, id")
        return request.render("dt_expense.portal_expense_category_form", self._base_values(page_title="Tạo danh mục", page_subtitle="", category=False, category_type=category_type, parents=parents, back_url="/my/apps/expenses/categories"))

    @http.route("/my/apps/expenses/categories/<int:category_id>/edit", type="http", auth="user", website=True)
    def expense_category_edit(self, category_id, **kw):
        category = self._category_model().browse(category_id)
        if not category.exists() or not category.can_manage(request.env.user):
            return request.redirect("/my/apps/expenses/categories")
        parents = self._category_model().search(self._category_domain(request.env.user, category_type=category.category_type, parent_only=True) + [("id", "!=", category.id)], order="sequence, id")
        return request.render("dt_expense.portal_expense_category_form", self._base_values(page_title="Sửa danh mục", page_subtitle="", category=category, category_type=category.category_type, parents=parents, back_url="/my/apps/expenses/categories"))

    @http.route("/my/apps/expenses/categories/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_categories_save(self, category_id=None, name="", icon="💸", category_type="expense", parent_id=None, sequence="10", note="", apply_next_month_rule="", **kw):
        user = request.env.user
        category_type = category_type if category_type in ("expense", "income") else "expense"
        parent = self._category_model().browse(self._safe_int(parent_id)) if parent_id else self._category_model().browse()
        vals = {
            "name": (name or "").strip() or "Danh mục mới",
            "icon": (icon or ("💰" if category_type == "income" else "💸")).strip(),
            "note": (note or "").strip(),
            "sequence": self._safe_int(sequence, 10),
            "category_type": category_type,
            "parent_id": parent.id if parent.exists() else False,
            "apply_next_month_rule": apply_next_month_rule == "on",
            "user_id": user.id,
        }
        category_model = self._category_model()
        if category_id:
            category = category_model.browse(self._safe_int(category_id))
            if category.exists() and category.can_manage(user):
                category.write(vals)
        else:
            category_model.create(vals)
        return request.redirect("/my/apps/expenses/categories")

    @http.route("/my/apps/expenses/categories/<int:category_id>/delete", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_category_delete(self, category_id, **kw):
        category = self._category_model().browse(category_id)
        if category.exists() and category.can_manage(request.env.user):
            if category.entry_count:
                category.write({"active": False})
            else:
                category.unlink()
        return request.redirect("/my/apps/expenses/categories")

    @http.route("/my/apps/expenses/categories/<int:category_id>/suggestions", type="http", auth="user", website=True)
    def expense_category_suggestions(self, category_id, **kw):
        category = self._category_model().browse(category_id)
        if not category.exists() or not category.can_manage(request.env.user):
            return request.redirect("/my/apps/expenses/categories")
        suggestions = self._suggestion_model().search([("category_id", "=", category.id)], order="sequence, id")
        return request.render("dt_expense.portal_expense_suggestions", self._base_values(page_title="Gợi ý tiêu đề", page_subtitle=f"Danh mục: {category.name}", category=category, suggestions=suggestions, back_url="/my/apps/expenses/categories"))

    @http.route("/my/apps/expenses/categories/<int:category_id>/suggestions/new", type="http", auth="user", website=True)
    def expense_category_suggestion_new(self, category_id, **kw):
        category = self._category_model().browse(category_id)
        if not category.exists() or not category.can_manage(request.env.user):
            return request.redirect("/my/apps/expenses/categories")
        return request.render("dt_expense.portal_expense_suggestion_form", self._base_values(page_title="Thêm gợi ý tiêu đề", page_subtitle=f"Danh mục: {category.name}", category=category, suggestion=False, back_url=f"/my/apps/expenses/categories/{category.id}/suggestions"))

    @http.route("/my/apps/expenses/suggestions/<int:suggestion_id>/edit", type="http", auth="user", website=True)
    def expense_category_suggestion_edit(self, suggestion_id, **kw):
        suggestion = self._suggestion_model().browse(suggestion_id)
        if not suggestion.exists() or not suggestion.category_id.can_manage(request.env.user):
            return request.redirect("/my/apps/expenses/categories")
        return request.render("dt_expense.portal_expense_suggestion_form", self._base_values(page_title="Sửa gợi ý tiêu đề", page_subtitle=f"Danh mục: {suggestion.category_id.name}", category=suggestion.category_id, suggestion=suggestion, back_url=f"/my/apps/expenses/categories/{suggestion.category_id.id}/suggestions"))

    @http.route("/my/apps/expenses/categories/<int:category_id>/suggestions/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_category_suggestion_save(self, category_id, suggestion_id=None, name="", sequence="10", **kw):
        category = self._category_model().browse(category_id)
        if not category.exists() or not category.can_manage(request.env.user):
            return request.redirect("/my/apps/expenses/categories")
        vals = {"category_id": category.id, "name": (name or "").strip() or "Gợi ý mới", "sequence": self._safe_int(sequence, 10)}
        suggestion_model = self._suggestion_model()
        if suggestion_id:
            suggestion = suggestion_model.browse(self._safe_int(suggestion_id))
            if suggestion.exists() and suggestion.category_id == category:
                suggestion.write(vals)
        else:
            suggestion_model.create(vals)
        return request.redirect(f"/my/apps/expenses/categories/{category.id}/suggestions")

    @http.route("/my/apps/expenses/suggestions/<int:suggestion_id>/delete", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_category_suggestion_delete(self, suggestion_id, **kw):
        suggestion = self._suggestion_model().browse(suggestion_id)
        back_url = "/my/apps/expenses/categories"
        if suggestion.exists() and suggestion.category_id.can_manage(request.env.user):
            back_url = f"/my/apps/expenses/categories/{suggestion.category_id.id}/suggestions"
            suggestion.unlink()
        return request.redirect(back_url)

    @http.route("/my/apps/expenses/history", type="http", auth="user", website=True)
    def expense_history(self, page=1, tab="activity", scope="mine", search="", member_id="", date_from="", date_to="", entry_type="", parent_id="", category_id="", group_mode="parent", **kw):
        user = request.env.user
        tab = tab if tab in ("activity", "statistics") else "activity"
        scope = scope if scope in ("mine", "family") else "mine"
        member_value = self._safe_int(member_id)
        parent_value = self._safe_int(parent_id)
        category_value = self._safe_int(category_id)
        domain = self._activity_domain(user, scope=scope, search=search, member_id=member_value, date_from=self._parse_date(date_from), date_to=self._parse_date(date_to), entry_type=entry_type, parent_id=parent_value, category_id=category_value)
        entry_model = self._entry_model()
        all_entries = entry_model.search(domain, order="expense_date desc, id desc")
        total_income = sum(abs(e.amount or 0.0) for e in all_entries if e.entry_type == "income")
        total_expense = sum(abs(e.amount or 0.0) for e in all_entries if e.entry_type == "expense")
        total_net = sum(e.get_balance_effect() for e in all_entries)
        per_page = 20
        total = len(all_entries)
        pager = portal_pager(url="/my/apps/expenses/history", total=total, page=page, step=per_page, url_args={"tab": tab, "scope": scope, "search": search, "member_id": member_id, "date_from": date_from, "date_to": date_to, "entry_type": entry_type, "parent_id": parent_id, "category_id": category_id, "group_mode": group_mode})
        entries = all_entries[pager["offset"]:pager["offset"]+per_page]
        parents = self._category_model().search(self._category_domain(user, parent_only=True), order="category_type, sequence, id")
        children_domain = self._category_domain(user, leaf_only=True)
        if parent_value:
            children_domain.append(("parent_id", "=", parent_value))
        children = self._category_model().search(children_domain, order="sequence, id")
        visible_user_ids = self._visible_user_ids(user, scope)
        family_members = request.env["res.users"].sudo().browse(visible_user_ids)
        statistics = self._build_statistics(all_entries, group_mode=group_mode)
        filter_count = len([x for x in [search, member_id if scope == 'family' else '', date_from, date_to, entry_type, parent_id, category_id] if x])
        simple_pager = self._build_simple_pager(pager)
        return request.render("dt_expense.portal_expense_history", self._base_values(page_title="Lịch sử giao dịch", page_subtitle="", tab=tab, entries=entries, pager=pager, simple_pager=simple_pager, search=search, scope=scope, member_id=member_value, family_members=family_members, date_from=date_from, date_to=date_to, entry_type=entry_type, parent_id=parent_value, category_id=category_value, parent_categories=parents, child_categories=children, group_mode=group_mode if group_mode in ('parent','child') else 'parent', statistics=statistics, total_income_label=self._format_money(total_income), total_expense_label=self._format_money(total_expense), total_net_label=self._format_money(total_net, show_plus=True), filter_count=filter_count, back_url="/my/apps/expenses"))

    @http.route("/my/apps/expenses/title_suggestions", type="http", auth="user", website=True)
    def expense_title_suggestions(self, category_id="", q="", **kw):
        user = request.env.user
        category = self._category_model().browse(self._safe_int(category_id)) if category_id else self._category_model().browse()
        query = (q or "").strip()
        rows = []
        seen = set()
        allowed_category = False
        if category.exists():
            allowed_ids = self._category_model().search(self._category_domain(user)).ids
            allowed_category = category.id in allowed_ids
        if allowed_category:
            suggestions = self._suggestion_model().search([("category_id", "=", category.id), ("active", "=", True)], order="sequence, id")
            histories = self._history_model().search([("user_id", "=", user.id), ("category_id", "=", category.id)], order="used_count desc, last_used_at desc", limit=15)
            for item in list(suggestions) + list(histories):
                label = (item.name or "").strip()
                if not label:
                    continue
                if query and query.lower() not in label.lower():
                    continue
                key = label.lower()
                if key in seen:
                    continue
                seen.add(key)
                rows.append({"label": label})
        return request.make_response(json.dumps(rows[:12]), headers=[('Content-Type', 'application/json')])
