# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FamilyExpenseTitleSuggestion(models.Model):
    _name = "dt.expense.title.suggestion"
    _description = "Family Expense Title Suggestion"
    _order = "sequence, is_manual desc, usage_count desc, last_used_at desc, id desc"

    name = fields.Char(required=True, string="Tiêu đề gợi ý")
    normalized_name = fields.Char(index=True)
    category_id = fields.Many2one("dt.expense.category", required=True, ondelete="cascade", index=True)
    category_type = fields.Selection(related="category_id.category_type", store=True, index=True)
    scope = fields.Selection(related="category_id.scope", store=True, index=True)
    owner_user_id = fields.Many2one(related="category_id.user_id", store=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    is_manual = fields.Boolean(default=True, string="Cấu hình thủ công")
    usage_count = fields.Integer(default=0)
    last_used_at = fields.Datetime()

    _sql_constraints = [
        (
            "expense_title_suggestion_unique",
            "unique(category_id, normalized_name)",
            "Tiêu đề gợi ý đã tồn tại trong danh mục này.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        normalized = []
        for vals in vals_list:
            vals = dict(vals)
            vals["normalized_name"] = self._normalize_name(vals.get("name"))
            normalized.append(vals)
        return super().create(normalized)

    def write(self, vals):
        vals = dict(vals)
        if "name" in vals:
            vals["normalized_name"] = self._normalize_name(vals.get("name"))
        return super().write(vals)

    @api.model
    def _normalize_name(self, name):
        return " ".join((name or "").strip().lower().split())

    @api.model
    def suggestions_for_portal(self, category, user=None, query="", limit=8):
        user = user or self.env.user
        if not category or not category.exists() or not category.can_access(user=user):
            return []
        query = (query or "").strip()
        domain = [("category_id", "=", category.id), ("active", "=", True)]
        if query:
            domain.append(("name", "ilike", query))
        suggestions = self.search(domain, limit=max(limit * 3, 20))
        ordered = sorted(
            suggestions,
            key=lambda row: (
                0 if row.is_manual else 1,
                -(row.usage_count or 0),
                row.sequence or 0,
                row.name or "",
            ),
        )
        rows = []
        seen = set()
        q = self._normalize_name(query)
        for suggestion in ordered:
            key = suggestion.normalized_name or self._normalize_name(suggestion.name)
            if not key or key in seen:
                continue
            seen.add(key)
            score = 0
            if q:
                if key.startswith(q):
                    score += 100
                if q in key:
                    score += 50
            if suggestion.is_manual:
                score += 30
            score += min(suggestion.usage_count or 0, 20)
            rows.append({
                "id": suggestion.id,
                "label": suggestion.name,
                "score": score,
                "is_manual": suggestion.is_manual,
                "usage_count": suggestion.usage_count or 0,
            })
        rows.sort(key=lambda row: (-row["score"], -row["usage_count"], row["label"]))
        return rows[:limit]

    @api.model
    def touch_history(self, category, title, user=None):
        user = user or self.env.user
        clean_title = (title or "").strip()
        if not clean_title or not category or not category.exists() or not category.can_access(user=user):
            return False
        normalized = self._normalize_name(clean_title)
        suggestion = self.search([
            ("category_id", "=", category.id),
            ("normalized_name", "=", normalized),
        ], limit=1)
        now = fields.Datetime.now()
        if suggestion:
            suggestion.write({
                "name": clean_title,
                "usage_count": (suggestion.usage_count or 0) + 1,
                "last_used_at": now,
            })
            return suggestion
        return self.create({
            "name": clean_title,
            "category_id": category.id,
            "sequence": 999,
            "is_manual": False,
            "usage_count": 1,
            "last_used_at": now,
        })
