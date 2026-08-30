# -*- coding: utf-8 -*-
import base64
import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta
import json
import math
from urllib.parse import urlencode, quote as urlquote

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
            "show_bottom_nav": extra.get("show_bottom_nav", False),
            "balance_visible": request.httprequest.cookies.get("dt_balance_visible") == "1",
        }
        values.update(extra)
        return values

    def _entry_model(self):
        return request.env["dt.expense.entry"].sudo()

    def _category_model(self):
        return request.env["dt.expense.category"].sudo()

    def _wallet_model(self):
        return request.env["dt.expense.wallet"].sudo()

    def _debt_model(self):
        return request.env["dt.expense.debt"].sudo()

    def _contact_model(self):
        return request.env["dt.expense.contact"].sudo()

    def _plan_model(self):
        return request.env["dt.expense.plan"].sudo()

    def _resolve_plan(self, user, plan_id):
        plan = self._plan_model().browse(self._safe_int(plan_id)) if plan_id else self._plan_model().browse()
        if not plan.exists() or plan.user_id.id != user.id:
            return self._plan_model().browse()
        return plan

    def _suggestion_model(self):
        return request.env["dt.expense.title.suggestion"].sudo()

    def _history_model(self):
        return request.env["dt.expense.title.history"].sudo()

    def _safe_int(self, value, default=None):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _parse_date(self, value, default=None):
        if isinstance(value, date):
            return value
        if not value:
            return default
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return default

    def _normalize_month_start(self, value):
        dt = self._parse_date(value, date.today()) if isinstance(value, str) else value
        return dt.replace(day=1)

    def _format_money(self, amount, show_plus=False, short=False):
        return self._entry_model()._format_money(amount, show_plus=show_plus, short=short)

    def _format_input_money(self, amount):
        return self._entry_model().format_amount_for_input(amount)

    def _parse_money(self, value):
        return self._entry_model().parse_money_text(value)

    def _period_range(self, period="month", anchor=None):
        anchor = anchor or date.today()
        if isinstance(anchor, str):
            anchor = self._parse_date(anchor, date.today())
        if period == "week":
            start = anchor - timedelta(days=anchor.weekday())
            end = start + timedelta(days=6)
            label = "%s - %s" % (start.strftime("%d/%m"), end.strftime("%d/%m/%Y"))
        elif period == "quarter":
            q_month = ((anchor.month - 1) // 3) * 3 + 1
            start = date(anchor.year, q_month, 1)
            end_month = q_month + 2
            end = date(anchor.year, end_month, calendar.monthrange(anchor.year, end_month)[1])
            label = "Quý %s/%s" % (((anchor.month - 1) // 3) + 1, anchor.year)
        elif period == "year":
            start = date(anchor.year, 1, 1)
            end = date(anchor.year, 12, 31)
            label = "Năm %s" % anchor.year
        else:
            start = date(anchor.year, anchor.month, 1)
            end = date(anchor.year, anchor.month, calendar.monthrange(anchor.year, anchor.month)[1])
            label = "Tháng %s, %s" % (anchor.month, anchor.year)
        return start, end, label

    def _category_domain(self, user, category_type=None, parent_only=False, leaf_only=False):
        admin_user = request.env.ref("base.user_admin", raise_if_not_found=False)
        owner_ids = [user.id]
        if admin_user:
            owner_ids.append(admin_user.id)
        domain = [("user_id", "in", owner_ids), ("active", "=", True)]
        if category_type:
            domain.append(("category_type", "=", category_type))
        if parent_only:
            domain.append(("parent_id", "=", False))
        if leaf_only:
            domain.append(("is_leaf", "=", True))
        return domain

    def _visible_user_ids(self, user, scope="mine"):
        if scope == "family":
            return user.get_visible_expense_user_ids()
        return [user.id]

    def _wallet_domain(self, user, scope="mine"):
        return [("user_id", "in", self._visible_user_ids(user, scope)), ("active", "=", True)]

    def _safe_int_list(self, values):
        result = []
        if not values:
            return result
        if isinstance(values, (str, bytes)):
            values = [values]
        for v in values:
            n = self._safe_int(v)
            if n:
                result.append(n)
        return result

    def _activity_domain(self, user, scope="mine", search="", member_id=None, date_from=None, date_to=None, entry_type=None, parent_id=None, category_id=None, wallet_id=None, member_ids=None, debt_flow=None, debt_id=None, plan_id=None):
        visible_ids = self._visible_user_ids(user, scope)
        domain = [("active", "=", True), ("user_id", "in", visible_ids)]
        ids = [i for i in (member_ids or []) if i in visible_ids]
        if ids:
            domain.append(("user_id", "in", ids))
        elif member_id:
            domain.append(("user_id", "=", member_id))
        if date_from:
            domain.append(("expense_date", ">=", date_from))
        if date_to:
            domain.append(("expense_date", "<=", date_to))
        if entry_type in ("expense", "income", "adjustment", "debt"):
            domain.append(("entry_type", "=", entry_type))
        if debt_flow in ("lend_out", "borrow_in", "collect_lend", "repay_borrow"):
            domain.append(("debt_flow", "=", debt_flow))
        if debt_id:
            domain.append(("debt_id", "=", debt_id))
        if plan_id:
            domain.append(("plan_id", "=", plan_id))
        if wallet_id:
            domain.append(("wallet_id", "=", wallet_id))
        if category_id:
            domain.append(("category_id", "=", category_id))
        elif parent_id:
            child_ids = self._category_model().search([("parent_id", "=", parent_id), ("active", "=", True)]).ids
            domain.append(("category_id", "in", child_ids + [parent_id]))
        if search:
            domain += ["|", "|", "|", "|", ("name", "ilike", search), ("note", "ilike", search), ("category_id.name", "ilike", search), ("user_id.name", "ilike", search), ("wallet_id.name", "ilike", search)]
        return domain

    def _cash_report_buckets(self, entries):
        """Return true income, true spending and total cash movement.

        Debt and adjustment entries affect balance, but they should not inflate the
        Thu/Chi labels in dashboard/history. Their cash effect is included in net.
        """
        income = sum(float(entry.amount or 0.0) for entry in entries if entry.entry_type == "income")
        expense = sum(float(entry.amount or 0.0) for entry in entries if entry.entry_type == "expense" and entry.category_id.count_in_expense)
        net = sum(entry.get_balance_effect() for entry in entries)
        return income, expense, net

    def _donut_point(self, angle_deg, radius, center=100):
        rad = math.radians(angle_deg - 90)
        return center + radius * math.cos(rad), center + radius * math.sin(rad)

    def _donut_slice_path(self, angle_start, angle_end, outer=90, inner=55):
        x1, y1 = self._donut_point(angle_start, outer)
        x2, y2 = self._donut_point(angle_end, outer)
        x3, y3 = self._donut_point(angle_end, inner)
        x4, y4 = self._donut_point(angle_start, inner)
        large_arc = 1 if (angle_end - angle_start) > 180 else 0
        return (
            "M %.2f %.2f A %s %s 0 %s 1 %.2f %.2f L %.2f %.2f A %s %s 0 %s 0 %.2f %.2f Z"
            % (x1, y1, outer, outer, large_arc, x2, y2, x3, y3, inner, inner, large_arc, x4, y4)
        )

    def _build_report(self, entries, group_mode="parent", limit=None, link_params=None):
        totals = defaultdict(float)
        buckets = {}
        expense_entries = entries.filtered(lambda e: e.entry_type == "expense" and e.category_id and e.category_id.count_in_expense)
        for entry in expense_entries:
            bucket = entry.category_id.parent_id if (group_mode == "parent" and entry.category_id.parent_id) else entry.category_id
            totals[bucket.id] += abs(entry.amount or 0.0)
            buckets[bucket.id] = bucket
        total_amount = sum(totals.values())
        colors = ["#bf5a3f", "#dcb06c", "#739363", "#8e7bb0", "#a99c8c", "#e6b66a", "#6a8c6a"]
        rows = []
        angle = 0.0
        sorted_items = sorted(totals.items(), key=lambda item: item[1], reverse=True)
        if limit:
            sorted_items = sorted_items[:limit]
        for idx, (bucket_id, amount) in enumerate(sorted_items):
            ratio = (amount / total_amount) if total_amount else 0.0
            next_angle = angle + ratio * 360.0
            color = colors[idx % len(colors)]
            bucket = buckets[bucket_id]
            link_query = dict(link_params or {})
            link_query["entry_type"] = "expense"
            link_query["category_id" if group_mode == "child" else "parent_id"] = bucket_id
            rows.append({
                "id": bucket_id,
                "name": bucket.name,
                "icon": bucket.icon or "💸",
                "amount": amount,
                "amount_label": self._format_money(amount),
                "ratio": round(ratio * 100),
                "ratio_raw": ratio * 100,
                "color": color,
                "svg_path": self._donut_slice_path(angle, min(next_angle, angle + 359.99)) if ratio else "",
                "link": "/my/apps/expenses/history?%s" % urlencode(link_query),
            })
            angle = next_angle
        return {
            "total": total_amount,
            "total_label": self._format_money(total_amount, short=False),
            "rows": rows,
        }

    def _home_summary(self, user):
        entry_model = self._entry_model()
        today = fields.Date.context_today(entry_model)
        month_start, month_end, month_label = self._period_range("month", today)
        weekday_labels = ["thứ Hai", "thứ Ba", "thứ Tư", "thứ Năm", "thứ Sáu", "thứ Bảy", "CN"]
        today_label = "Sáng %s · %s" % (weekday_labels[today.weekday()], today.strftime("%d.%m"))
        month_short_label = "T%s" % today.month
        visible_user_ids = user.get_visible_expense_user_ids()
        entries = entry_model.search([("active", "=", True), ("user_id", "in", visible_user_ids)])
        month_entries = entries.filtered(lambda entry: entry.accounting_month and month_start <= entry.accounting_month <= month_end)
        income_total, expense_total, net_total = self._cash_report_buckets(month_entries)
        current_balance = entry_model.compute_current_balance(users=visible_user_ids)
        wallets = self._wallet_model().search([("user_id", "=", user.id), ("active", "=", True)], order="sequence, id")
        debts = self._debt_model().search([("user_id", "in", visible_user_ids), ("active", "=", True), ("state", "=", "open")])
        lend_total = sum(debt.remaining_amount for debt in debts if debt.debt_type == "lend")
        borrow_total = sum(debt.remaining_amount for debt in debts if debt.debt_type == "borrow")
        member_rows = []
        for member in request.env["res.users"].sudo().browse(visible_user_ids):
            member_entries = month_entries.filtered(lambda e: e.user_id.id == member.id)
            _, member_expense, member_net = self._cash_report_buckets(member_entries)
            member_rows.append({"user": member, "expense_label": self._format_money(member_expense, short=True), "net_label": self._format_money(member_net, show_plus=True, short=True)})
        report = self._build_report(month_entries, group_mode="child", limit=6, link_params={
            "date_from": month_start.isoformat(),
            "date_to": month_end.isoformat(),
            "scope": "family",
        })
        return {
            "current_balance": current_balance,
            "current_balance_label": self._format_money(current_balance),
            "current_balance_input": self._format_input_money(current_balance),
            "month_label": month_label,
            "today_label": today_label,
            "month_short_label": month_short_label,
            "month_income_label": self._format_money(income_total, short=False),
            "month_expense_label": self._format_money(expense_total, short=False),
            "month_net_label": self._format_money(net_total, show_plus=True, short=True),
            "wallets": wallets,
            "debt_lend_label": self._format_money(lend_total, short=False),
            "debt_borrow_label": self._format_money(borrow_total, short=False),
            "debt_count": len(debts),
            "member_rows": member_rows,
            "report": report,
        }

    def _plan_summary(self, plan):
        debts = self._debt_model().search([("plan_id", "=", plan.id), ("active", "=", True)])
        debt_borrow_total = sum(debt.amount for debt in debts if debt.debt_type == "borrow")
        debt_lend_total = sum(debt.amount for debt in debts if debt.debt_type == "lend")
        entries = self._entry_model().search([("plan_id", "=", plan.id), ("active", "=", True)])
        fund_net = sum(entry.amount if entry.plan_flow == "fund_in" else -entry.amount for entry in entries if entry.entry_type == "plan_fund")
        income_total = sum(entry.amount for entry in entries if entry.entry_type == "income")
        expense_total = sum(entry.amount for entry in entries if entry.entry_type == "expense" and entry.category_id.count_in_expense)
        raised_total = debt_borrow_total + fund_net + income_total
        remaining_target = max(plan.budget_amount - raised_total, 0.0)
        spent_total = expense_total + debt_lend_total
        fund_balance = raised_total - spent_total
        return {
            "debts": debts,
            "debt_borrow_total_label": self._format_money(debt_borrow_total, short=False),
            "debt_lend_total_label": self._format_money(debt_lend_total, short=False),
            "raised_total": raised_total,
            "raised_total_label": self._format_money(raised_total, short=False),
            "remaining_target": remaining_target,
            "remaining_target_label": self._format_money(remaining_target, short=False),
            "spent_total": spent_total,
            "spent_total_label": self._format_money(spent_total, short=False),
            "fund_balance": fund_balance,
            "fund_balance_label": self._format_money(fund_balance, short=False),
        }

    def _wallet_summary(self, wallet):
        entries = self._entry_model().search([("wallet_id", "=", wallet.id), ("active", "=", True)])
        income_total = sum(entry.get_balance_effect() for entry in entries if entry.entry_type == "income")
        expense_total = sum(entry.get_balance_effect() for entry in entries if entry.entry_type == "expense")
        adjustment_total = sum(entry.get_balance_effect() for entry in entries if entry.entry_type == "adjustment")
        lend_effect = sum(entry.get_balance_effect() for entry in entries if entry.entry_type == "debt" and entry.debt_flow in ("lend_out", "collect_lend"))
        borrow_effect = sum(entry.get_balance_effect() for entry in entries if entry.entry_type == "debt" and entry.debt_flow in ("borrow_in", "repay_borrow"))
        plan_fund_entries = entries.filtered(lambda e: e.entry_type == "plan_fund")
        plan_fund_effect = sum(entry.get_balance_effect() for entry in plan_fund_entries)
        transfer_effect = sum(entry.get_balance_effect() for entry in entries if entry.entry_type == "transfer")
        plan_breakdown = defaultdict(float)
        for entry in plan_fund_entries:
            if entry.plan_id:
                plan_breakdown[entry.plan_id] += -entry.get_balance_effect()
        plan_rows = [{"plan": plan, "amount_label": self._format_money(amount, short=False)} for plan, amount in plan_breakdown.items() if amount]
        lend_debts = self._debt_model().search([("wallet_id", "=", wallet.id), ("debt_type", "=", "lend"), ("state", "=", "open")])
        borrow_debts = self._debt_model().search([("wallet_id", "=", wallet.id), ("debt_type", "=", "borrow"), ("state", "=", "open")])
        return {
            "opening_balance_label": self._format_money(wallet.opening_balance, short=False),
            "income_total_label": self._format_money(income_total, show_plus=True, short=False),
            "expense_total_label": self._format_money(expense_total, show_plus=True, short=False),
            "adjustment_total_label": self._format_money(adjustment_total, show_plus=True, short=False),
            "lend_effect_label": self._format_money(lend_effect, show_plus=True, short=False),
            "borrow_effect_label": self._format_money(borrow_effect, show_plus=True, short=False),
            "plan_fund_effect_label": self._format_money(plan_fund_effect, show_plus=True, short=False),
            "transfer_effect_label": self._format_money(transfer_effect, show_plus=True, short=False),
            "plan_rows": plan_rows,
            "lend_debts": lend_debts,
            "borrow_debts": borrow_debts,
        }

    def _entry_form_values(self, entry=False, active_tab="expense", plan_id=None):
        user = request.env.user
        entry = entry.sudo() if entry else False
        current_type = entry.entry_type if entry else active_tab
        if current_type not in ("expense", "income", "adjustment"):
            current_type = "expense"

        # Leaf categories for quick chips
        leaf_categories = self._category_model().search(self._category_domain(user, leaf_only=True), order="category_type, sequence, id")
        # Parent categories for modal grouping (and selectable)
        parent_categories = self._category_model().search(self._category_domain(user, parent_only=True), order="category_type, sequence, id")

        # Build leaf-by-parent mapping
        leaf_by_parent = {}
        for cat in leaf_categories:
            if cat.parent_id:
                leaf_by_parent.setdefault(cat.parent_id.id, []).append(cat)

        # 6-month usage counts per category
        _today = date.today()
        _m6, _y6 = _today.month - 6, _today.year
        if _m6 <= 0:
            _m6 += 12
            _y6 -= 1
        six_months_ago = date(_y6, _m6, 1)
        _all_cat_ids = list(leaf_categories.ids) + list(parent_categories.ids)
        _entries_6m = self._entry_model().search([
            ("user_id", "=", user.id), ("active", "=", True),
            ("category_id", "in", _all_cat_ids or [0]),
            ("expense_date", ">=", six_months_ago),
        ])
        six_month_counts = {}
        for _e in _entries_6m:
            if _e.category_id:
                six_month_counts[_e.category_id.id] = six_month_counts.get(_e.category_id.id, 0) + 1

        # 6-month group usage = parent count + sum of all leaf children counts
        six_month_group_usage = {}
        for _p in parent_categories:
            _ch = leaf_by_parent.get(_p.id, [])
            six_month_group_usage[_p.id] = six_month_counts.get(_p.id, 0) + sum(six_month_counts.get(_c.id, 0) for _c in _ch)

        # Sort parents by 6-month group usage desc for modal
        sorted_parents = parent_categories.sorted(key=lambda p: (-six_month_group_usage.get(p.id, 0), p.sequence, p.id))

        # Pre-build grouped_cats with children sorted by 6-month usage desc for the modal.
        # Parents with no children of their own are collected into one "Khác" group per
        # type instead of each rendering as its own full-width, mostly-empty header row.
        grouped_cats = []
        childless_parents = {"expense": [], "income": []}
        for parent in sorted_parents:
            children = leaf_by_parent.get(parent.id, [])
            if not children:
                childless_parents.setdefault(parent.category_type, []).append(parent)
                continue
            children_sorted = sorted(children, key=lambda c: (-six_month_counts.get(c.id, 0), c.sequence, c.id))
            grouped_cats.append({"parent": parent, "children": children_sorted})
        for cat_type, others in childless_parents.items():
            if others:
                grouped_cats.append({"parent": False, "children": others, "other_type": cat_type})

        # All selectable = leaf + parent (select element options)
        all_selectable = leaf_categories | parent_categories
        if entry and entry.category_id and entry.category_id not in all_selectable:
            all_selectable |= entry.category_id

        # Quick row = top 7 parent categories per type by 6-month group usage
        parents_by_type = {
            "expense": parent_categories.filtered(lambda c: c.category_type == "expense"),
            "income": parent_categories.filtered(lambda c: c.category_type == "income"),
        }
        def _pick_quick_parent(items):
            return items.sorted(key=lambda p: (-six_month_group_usage.get(p.id, 0), p.sequence, p.id))[:7]
        quick_categories = _pick_quick_parent(parents_by_type["expense"]) | _pick_quick_parent(parents_by_type["income"])
        # Covers every parent (not just the quick subset) so the "expand" panel can reuse it.
        quick_has_children = {cat.id: bool(leaf_by_parent.get(cat.id)) for cat in parent_categories}

        wallets = self._wallet_model().search([("user_id", "=", user.id), ("active", "=", True)], order="sequence, id")
        if not wallets:
            wallets = self._wallet_model().get_default_wallet(user)
        media_items = entry.get_media_items() if entry else request.env["dt.media"].sudo().browse()
        page_title = "Sửa giao dịch" if entry else "Ghi chép GD"
        plans = self._plan_model().search([("user_id", "=", user.id), ("state", "!=", "archived")], order="create_date desc")
        plan = entry.plan_id if entry else self._resolve_plan(user, plan_id)
        return self._base_values(
            page_title=page_title,
            page_subtitle="Nhập nhanh thu chi",
            entry=entry,
            active_tab=current_type,
            categories=all_selectable,
            quick_categories=quick_categories,
            quick_has_children=quick_has_children,
            parent_categories=sorted_parents,
            grouped_cats=grouped_cats,
            wallets=wallets,
            default_wallet=entry.wallet_id if entry else self._wallet_model().get_default_wallet(user),
            media_items=media_items,
            current_user=user.sudo(),
            default_date=(entry.expense_date.isoformat() if entry and entry.expense_date else date.today().isoformat()),
            default_accounting_month=(entry.accounting_month.isoformat() if entry and entry.accounting_month else date.today().replace(day=1).isoformat()),
            amount_input_value=(self._format_input_money(entry.amount) if entry else ""),
            plans=plans,
            plan=plan,
            return_to=("/my/apps/expenses/plans/%s" % plan.id if plan else ""),
            back_url="/my/apps/expenses",
        )

    @http.route(["/my/apps/expenses", "/my/expenses"], type="http", auth="user", website=True)
    def expense_home(self, **kw):
        user = request.env.user
        summary = self._home_summary(user)
        values = self._base_values(page_title="Hello %s" % user.name, page_subtitle=summary.get("today_label", ""), back_url="", show_bottom_nav=True, page_action_url="/my/apps/expenses/new", show_balance_toggle=True)
        values.update(summary)
        return request.render("dt_expense.portal_expense_home", values)

    @http.route("/my/apps/expenses/new", type="http", auth="user", website=True)
    def expense_new(self, entry_type="expense", plan_id=None, **kw):
        active_tab = entry_type if entry_type in ("expense", "income", "adjustment") else "expense"
        return request.render("dt_expense.portal_expense_form", self._entry_form_values(entry=False, active_tab=active_tab, plan_id=self._safe_int(plan_id)))

    def _safe_return_to(self, return_to, fallback):
        if return_to and isinstance(return_to, str) and return_to.startswith("/my/apps/"):
            return return_to
        return fallback

    @http.route("/my/apps/expenses/<int:entry_id>/view", type="http", auth="user", website=True)
    def expense_view(self, entry_id, scope="mine", return_to="", **kw):
        user = request.env.user
        scope = scope if scope in ("mine", "family") else "mine"
        entry = self._entry_model().browse(entry_id)
        back_url = self._safe_return_to(return_to, "/my/apps/expenses/history?scope=%s" % scope)
        if not entry.exists() or entry.user_id.id not in self._visible_user_ids(user, scope):
            return request.redirect(back_url)
        is_own = entry.user_id.id == user.id and scope != "family"
        can_edit = is_own and entry.entry_type not in ("debt", "plan_fund", "transfer")
        can_delete = is_own and entry.entry_type not in ("debt", "transfer")
        media_items = entry.get_media_items()
        edit_return = urlquote(back_url, safe="")
        return request.render("dt_expense.portal_expense_view", self._base_values(
            page_title="Chi tiết giao dịch", page_subtitle=entry.expense_date.strftime("%d/%m/%Y") if entry.expense_date else "",
            entry=entry.sudo(), media_items=media_items, scope=scope, can_edit=can_edit, can_delete=can_delete,
            back_url=back_url, edit_return=edit_return,
        ))

    @http.route("/my/apps/expenses/<int:entry_id>/edit", type="http", auth="user", website=True)
    def expense_edit(self, entry_id, return_to="", **kw):
        entry = self._entry_model().browse(entry_id)
        back_url = self._safe_return_to(return_to, "/my/apps/expenses/history")
        if not entry.exists() or entry.user_id.id != request.env.user.id or entry.entry_type in ("debt", "plan_fund", "transfer"):
            return request.redirect(back_url)
        values = self._entry_form_values(entry=entry)
        values["back_url"] = back_url
        values["return_to"] = return_to or ""
        return request.render("dt_expense.portal_expense_form", values)

    @http.route("/my/apps/expenses/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_save(self, entry_id=None, entry_type="expense", adjustment_direction="increase", name="", expense_date="", accounting_month="", category_id=None, wallet_id=None, amount="0", note="", plan_id=None, return_to="", **kw):
        user = request.env.user
        entry_model = self._entry_model()
        entry_type = entry_type if entry_type in ("expense", "income", "adjustment") else "expense"
        wallet = self._wallet_model().browse(self._safe_int(wallet_id)) if wallet_id else self._wallet_model().get_default_wallet(user)
        if not wallet.exists() or wallet.user_id.id != user.id:
            wallet = self._wallet_model().get_default_wallet(user)
        plan = self._resolve_plan(user, plan_id)
        vals = {
            "name": (name or "").strip(),
            "note": (note or "").strip(),
            "user_id": user.id,
            "wallet_id": wallet.id,
            "entry_type": entry_type,
            "adjustment_direction": adjustment_direction if adjustment_direction in ("increase", "decrease") else "increase",
            "amount": abs(self._parse_money(amount)),
            "currency_id": entry_model._default_currency_id(),
            "expense_date": self._parse_date(expense_date, date.today()),
            "accounting_month": self._normalize_month_start(accounting_month or expense_date or date.today().isoformat()),
            "plan_id": plan.id if plan else False,
        }
        if entry_type == "adjustment":
            vals["category_id"] = False
        else:
            category = self._category_model().browse(self._safe_int(category_id)) if category_id else self._category_model().browse()
            allowed_category_ids = self._category_model().search(self._category_domain(user, category_type=entry_type)).ids
            if not category.exists() or category.id not in allowed_category_ids:
                return request.redirect("/my/apps/expenses/new?entry_type=%s" % entry_type)
            vals["category_id"] = category.id
        if entry_id:
            entry = entry_model.browse(self._safe_int(entry_id))
            if not entry.exists() or entry.user_id.id != user.id or entry.entry_type in ("debt", "plan_fund", "transfer"):
                return request.redirect("/my/apps/expenses/history")
            entry.write(vals)
        else:
            entry = entry_model.create(vals)
        request.env["dt.media"].sudo().create_from_uploads(request.httprequest.files.getlist("media_files"), entry, owner_user=user, mark_first_cover=True)
        return request.redirect(self._safe_return_to(return_to, "/my/apps/expenses/history"))

    @http.route("/my/apps/expenses/balance/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_balance_save(self, current_amount="0", wallet_id=None, **kw):
        user = request.env.user
        wallet = self._wallet_model().browse(self._safe_int(wallet_id)) if wallet_id else self._wallet_model().get_default_wallet(user)
        if wallet.exists() and wallet.user_id.id == user.id:
            self._entry_model().create_balance_adjustment(self._parse_money(current_amount), user=user, wallet=wallet)
        return request.redirect("/my/apps/expenses/wallets")

    @http.route("/my/apps/expenses/<int:entry_id>/delete", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_delete(self, entry_id, return_to="", **kw):
        entry = self._entry_model().browse(entry_id)
        if entry.exists() and entry.user_id.id == request.env.user.id and entry.entry_type not in ("debt", "transfer"):
            request.env["dt.media"].sudo().search([("res_model", "=", entry._name), ("res_id", "=", entry.id)]).unlink()
            entry.unlink()
        return request.redirect(self._safe_return_to(return_to, "/my/apps/expenses/history"))

    @http.route("/my/apps/expenses/categories", type="http", auth="user", website=True)
    def expense_categories(self, category_type="expense", **kw):
        user = request.env.user
        category_type = category_type if category_type in ("expense", "income") else "expense"
        categories = self._category_model().search(self._category_domain(user, category_type=category_type), order="sequence, id")
        roots = categories.filtered(lambda c: not c.parent_id)
        return request.render("dt_expense.portal_expense_categories", self._base_values(
            page_title="Danh mục chi tiêu" if category_type == "expense" else "Danh mục thu nhập",
            page_subtitle="%s nhóm cha · %s mục con" % (len(roots), len(categories.filtered(lambda c: c.parent_id))),
            category_type=category_type,
            roots=roots,
            page_action_url="/my/apps/expenses/categories/new?category_type=%s" % category_type,
            back_url="/my/apps/expenses",
        ))

    @http.route("/my/apps/expenses/categories/new", type="http", auth="user", website=True)
    def expense_category_new(self, category_type="expense", parent_id=None, **kw):
        user = request.env.user
        category_type = category_type if category_type in ("expense", "income") else "expense"
        parents = self._category_model().search(self._category_domain(user, category_type=category_type, parent_only=True), order="sequence, id")
        parent = self._category_model().browse(self._safe_int(parent_id)) if parent_id else self._category_model().browse()
        return request.render("dt_expense.portal_expense_category_form", self._base_values(page_title="Tạo danh mục", category=False, category_type=category_type, parents=parents, selected_parent=parent, back_url="/my/apps/expenses/categories?category_type=%s" % category_type))

    @http.route("/my/apps/expenses/categories/<int:category_id>/edit", type="http", auth="user", website=True)
    def expense_category_edit(self, category_id, **kw):
        category = self._category_model().browse(category_id)
        if not category.exists() or not category.can_manage(request.env.user):
            return request.redirect("/my/apps/expenses/categories")
        parents = self._category_model().search(self._category_domain(request.env.user, category_type=category.category_type, parent_only=True) + [("id", "!=", category.id)], order="sequence, id")
        return request.render("dt_expense.portal_expense_category_form", self._base_values(page_title="Sửa danh mục", category=category, category_type=category.category_type, parents=parents, selected_parent=category.parent_id, back_url="/my/apps/expenses/categories?category_type=%s" % category.category_type))

    @http.route("/my/apps/expenses/categories/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_categories_save(self, category_id=None, name="", icon="💸", category_type="expense", parent_id=None, sequence="10", note="", apply_next_month_rule="", count_in_expense="", **kw):
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
            "count_in_expense": count_in_expense == "on",
            "user_id": user.id,
        }
        image_file = request.httprequest.files.get("image")
        if image_file and image_file.filename:
            vals["image"] = base64.b64encode(image_file.read())
        if category_id:
            category = self._category_model().browse(self._safe_int(category_id))
            if category.exists() and category.can_manage(user):
                category.write(vals)
        else:
            self._category_model().create(vals)
        return request.redirect("/my/apps/expenses/categories?category_type=%s" % category_type)

    @http.route("/my/apps/expenses/categories/<int:category_id>/delete", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_category_delete(self, category_id, **kw):
        category = self._category_model().browse(category_id)
        if category.exists() and category.can_manage(request.env.user):
            if category.entry_count or category.child_ids:
                category.write({"active": False})
            else:
                category.unlink()
        return request.redirect("/my/apps/expenses/categories?category_type=%s" % (category.category_type or "expense"))

    @http.route("/my/apps/expenses/categories/<int:category_id>/suggestions", type="http", auth="user", website=True)
    def expense_category_suggestions(self, category_id, **kw):
        category = self._category_model().browse(category_id)
        if not category.exists() or not category.can_manage(request.env.user):
            return request.redirect("/my/apps/expenses/categories")
        suggestions = self._suggestion_model().search([("category_id", "=", category.id)], order="sequence, id")
        return request.render("dt_expense.portal_expense_suggestions", self._base_values(page_title="Gợi ý tiêu đề", page_subtitle=category.name, category=category, suggestions=suggestions, page_action_url="/my/apps/expenses/categories/%s/suggestions/new" % category.id, back_url="/my/apps/expenses/categories?category_type=%s" % category.category_type))

    @http.route("/my/apps/expenses/categories/<int:category_id>/suggestions/new", type="http", auth="user", website=True)
    def expense_category_suggestion_new(self, category_id, **kw):
        category = self._category_model().browse(category_id)
        if not category.exists() or not category.can_manage(request.env.user):
            return request.redirect("/my/apps/expenses/categories")
        return request.render("dt_expense.portal_expense_suggestion_form", self._base_values(page_title="Thêm gợi ý", category=category, suggestion=False, back_url=f"/my/apps/expenses/categories/{category.id}/suggestions"))

    @http.route("/my/apps/expenses/suggestions/<int:suggestion_id>/edit", type="http", auth="user", website=True)
    def expense_category_suggestion_edit(self, suggestion_id, **kw):
        suggestion = self._suggestion_model().browse(suggestion_id)
        if not suggestion.exists() or not suggestion.category_id.can_manage(request.env.user):
            return request.redirect("/my/apps/expenses/categories")
        return request.render("dt_expense.portal_expense_suggestion_form", self._base_values(page_title="Sửa gợi ý", category=suggestion.category_id, suggestion=suggestion, back_url=f"/my/apps/expenses/categories/{suggestion.category_id.id}/suggestions"))

    @http.route("/my/apps/expenses/categories/<int:category_id>/suggestions/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_category_suggestion_save(self, category_id, suggestion_id=None, name="", sequence="10", **kw):
        category = self._category_model().browse(category_id)
        if not category.exists() or not category.can_manage(request.env.user):
            return request.redirect("/my/apps/expenses/categories")
        vals = {"category_id": category.id, "name": (name or "").strip() or "Gợi ý mới", "sequence": self._safe_int(sequence, 10)}
        if suggestion_id:
            suggestion = self._suggestion_model().browse(self._safe_int(suggestion_id))
            if suggestion.exists() and suggestion.category_id.id == category.id:
                suggestion.write(vals)
        else:
            self._suggestion_model().create(vals)
        return request.redirect(f"/my/apps/expenses/categories/{category.id}/suggestions")

    @http.route("/my/apps/expenses/suggestions/<int:suggestion_id>/delete", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_category_suggestion_delete(self, suggestion_id, **kw):
        suggestion = self._suggestion_model().browse(suggestion_id)
        back_url = "/my/apps/expenses/categories"
        if suggestion.exists() and suggestion.category_id.can_manage(request.env.user):
            back_url = f"/my/apps/expenses/categories/{suggestion.category_id.id}/suggestions"
            suggestion.unlink()
        return request.redirect(back_url)

    @http.route("/my/apps/expenses/wallets", type="http", auth="user", website=True)
    def expense_wallets(self, **kw):
        user = request.env.user
        wallets = self._wallet_model().search([("user_id", "=", user.id), ("active", "=", True)], order="sequence, id")
        if not wallets:
            wallets = self._wallet_model().get_default_wallet(user)
        return request.render("dt_expense.portal_expense_wallets", self._base_values(page_title="Nguồn tiền", page_subtitle="Momo, ngân hàng, tiền mặt của bạn", wallets=wallets, default_date=date.today().isoformat(), page_action_url="/my/apps/expenses/wallets/new", back_url="/my/apps/expenses", show_balance_toggle=True))

    @http.route("/my/apps/expenses/wallets/new", type="http", auth="user", website=True)
    def expense_wallet_new(self, **kw):
        return request.render("dt_expense.portal_expense_wallet_form", self._base_values(page_title="Tạo nguồn tiền", wallet=False, back_url="/my/apps/expenses/wallets"))

    @http.route("/my/apps/expenses/wallets/<int:wallet_id>/edit", type="http", auth="user", website=True)
    def expense_wallet_edit(self, wallet_id, **kw):
        wallet = self._wallet_model().browse(wallet_id)
        if not wallet.exists() or wallet.user_id.id != request.env.user.id:
            return request.redirect("/my/apps/expenses/wallets")
        return request.render("dt_expense.portal_expense_wallet_form", self._base_values(page_title="Sửa nguồn tiền", wallet=wallet, back_url="/my/apps/expenses/wallets"))

    @http.route("/my/apps/expenses/wallets/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_wallet_save(self, wallet_id=None, name="", icon="💳", opening_balance="0", sequence="10", note="", **kw):
        user = request.env.user
        vals = {"name": (name or "").strip() or "Nguồn tiền", "icon": (icon or "💳").strip(), "opening_balance": self._parse_money(opening_balance), "sequence": self._safe_int(sequence, 10), "note": (note or "").strip(), "user_id": user.id}
        if wallet_id:
            wallet = self._wallet_model().browse(self._safe_int(wallet_id))
            if wallet.exists() and wallet.user_id.id == user.id:
                wallet.write(vals)
        else:
            self._wallet_model().create(vals)
        return request.redirect("/my/apps/expenses/wallets")

    @http.route("/my/apps/expenses/wallets/<int:wallet_id>/delete", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_wallet_delete(self, wallet_id, **kw):
        wallet = self._wallet_model().browse(wallet_id)
        if wallet.exists() and wallet.user_id.id == request.env.user.id:
            if wallet.entry_count:
                wallet.write({"active": False})
            else:
                wallet.unlink()
        return request.redirect("/my/apps/expenses/wallets")

    @http.route("/my/apps/expenses/wallets/<int:wallet_id>", type="http", auth="user", website=True)
    def expense_wallet_view(self, wallet_id, **kw):
        wallet = self._wallet_model().browse(wallet_id)
        if not wallet.exists() or wallet.user_id.id != request.env.user.id:
            return request.redirect("/my/apps/expenses/wallets")
        summary = self._wallet_summary(wallet)
        values = self._base_values(page_title=wallet.name, page_subtitle="%s giao dịch" % wallet.entry_count, wallet=wallet, page_action_url="/my/apps/expenses/wallets/%s/edit" % wallet.id, show_balance_toggle=True, back_url="/my/apps/expenses/wallets")
        values.update(summary)
        return request.render("dt_expense.portal_expense_wallet_view", values)

    @http.route("/my/apps/expenses/wallets/<int:wallet_id>/set_primary", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_wallet_set_primary(self, wallet_id, **kw):
        wallet = self._wallet_model().browse(wallet_id)
        if wallet.exists() and wallet.user_id.id == request.env.user.id:
            wallet.write({"is_primary": True})
        return request.redirect("/my/apps/expenses/wallets")

    @http.route("/my/apps/expenses/wallets/transfer", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_wallet_transfer(self, from_wallet_id=None, to_wallet_id=None, amount="0", transfer_date="", note="", **kw):
        user = request.env.user
        from_wallet = self._wallet_model().browse(self._safe_int(from_wallet_id))
        to_wallet = self._wallet_model().browse(self._safe_int(to_wallet_id))
        transfer_amount = abs(self._parse_money(amount))
        if (from_wallet.exists() and from_wallet.user_id.id == user.id
                and to_wallet.exists() and to_wallet.user_id.id == user.id
                and from_wallet.id != to_wallet.id and transfer_amount):
            entry_model = self._entry_model()
            transfer_date_value = self._parse_date(transfer_date, date.today())
            note_clean = (note or "").strip()
            leg_out = entry_model.create({
                "name": note_clean or "Chuyển đến %s" % to_wallet.name,
                "entry_type": "transfer",
                "transfer_flow": "transfer_out",
                "wallet_id": from_wallet.id,
                "amount": transfer_amount,
                "currency_id": entry_model._default_currency_id(),
                "expense_date": transfer_date_value,
                "accounting_month": transfer_date_value.replace(day=1),
                "user_id": user.id,
                "note": note_clean,
            })
            leg_in = entry_model.create({
                "name": note_clean or "Chuyển từ %s" % from_wallet.name,
                "entry_type": "transfer",
                "transfer_flow": "transfer_in",
                "wallet_id": to_wallet.id,
                "amount": transfer_amount,
                "currency_id": entry_model._default_currency_id(),
                "expense_date": transfer_date_value,
                "accounting_month": transfer_date_value.replace(day=1),
                "user_id": user.id,
                "note": note_clean,
            })
            leg_out.write({"transfer_pair_id": leg_in.id})
            leg_in.write({"transfer_pair_id": leg_out.id})
        return request.redirect("/my/apps/expenses/wallets")

    @http.route("/my/apps/expenses/wallets/transfer/<int:entry_id>/delete", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_wallet_transfer_delete(self, entry_id, **kw):
        entry = self._entry_model().browse(entry_id)
        if entry.exists() and entry.user_id.id == request.env.user.id and entry.entry_type == "transfer":
            (entry | entry.transfer_pair_id).unlink()
        return request.redirect("/my/apps/expenses/wallets")

    @http.route("/my/apps/expenses/debts", type="http", auth="user", website=True)
    def expense_debts(self, **kw):
        user = request.env.user
        states = [s for s in request.httprequest.args.getlist("state") if s in ("open", "paid")]
        debt_types = [t for t in request.httprequest.args.getlist("debt_type") if t in ("lend", "borrow")]
        wallet_value = self._safe_int(request.httprequest.args.get("wallet_id"))
        domain = [("user_id", "=", user.id)]
        if states:
            domain.append(("state", "in", states))
        if debt_types:
            domain.append(("debt_type", "in", debt_types))
        if wallet_value:
            domain.append(("wallet_id", "=", wallet_value))
        debts = self._debt_model().search(domain, order="state, debt_date desc, id desc")
        open_debts = self._debt_model().search([("user_id", "=", user.id), ("state", "=", "open")])
        lend_total = sum(debt.remaining_amount for debt in open_debts if debt.debt_type == "lend")
        borrow_total = sum(debt.remaining_amount for debt in open_debts if debt.debt_type == "borrow")
        return request.render("dt_expense.portal_expense_debts", self._base_values(page_title="Sổ nợ", debts=debts, states=states, debt_types=debt_types, lend_total_label=self._format_money(lend_total), borrow_total_label=self._format_money(borrow_total), page_action_url="/my/apps/expenses/debts/new", show_balance_toggle=True, back_url="/my/apps/expenses"))

    @http.route("/my/apps/expenses/debts/new", type="http", auth="user", website=True)
    def expense_debt_new(self, debt_type="lend", plan_id=None, **kw):
        user = request.env.user
        debt_type = debt_type if debt_type in ("lend", "borrow") else "lend"
        wallets = self._wallet_model().search([("user_id", "=", user.id), ("active", "=", True)], order="sequence, id") or self._wallet_model().get_default_wallet(user)
        plans = self._plan_model().search([("user_id", "=", user.id), ("state", "!=", "archived")], order="create_date desc")
        plan = self._resolve_plan(user, plan_id)
        return request.render("dt_expense.portal_expense_debt_form", self._base_values(page_title="Tạo khoản nợ", debt=False, debt_type=debt_type, wallets=wallets, media_items=request.env["dt.media"].sudo().browse(), default_date=date.today().isoformat(), plans=plans, plan=plan, back_url="/my/apps/expenses/debts"))

    @http.route("/my/apps/expenses/debts/<int:debt_id>/edit", type="http", auth="user", website=True)
    def expense_debt_edit(self, debt_id, **kw):
        debt = self._debt_model().browse(debt_id)
        if not debt.exists() or debt.user_id.id != request.env.user.id:
            return request.redirect("/my/apps/expenses/debts")
        wallets = self._wallet_model().search([("user_id", "=", request.env.user.id), ("active", "=", True)], order="sequence, id")
        plans = self._plan_model().search([("user_id", "=", request.env.user.id), ("state", "!=", "archived")], order="create_date desc")
        return request.render("dt_expense.portal_expense_debt_form", self._base_values(page_title="Sửa khoản nợ", debt=debt, debt_type=debt.debt_type, wallets=wallets, media_items=debt.get_media_items(), default_date=debt.debt_date.isoformat(), plans=plans, plan=debt.plan_id, back_url="/my/apps/expenses/debts"))

    @http.route("/my/apps/expenses/debts/counterparty_suggestions", type="http", auth="user", website=True)
    def expense_debt_counterparty_suggestions(self, q="", **kw):
        user = request.env.user
        domain = [("user_id", "=", user.id), ("active", "=", True)]
        query = (q or "").strip()
        if query:
            domain.append(("name", "ilike", query))
        contacts = self._contact_model().search(domain, order="used_count desc, last_used_at desc, name asc", limit=12)
        rows = [{"label": c.name} for c in contacts]
        return request.make_response(json.dumps(rows), headers=[("Content-Type", "application/json")])

    @http.route("/my/apps/expenses/debts/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_debt_save(self, debt_id=None, debt_type="lend", counterparty="", amount="0", wallet_id=None, debt_date="", due_date="", name="", note="", plan_id=None, **kw):
        user = request.env.user
        debt_type = debt_type if debt_type in ("lend", "borrow") else "lend"
        name_clean = (name or "").strip()
        if not name_clean:
            fallback = ("/my/apps/expenses/debts/%s/edit" % debt_id) if debt_id else ("/my/apps/expenses/debts/new?debt_type=%s" % debt_type)
            return request.redirect(fallback)
        wallet = self._wallet_model().browse(self._safe_int(wallet_id)) if wallet_id else self._wallet_model().get_default_wallet(user)
        if not wallet.exists() or wallet.user_id.id != user.id:
            wallet = self._wallet_model().get_default_wallet(user)
        plan = self._resolve_plan(user, plan_id)
        vals = {
            "debt_type": debt_type,
            "counterparty": (counterparty or "").strip() or "Người liên quan",
            "amount": abs(self._parse_money(amount)),
            "wallet_id": wallet.id,
            "debt_date": self._parse_date(debt_date, date.today()),
            "due_date": self._parse_date(due_date),
            "name": name_clean,
            "note": (note or "").strip(),
            "user_id": user.id,
            "plan_id": plan.id if plan else False,
        }
        if debt_id:
            debt = self._debt_model().browse(self._safe_int(debt_id))
            if not debt.exists() or debt.user_id.id != user.id:
                debt = self._debt_model().browse()
            else:
                debt.write(vals)
        else:
            debt = self._debt_model().create(vals)
        if debt:
            request.env["dt.media"].sudo().create_from_uploads(request.httprequest.files.getlist("media_files"), debt, owner_user=user)
        return request.redirect(("/my/apps/expenses/plans/%s" % plan.id) if plan else "/my/apps/expenses/debts")

    @http.route("/my/apps/expenses/debts/<int:debt_id>/payment/new", type="http", auth="user", website=True)
    def expense_debt_payment_new(self, debt_id, **kw):
        user = request.env.user
        debt = self._debt_model().browse(debt_id)
        if not debt.exists() or debt.user_id.id != user.id or debt.state != "open":
            return request.redirect("/my/apps/expenses/debts")
        label = "Thu nợ" if debt.debt_type == "lend" else "Trả nợ"
        return request.render("dt_expense.portal_expense_debt_payment_form", self._base_values(page_title=label, debt=debt, default_date=date.today().isoformat(), back_url="/my/apps/expenses/debts"))

    @http.route("/my/apps/expenses/debts/<int:debt_id>/payment", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_debt_payment(self, debt_id, payment_amount="0", payment_date="", payment_note="", **kw):
        user = request.env.user
        debt = self._debt_model().browse(debt_id)
        if debt.exists() and debt.user_id.id == user.id and debt.state == "open":
            entry = debt.register_payment(self._parse_money(payment_amount), payment_date=self._parse_date(payment_date, date.today()), wallet=debt.wallet_id, note=(payment_note or "").strip())
            if entry:
                request.env["dt.media"].sudo().create_from_uploads(request.httprequest.files.getlist("media_files"), entry, owner_user=user)
        return request.redirect("/my/apps/expenses/debts")

    @http.route("/my/apps/expenses/debts/<int:debt_id>/cancel", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_debt_cancel(self, debt_id, **kw):
        debt = self._debt_model().browse(debt_id)
        if debt.exists() and debt.user_id.id == request.env.user.id:
            debt.action_cancel()
        return request.redirect("/my/apps/expenses/debts")

    @http.route("/my/apps/expenses/plans", type="http", auth="user", website=True)
    def expense_plans(self, **kw):
        user = request.env.user
        states = [s for s in request.httprequest.args.getlist("state") if s in ("active", "done", "archived")]
        domain = [("user_id", "=", user.id)]
        if states:
            domain.append(("state", "in", states))
        plans = self._plan_model().search(domain, order="create_date desc, id desc")
        plan_rows = [{"plan": plan, "summary": self._plan_summary(plan)} for plan in plans]
        return request.render("dt_expense.portal_expense_plans", self._base_values(page_title="Kế hoạch", plan_rows=plan_rows, states=states, page_action_url="/my/apps/expenses/plans/new", show_balance_toggle=True, back_url="/my/apps/expenses"))

    @http.route("/my/apps/expenses/plans/new", type="http", auth="user", website=True)
    def expense_plan_new(self, **kw):
        return request.render("dt_expense.portal_expense_plan_form", self._base_values(page_title="Tạo kế hoạch", plan=False, media_items=request.env["dt.media"].sudo().browse(), back_url="/my/apps/expenses/plans"))

    @http.route("/my/apps/expenses/plans/<int:plan_id>/edit", type="http", auth="user", website=True)
    def expense_plan_edit(self, plan_id, **kw):
        plan = self._plan_model().browse(plan_id)
        if not plan.exists() or not plan.can_manage(request.env.user):
            return request.redirect("/my/apps/expenses/plans")
        return request.render("dt_expense.portal_expense_plan_form", self._base_values(page_title="Sửa kế hoạch", plan=plan, back_url="/my/apps/expenses/plans/%s" % plan.id))

    @http.route("/my/apps/expenses/plans/save", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_plan_save(self, plan_id=None, name="", note="", budget_amount="0", target_date="", state="active", **kw):
        user = request.env.user
        name_clean = (name or "").strip()
        if not name_clean:
            fallback = ("/my/apps/expenses/plans/%s/edit" % plan_id) if plan_id else "/my/apps/expenses/plans/new"
            return request.redirect(fallback)
        vals = {
            "name": name_clean,
            "note": (note or "").strip(),
            "budget_amount": abs(self._parse_money(budget_amount)),
            "target_date": self._parse_date(target_date),
            "user_id": user.id,
        }
        image_file = request.httprequest.files.get("image")
        if image_file and image_file.filename:
            vals["image"] = base64.b64encode(image_file.read())
        if plan_id:
            plan = self._plan_model().browse(self._safe_int(plan_id))
            if plan.exists() and plan.can_manage(user):
                if state in ("active", "done", "archived"):
                    vals["state"] = state
                plan.write(vals)
        else:
            plan = self._plan_model().create(vals)
        return request.redirect("/my/apps/expenses/plans")

    @http.route("/my/apps/expenses/plans/<int:plan_id>", type="http", auth="user", website=True)
    def expense_plan_view(self, plan_id, **kw):
        plan = self._plan_model().browse(plan_id)
        if not plan.exists() or not plan.can_manage(request.env.user):
            return request.redirect("/my/apps/expenses/plans")
        summary = self._plan_summary(plan)
        entries = self._entry_model().search([("plan_id", "=", plan.id), ("active", "=", True)], order="expense_date desc, id desc")
        report = self._build_report(entries.filtered(lambda e: e.entry_type == "expense"), group_mode="parent", link_params={"plan_id": plan.id})
        wallets = self._wallet_model().search([("user_id", "=", plan.user_id.id), ("active", "=", True)], order="sequence, id")
        plan_return_to = "/my/apps/expenses/plans/%s" % plan.id
        return_to_encoded = urlquote(plan_return_to, safe="")
        values = self._base_values(page_title=plan.name, page_subtitle=dict(plan._fields["state"].selection).get(plan.state), plan=plan, entries=entries, scope="mine", return_to=plan_return_to, return_to_encoded=return_to_encoded, report=report, wallets=wallets, page_action_url="/my/apps/expenses/new?plan_id=%s" % plan.id, show_balance_toggle=True, back_url="/my/apps/expenses/plans")
        values.update(summary)
        return request.render("dt_expense.portal_expense_plan_view", values)

    @http.route("/my/apps/expenses/plans/<int:plan_id>/fund", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def expense_plan_fund(self, plan_id, direction="in", amount="0", wallet_id=None, note="", **kw):
        user = request.env.user
        plan = self._plan_model().browse(plan_id)
        wallet = self._wallet_model().browse(self._safe_int(wallet_id)) if wallet_id else self._wallet_model().get_default_wallet(user)
        fund_amount = abs(self._parse_money(amount))
        if plan.exists() and plan.can_manage(user) and wallet.exists() and wallet.user_id.id == user.id and fund_amount:
            flow = "fund_in" if direction == "in" else "fund_out"
            note_clean = (note or "").strip()
            self._entry_model().create({
                "name": note_clean or ("Ứng quỹ · %s" % plan.name if flow == "fund_in" else "Rút quỹ · %s" % plan.name),
                "entry_type": "plan_fund",
                "plan_flow": flow,
                "plan_id": plan.id,
                "wallet_id": wallet.id,
                "amount": fund_amount,
                "currency_id": self._entry_model()._default_currency_id(),
                "expense_date": date.today(),
                "accounting_month": date.today().replace(day=1),
                "user_id": user.id,
                "note": note_clean,
            })
        return request.redirect("/my/apps/expenses/plans/%s" % plan_id)

    @http.route("/my/apps/expenses/history", type="http", auth="user", website=True)
    def expense_history(self, scope="mine", search="", member_id="", date_from="", date_to="", entry_type="", parent_id="", category_id="", wallet_id="", debt_flow="", debt_id="", plan_id="", **kw):
        user = request.env.user
        scope = scope if scope in ("mine", "family") else "mine"
        member_value = self._safe_int(member_id)
        member_ids_value = self._safe_int_list(request.httprequest.args.getlist("member_ids"))
        parent_value = self._safe_int(parent_id)
        category_value = self._safe_int(category_id)
        wallet_value = self._safe_int(wallet_id)
        debt_id_value = self._safe_int(debt_id)
        plan_value = self._safe_int(plan_id)
        today = date.today()
        if not date_from and not date_to:
            start, end, month_label = self._period_range("month", today)
            date_from = start.strftime("%Y-%m-%d")
            date_to = end.strftime("%Y-%m-%d")
        domain = self._activity_domain(user, scope=scope, search=search, member_id=member_value, member_ids=member_ids_value, date_from=self._parse_date(date_from), date_to=self._parse_date(date_to), entry_type=entry_type, parent_id=parent_value, category_id=category_value, wallet_id=wallet_value, debt_flow=debt_flow, debt_id=debt_id_value, plan_id=plan_value)
        all_entries = self._entry_model().search(domain, order="expense_date desc, id desc")
        total_income, total_expense, total_net = self._cash_report_buckets(all_entries)
        per_page = 20
        entries = all_entries[:per_page]
        has_more = len(all_entries) > per_page
        parents = self._category_model().search(self._category_domain(user, parent_only=True), order="category_type, sequence, id")
        children = self._category_model().search(self._category_domain(user, leaf_only=True), order="sequence, id")
        family_members = request.env["res.users"].sudo().browse(self._visible_user_ids(user, "family"))
        wallets = self._wallet_model().search(self._wallet_domain(user, scope), order="sequence, id")
        plans = self._plan_model().search([("user_id", "=", user.id)], order="create_date desc")
        df = self._parse_date(date_from)
        dt = self._parse_date(date_to)
        period_kind = "month"
        if df and dt:
            last_day = calendar.monthrange(df.year, df.month)[1]
            if df.month == 1 and df.day == 1 and dt.month == 12 and dt.day == 31 and df.year == dt.year:
                period_kind = "year"
                month_label = "Năm %d" % df.year
            elif (dt - df).days == 6 and df.weekday() == 0:
                iso_year, iso_week, _ = df.isocalendar()
                period_kind = "week"
                month_label = "Tuần %d · %d" % (iso_week, iso_year)
            elif df.day == 1 and dt.day == last_day and df.month == dt.month and df.year == dt.year:
                month_label = df.strftime("Tháng %-m, %Y")
            else:
                month_label = "%s — %s" % (df.strftime("%d/%m"), dt.strftime("%d/%m/%Y"))
        else:
            month_label = df.strftime("Tháng %-m, %Y") if df else ""
        member_filter_active = (scope == 'family' and (member_ids_value or member_id)) and 1 or 0
        filter_count = len([x for x in [search, member_filter_active, entry_type, parent_id, category_id, wallet_id, plan_id] if x])
        qs = request.httprequest.query_string.decode() if request.httprequest.query_string else ""
        return_to = "/my/apps/expenses/history" + (("?" + qs) if qs else "")
        return_to_encoded = urlquote(return_to, safe="")
        return request.render("dt_expense.portal_expense_history", self._base_values(page_title="Lịch sử giao dịch", entries=entries, return_to=return_to, has_more=has_more, next_offset=per_page, month_label=month_label, search=search, scope=scope, member_id=member_value, selected_member_ids=member_ids_value, family_members=family_members, date_from=date_from, date_to=date_to, entry_type=entry_type, debt_flow=debt_flow, debt_id=debt_id_value, parent_id=parent_value, category_id=category_value, wallet_id=wallet_value, plan_id=plan_value, plans=plans, parent_categories=parents, child_categories=children, wallets=wallets, total_income_label=self._format_money(total_income, short=False), total_expense_label=self._format_money(total_expense, short=False), total_net_label=self._format_money(total_net, show_plus=True, short=False), filter_count=filter_count, back_url="/my/apps/expenses", page_action_url="/my/apps/expenses/new", return_to_encoded=return_to_encoded, period_kind=period_kind, show_balance_toggle=True))

    @http.route("/my/apps/expenses/history/entries", type="http", auth="user", website=True)
    def expense_history_entries(self, offset=0, scope="mine", search="", member_id="", date_from="", date_to="", entry_type="", parent_id="", category_id="", wallet_id="", debt_flow="", debt_id="", plan_id="", **kw):
        user = request.env.user
        scope = scope if scope in ("mine", "family") else "mine"
        offset_value = max(0, self._safe_int(str(offset), 0))
        per_page = 20
        member_ids_value = self._safe_int_list(request.httprequest.args.getlist("member_ids"))
        domain = self._activity_domain(user, scope=scope, search=search, member_id=self._safe_int(member_id), member_ids=member_ids_value, date_from=self._parse_date(date_from), date_to=self._parse_date(date_to), entry_type=entry_type, parent_id=self._safe_int(parent_id), category_id=self._safe_int(category_id), wallet_id=self._safe_int(wallet_id), debt_flow=debt_flow, debt_id=self._safe_int(debt_id), plan_id=self._safe_int(plan_id))
        all_entries = self._entry_model().search(domain, order="expense_date desc, id desc")
        total = len(all_entries)
        entries = all_entries[offset_value:offset_value + per_page]
        has_more = offset_value + per_page < total
        qs = request.httprequest.query_string.decode() if request.httprequest.query_string else ""
        history_qs = qs.replace("offset=" + str(offset_value) + "&", "").replace("&offset=" + str(offset_value), "").replace("offset=" + str(offset_value), "")
        return_to = "/my/apps/expenses/history" + (("?" + history_qs) if history_qs else "")
        return_to_encoded = urlquote(return_to, safe="")
        html = request.env["ir.ui.view"]._render_template("dt_expense.portal_expense_history_entries_partial", {"entries": entries, "scope": scope, "request": request, "return_to": return_to, "return_to_encoded": return_to_encoded})
        if isinstance(html, bytes):
            html = html.decode("utf-8")
        return request.make_response(json.dumps({"html": html, "has_more": has_more, "next_offset": offset_value + per_page}), headers=[("Content-Type", "application/json")])

    @http.route("/my/apps/expenses/reports", type="http", auth="user", website=True)
    def expense_reports(self, period="month", anchor="", scope="family", group_mode="parent", **kw):
        user = request.env.user
        period = period if period in ("week", "month", "quarter", "year") else "month"
        scope = scope if scope in ("mine", "family") else "family"
        anchor_date = self._parse_date(anchor, date.today())
        start, end, period_label = self._period_range(period, anchor_date)
        if period == "week":
            report_domain = [("expense_date", ">=", start), ("expense_date", "<=", end)]
        else:
            report_domain = [("accounting_month", ">=", start.replace(day=1)), ("accounting_month", "<=", end.replace(day=1))]
        report_domain = [("active", "=", True), ("user_id", "in", self._visible_user_ids(user, scope))] + report_domain
        entries = self._entry_model().search(report_domain, order="expense_date desc, id desc")
        group_mode = group_mode if group_mode in ("parent", "child") else "parent"
        report = self._build_report(entries, group_mode=group_mode, link_params={
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "scope": scope,
        })
        return request.render("dt_expense.portal_expense_report", self._base_values(page_title="Báo cáo chi tiêu", page_subtitle="Phân bổ theo danh mục · %s" % period_label, period=period, anchor=anchor_date.isoformat(), scope=scope, group_mode=group_mode, period_label=period_label, report=report, expense_total_label=self._format_money(report["total"], short=False), back_url="/my/apps/expenses", show_balance_toggle=True))

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
        return request.make_response(json.dumps(rows[:12]), headers=[("Content-Type", "application/json")])
