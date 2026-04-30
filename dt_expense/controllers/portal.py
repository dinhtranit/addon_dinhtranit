# -*- coding: utf-8 -*-
import json
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta

from odoo import fields, http
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.http import request, Response


class FamilyExpensePortal(http.Controller):

    def _base_values(self, **extra):
        apps = request.env["dt.app"].sudo().search([("is_active", "=", True)], order="sequence, id")
        values = {
            "app_cards": apps,
            "page_name": extra.get("page_name", "expenses"),
            "page_title": extra.get("page_title", "Family Expense"),
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

    def _my_entry_domain(self, user):
        return [("user_id", "=", user.id)]

    def _visible_entry_domain(self, user):
        return [
            "|",
            ("user_id", "=", user.id),
            "&",
            ("privacy", "=", "public"),
            ("company_id", "=", user.company_id.id),
        ]

    def _category_domain(self, user, category_type=None):
        domain = ["|", ("scope", "=", "shared"), ("user_id", "=", user.id)]
        if category_type:
            domain.append(("category_type", "=", category_type))
        return domain

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

    def _format_money(self, amount, show_plus=False):
        return self._entry_model()._format_money(amount, show_plus=show_plus)

    def _format_input_money(self, amount):
        return self._entry_model().format_amount_for_input(amount)

    def _parse_money(self, value):
        return self._entry_model().parse_money_text(value)

    def _safe_int(self, value, default=None):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _signed_amount(self, entry):
        return entry.signed_amount if entry.signed_amount or entry.signed_amount == 0 else entry.get_balance_effect()

    def _sum_signed(self, entries):
        return sum(self._signed_amount(entry) for entry in entries)

    def _build_category_bars(self, entries):
        totals = defaultdict(float)
        categories = {}
        for entry in entries:
            if not entry.category_id:
                continue
            totals[entry.category_id.id] += abs(entry.amount or 0.0)
            categories[entry.category_id.id] = entry.category_id
        grand_total = sum(totals.values()) or 1.0
        rows = []
        for category_id, amount in sorted(totals.items(), key=lambda item: item[1], reverse=True):
            category = categories.get(category_id)
            rows.append({
                "label": f"{category.icon or '💸'} {category.name}",
                "amount_label": self._format_money(amount),
                "ratio": round(amount / grand_total * 100, 1),
            })
        return rows

    def _build_trend_bars(self, entries, period, start, end):
        bucket = defaultdict(float)
        if period == "year":
            cursor = start
            while cursor <= end:
                bucket[cursor.strftime("%Y-%m")] = 0.0
                cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
            for entry in entries:
                bucket[entry.expense_date.strftime("%Y-%m")] += self._signed_amount(entry)
            max_value = max((abs(value) for value in bucket.values()), default=0.0)
            return [{
                "label": key[-2:] + "/" + key[:4],
                "amount_label": self._format_money(amount, show_plus=True),
                "ratio": round((abs(amount) / max_value) * 100, 1) if max_value else 0,
            } for key, amount in bucket.items()]
        cursor = start
        while cursor <= end:
            bucket[cursor.isoformat()] = 0.0
            cursor += timedelta(days=1)
        for entry in entries:
            bucket[entry.expense_date.isoformat()] += self._signed_amount(entry)
        max_value = max((abs(value) for value in bucket.values()), default=0.0)
        rows = []
        for key, amount in bucket.items():
            current_day = datetime.strptime(key, "%Y-%m-%d").date()
            rows.append({
                "label": current_day.strftime("%d/%m"),
                "amount_label": self._format_money(amount, show_plus=True),
                "ratio": round((abs(amount) / max_value) * 100, 1) if max_value else 0,
            })
        return rows

    def _home_summary(self, user):
        entry_model = self._entry_model()
        today = fields.Date.context_today(entry_model)
        month_key = today.strftime("%Y-%m")
        my_entries = entry_model.search(self._my_entry_domain(user), order="expense_date desc, id desc")
        month_entries = my_entries.filtered(lambda entry: entry.expense_month_key == month_key)
        today_entries = my_entries.filtered(lambda entry: entry.expense_date == today)
        month_income_total = sum(abs(entry.amount or 0.0) for entry in month_entries if entry.entry_type == "income")
        month_expense_total = sum(abs(entry.amount or 0.0) for entry in month_entries if entry.entry_type == "expense")
        month_net_total = self._sum_signed(month_entries)
        current_balance = self._sum_signed(my_entries)
        return {
            "current_balance": current_balance,
            "current_balance_label": self._format_money(current_balance),
            "current_balance_input": self._format_input_money(current_balance),
            "month_income_label": self._format_money(month_income_total),
            "month_expense_label": self._format_money(month_expense_total),
            "month_net_label": self._format_money(month_net_total, show_plus=True),
            "today_count": len(today_entries),
        }

    def _entry_form_values(self, entry=False, entry_type="expense"):
        entry_model = self._entry_model()
        user = request.env.user
        valid_entry_types = ["expense", "income", "adjustment"]
        current_entry_type = entry.entry_type if entry else (entry_type if entry_type in valid_entry_types else "expense")
        categories = self._category_model().search(self._category_domain(user), order="category_type, sequence, id")
        page_title_map = {
            "expense": ("Thêm chi tiêu", "Nhập khoản chi mới bằng VND."),
            "income": ("Thêm thu nhập", "Theo dõi nhiều nguồn tiền vào."),
            "adjustment": ("Điều chỉnh số dư", "Dùng khi muốn chỉnh số dư thực tế."),
        }
        page_title, page_subtitle = page_title_map.get(current_entry_type, page_title_map["expense"])
        if entry:
            page_title = f"Sửa {entry.get_entry_type_label().lower()}"
            page_subtitle = "Cập nhật tiền, quyền xem, danh mục, gợi ý tiêu đề và file đính kèm."
        selected_category = entry.category_id if entry else False
        initial_suggestions = []
        if selected_category:
            initial_suggestions = self._suggestion_model().suggestions_for_portal(selected_category, user=user, query=entry.name or "", limit=8)
        return self._base_values(
            page_title=page_title,
            page_subtitle=page_subtitle,
            entry=entry,
            current_entry_type=current_entry_type,
            entry_type_options=entry_model._fields["entry_type"].selection,
            categories=categories,
            default_date=(entry.expense_date.isoformat() if entry and entry.expense_date else date.today().isoformat()),
            amount_input_value=(entry_model.format_amount_for_input(entry.amount) if entry else ""),
            back_url="/my/apps/expenses",
            initial_suggestions=initial_suggestions,
        )

    @http.route("/my/apps/expenses", type="http", auth="user", website=True)
    def expense_home(self, page=1, **kw):
        user = request.env.user
        entry_model = self._entry_model()
        category_model = self._category_model()
        per_page = 10
        domain = self._visible_entry_domain(user)
        total = entry_model.search_count(domain)
        pager = portal_pager(url="/my/apps/expenses", total=total, page=page, step=per_page)
        recent_entries = entry_model.search(domain, order="expense_date desc, id desc", limit=per_page, offset=pager["offset"])
        categories = category_model.search(self._category_domain(user), order="category_type, sequence, id")
        summary = self._home_summary(user)
        values = self._base_values(
            page_title="Sổ thu chi",
            page_subtitle="Theo dõi số dư, khoản thu, khoản chi và các điều chỉnh bằng VND.",
            recent_entries=recent_entries,
            pager=pager,
            total=total,
            income_category_count=len(categories.filtered(lambda category: category.category_type == "income")),
            expense_category_count=len(categories.filtered(lambda category: category.category_type == "expense")),
        )
        values.update(summary)
        return request.render("dt_expense.portal_expense_home", values)

    @http.route("/my/apps/expenses/new", type="http", auth="user", website=True)
    def expense_new(self, entry_type="expense", **kw):
        return request.render("dt_expense.portal_expense_form", self._entry_form_values(entry=False, entry_type=entry_type))

    @http.route("/my/apps/expenses/<int:entry_id>/edit", type="http", auth="user", website=True)
    def expense_edit(self, entry_id, **kw):
        entry = self._entry_model().browse(entry_id)
        if not entry.exists() or entry.user_id != request.env.user:
            return request.redirect("/my/apps/expenses")
        return request.render("dt_expense.portal_expense_form", self._entry_form_values(entry=entry))

    @http.route("/my/apps/expenses/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_save(self, entry_id=None, entry_type="expense", adjustment_direction="increase", name="", expense_date="", category_id=None, amount="0", note="", privacy="private", **kw):
        user = request.env.user
        entry_model = self._entry_model()
        valid_types = dict(entry_model._fields["entry_type"].selection)
        entry_type = entry_type if entry_type in valid_types else "expense"
        adjustment_direction = adjustment_direction if adjustment_direction in ("increase", "decrease") else "increase"
        privacy = privacy if privacy in ("private", "public") else "private"
        amount_value = abs(self._parse_money(amount))
        vals = {
            "name": (name or "").strip(),
            "note": (note or "").strip(),
            "user_id": user.id,
            "entry_type": entry_type,
            "adjustment_direction": adjustment_direction,
            "privacy": privacy,
            "amount": amount_value,
            "currency_id": entry_model._default_currency_id(),
        }
        if expense_date:
            try:
                vals["expense_date"] = datetime.strptime(expense_date, "%Y-%m-%d").date()
            except ValueError:
                vals["expense_date"] = date.today()
        else:
            vals["expense_date"] = date.today()
        if entry_type == "adjustment":
            vals["category_id"] = False
        else:
            category_record_id = self._safe_int(category_id)
            category = self._category_model().browse(category_record_id) if category_record_id else self._category_model().browse()
            if not category.exists() or category.category_type != entry_type or not category.can_access(user=user):
                return request.redirect(f"/my/apps/expenses/new?entry_type={entry_type}")
            vals["category_id"] = category.id
        if entry_id:
            entry_record_id = self._safe_int(entry_id)
            entry = entry_model.browse(entry_record_id) if entry_record_id else entry_model.browse()
            if not entry.exists() or entry.user_id != user:
                return request.redirect("/my/apps/expenses")
            entry.write(vals)
        else:
            entry = entry_model.create(vals)
        request.env["dt.media"].sudo().create_from_uploads(
            request.httprequest.files.getlist("media_files"),
            entry,
            owner_user=user,
            mark_first_cover=True,
        )
        return request.redirect("/my/apps/expenses")

    @http.route("/my/apps/expenses/balance/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_balance_save(self, current_amount="0", **kw):
        target_balance = self._parse_money(current_amount)
        self._entry_model().create_balance_adjustment(target_balance, user=request.env.user)
        return request.redirect("/my/apps/expenses")

    @http.route("/my/apps/expenses/<int:entry_id>/delete", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_delete(self, entry_id, **kw):
        entry = self._entry_model().browse(entry_id)
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
                    entry_record_id = self._safe_int(entry_id)
                    if entry_record_id:
                        return request.redirect(f"/my/apps/expenses/{entry_record_id}/edit")
        return request.redirect("/my/apps/expenses")

    @http.route("/my/apps/expenses/categories", type="http", auth="user", website=True)
    def expense_categories(self, **kw):
        user = request.env.user
        categories = self._category_model().search(self._category_domain(user), order="category_type, sequence, id")
        return request.render("dt_expense.portal_expense_categories", self._base_values(
            page_title="Danh mục thu chi",
            page_subtitle="Quản lý danh mục, quyền sửa và các gợi ý tiêu đề nhập nhanh.",
            categories=categories,
            back_url="/my/apps/expenses",
            category_type_options=self._category_model()._fields["category_type"].selection,
            scope_options=self._category_model()._fields["scope"].selection,
        ))

    @http.route("/my/apps/expenses/categories/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_categories_save(self, category_id=None, name="", icon="💸", category_type="expense", scope="shared", sequence="10", note="", **kw):
        user = request.env.user
        category_type = category_type if category_type in ("expense", "income") else "expense"
        scope = scope if scope in ("shared", "private") else "shared"
        sequence_value = self._safe_int(sequence, default=10)
        default_icon = "💰" if category_type == "income" else "💸"
        vals = {
            "name": (name or "").strip() or "Danh mục mới",
            "icon": (icon or default_icon).strip() or default_icon,
            "note": (note or "").strip(),
            "sequence": sequence_value,
            "category_type": category_type,
            "scope": scope,
            "user_id": user.id if scope == "private" else False,
        }
        category_model = self._category_model()
        if category_id:
            category_record_id = self._safe_int(category_id)
            category = category_model.browse(category_record_id) if category_record_id else category_model.browse()
            if category.exists() and category.can_manage(user=user):
                category.write(vals)
        else:
            category_model.create(vals)
        return request.redirect("/my/apps/expenses/categories")

    @http.route("/my/apps/expenses/categories/<int:category_id>/delete", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_categories_delete(self, category_id, **kw):
        category = self._category_model().browse(category_id)
        if category.exists() and category.can_manage(user=request.env.user):
            if category.entry_count:
                category.write({"active": False})
            else:
                category.unlink()
        return request.redirect("/my/apps/expenses/categories")

    @http.route("/my/apps/expenses/categories/<int:category_id>/suggestions/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_category_suggestion_save(self, category_id, suggestion_id=None, name="", sequence="10", **kw):
        user = request.env.user
        category = self._category_model().browse(category_id)
        if not category.exists() or not category.can_manage(user=user):
            return request.redirect("/my/apps/expenses/categories")
        vals = {
            "name": (name or "").strip(),
            "sequence": self._safe_int(sequence, default=10),
            "category_id": category.id,
            "is_manual": True,
            "active": True,
        }
        if not vals["name"]:
            return request.redirect("/my/apps/expenses/categories")
        suggestion_model = self._suggestion_model()
        existing = suggestion_model.search([
            ("category_id", "=", category.id),
            ("normalized_name", "=", suggestion_model._normalize_name(vals["name"])),
        ], limit=1)
        if suggestion_id:
            record = suggestion_model.browse(self._safe_int(suggestion_id))
            if record.exists() and record.category_id == category and category.can_manage(user=user):
                if existing and existing != record:
                    existing.write({"sequence": vals["sequence"], "active": True, "is_manual": True})
                    record.unlink()
                else:
                    record.write(vals)
        else:
            if existing:
                existing.write({"sequence": vals["sequence"], "active": True, "is_manual": True, "name": vals["name"]})
            else:
                suggestion_model.create(vals)
        return request.redirect("/my/apps/expenses/categories")

    @http.route("/my/apps/expenses/categories/<int:category_id>/suggestions/<int:suggestion_id>/delete", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_category_suggestion_delete(self, category_id, suggestion_id, **kw):
        user = request.env.user
        category = self._category_model().browse(category_id)
        suggestion = self._suggestion_model().browse(suggestion_id)
        if category.exists() and suggestion.exists() and suggestion.category_id == category and category.can_manage(user=user):
            suggestion.unlink()
        return request.redirect("/my/apps/expenses/categories")

    @http.route("/my/apps/expenses/title-suggestions", type="http", auth="user", website=True)
    def expense_title_suggestions(self, category_id=None, q="", limit="8", **kw):
        user = request.env.user
        category = self._category_model().browse(self._safe_int(category_id)) if category_id else self._category_model().browse()
        rows = self._suggestion_model().suggestions_for_portal(category, user=user, query=q, limit=self._safe_int(limit, default=8) or 8) if category else []
        payload = json.dumps({"items": rows})
        return Response(payload, content_type="application/json;charset=utf-8")

    @http.route("/my/apps/expenses/reports", type="http", auth="user", website=True)
    def expense_reports(self, period="month", anchor_date="", category_id="", entry_type="", view_scope="mine", **kw):
        user = request.env.user
        categories = self._category_model().search(self._category_domain(user), order="category_type, sequence, id")
        anchor = self._parse_anchor_date(anchor_date)
        period, start, end, label = self._compute_period_range(period, anchor)
        base_domain = self._my_entry_domain(user) if view_scope != "family" else self._visible_entry_domain(user)
        domain = list(base_domain) + [("expense_date", ">=", start), ("expense_date", "<=", end)]
        selected_category = False
        if category_id:
            category_record_id = self._safe_int(category_id)
            selected_category = self._category_model().browse(category_record_id) if category_record_id else False
            if selected_category and selected_category.exists():
                domain.append(("category_id", "=", selected_category.id))
        selected_entry_type = entry_type if entry_type in ("expense", "income", "adjustment") else ""
        if selected_entry_type:
            domain.append(("entry_type", "=", selected_entry_type))
        entries = self._entry_model().search(domain, order="expense_date desc, id desc")
        income_total = sum(abs(entry.amount or 0.0) for entry in entries if entry.entry_type == "income")
        expense_total = sum(abs(entry.amount or 0.0) for entry in entries if entry.entry_type == "expense")
        adjustment_total = sum(self._signed_amount(entry) for entry in entries if entry.entry_type == "adjustment")
        net_total = self._sum_signed(entries)
        return request.render("dt_expense.portal_expense_reports", self._base_values(
            page_title="Báo cáo thu chi",
            page_subtitle=label,
            back_url="/my/apps/expenses",
            categories=categories,
            entries=entries,
            period=period,
            anchor_date=anchor.isoformat(),
            view_scope=view_scope,
            selected_entry_type=selected_entry_type,
            selected_category=selected_category,
            income_total_label=self._format_money(income_total),
            expense_total_label=self._format_money(expense_total),
            adjustment_total_label=self._format_money(adjustment_total, show_plus=True),
            net_total_label=self._format_money(net_total, show_plus=True),
            category_bars=self._build_category_bars(entries),
            trend_bars=self._build_trend_bars(entries, period, start, end),
        ))
