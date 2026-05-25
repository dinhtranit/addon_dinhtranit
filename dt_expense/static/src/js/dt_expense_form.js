/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

function monthStart(value) {
    if (!value) { return ""; }
    const parts = value.split("-");
    if (parts.length !== 3) { return value; }
    return `${parts[0]}-${parts[1]}-01`;
}

function nextMonth(value) {
    if (!value) { return ""; }
    const [year, month] = value.split("-").map((item) => parseInt(item, 10));
    if (!year || !month) { return value; }
    if (month === 12) { return `${year + 1}-01-01`; }
    return `${year}-${String(month + 1).padStart(2, "0")}-01`;
}

publicWidget.registry.DTExpenseForm = publicWidget.Widget.extend({
    selector: 'form[data-expense-form="1"]',
    events: {
        'click [data-entry-tab]': '_onTabClick',
        'click [data-category-id]': '_onQuickCategoryClick',
        'click [data-show-all-categories]': '_showAllCategories',
        'click [data-hide-all-categories]': '_hideAllCategories',
        'change [data-entry-type-hidden="1"]': '_updateState',
        'change [data-category-select="1"]': '_onCategoryChange',
        'input [data-title-input="1"]': '_onTitleInput',
        'focusin [data-title-input="1"]': '_onTitleFocus',
        'change [data-expense-date="1"]': '_onDateChange',
        'input input[name="amount"]': '_updateSavePreview',
    },

    start() {
        this.entryTypeInput = this.el.querySelector('[data-entry-type-hidden="1"]');
        this.categoryFields = this.el.querySelectorAll('[data-category-field="1"]');
        this.categorySelect = this.el.querySelector('[data-category-select="1"]');
        this.adjustmentField = this.el.querySelector('[data-adjustment-only="1"]');
        this.titleInput = this.el.querySelector('[data-title-input="1"]');
        this.titleList = this.el.querySelector('[data-title-suggestion-list="1"]');
        this.expenseDate = this.el.querySelector('[data-expense-date="1"]');
        this.accountingMonth = this.el.querySelector('[data-accounting-month="1"]');
        this.savePreview = this.el.querySelector('[data-save-amount-preview="1"]');
        this.allCategories = this.el.querySelector('[data-all-categories="1"]');
        this._suggestionRequest = 0;
        this._updateState();
        this._updateSavePreview();
        return this._super(...arguments);
    },

    _onTabClick(ev) {
        ev.preventDefault();
        const tab = ev.currentTarget.dataset.entryTab || 'expense';
        if (this.entryTypeInput) { this.entryTypeInput.value = tab; }
        this.el.querySelectorAll('[data-entry-tab]').forEach((button) => {
            button.classList.toggle('is-active', button.dataset.entryTab === tab);
        });
        this._updateState();
    },

    _showAllCategories(ev) {
        ev.preventDefault();
        if (this.allCategories) { this.allCategories.classList.remove('d-none'); }
    },

    _hideAllCategories(ev) {
        ev.preventDefault();
        if (this.allCategories) { this.allCategories.classList.add('d-none'); }
    },

    _onQuickCategoryClick(ev) {
        ev.preventDefault();
        const button = ev.currentTarget;
        const categoryId = button.dataset.categoryId;
        const entryType = button.dataset.entryType;
        if (entryType && this.entryTypeInput) {
            this.entryTypeInput.value = entryType;
            this.el.querySelectorAll('[data-entry-tab]').forEach((tab) => tab.classList.toggle('is-active', tab.dataset.entryTab === entryType));
        }
        if (this.categorySelect && categoryId) {
            this.categorySelect.value = categoryId;
            this.el.querySelectorAll('[data-category-id]').forEach((chip) => chip.classList.toggle('is-active', chip.dataset.categoryId === categoryId));
        }
        if (this.allCategories && button.closest('[data-all-categories]')) { this.allCategories.classList.add('d-none'); }
        this._onCategoryChange();
    },

    _updateState() {
        const currentType = (this.entryTypeInput && this.entryTypeInput.value) || 'expense';
        const isAdjustment = currentType === 'adjustment';
        this.categoryFields.forEach((field) => { field.style.display = isAdjustment ? 'none' : ''; });
        if (this.adjustmentField) { this.adjustmentField.style.display = isAdjustment ? '' : 'none'; }
        if (this.categorySelect) {
            this.categorySelect.required = !isAdjustment;
            Array.from(this.categorySelect.options).forEach((option) => {
                if (!option.value) { option.hidden = false; return; }
                const visible = option.dataset.entryType === currentType;
                option.hidden = !visible;
                if (!visible && option.selected) { option.selected = false; }
            });
            if (isAdjustment) { this.categorySelect.value = ''; }
        }
        this.el.querySelectorAll('[data-category-id]').forEach((chip) => {
            chip.hidden = !isAdjustment && chip.dataset.entryType !== currentType;
            chip.classList.toggle('is-active', this.categorySelect && chip.dataset.categoryId === this.categorySelect.value);
        });
        this._onDateChange();
        this._refreshSuggestions();
        this._updateSavePreview();
    },

    _onCategoryChange() {
        if (this.categorySelect) {
            const categoryId = this.categorySelect.value;
            this.el.querySelectorAll('[data-category-id]').forEach((chip) => chip.classList.toggle('is-active', chip.dataset.categoryId === categoryId));
        }
        this._onDateChange();
        this._refreshSuggestions(true);
    },

    _onDateChange() {
        if (!this.expenseDate || !this.accountingMonth) { return; }
        const categoryOption = this.categorySelect && this.categorySelect.selectedOptions.length ? this.categorySelect.selectedOptions[0] : null;
        const dateValue = this.expenseDate.value;
        if (!dateValue) { return; }
        const day = parseInt(dateValue.split('-')[2], 10);
        const applyNext = categoryOption && categoryOption.dataset.nextMonthRule === '1';
        this.accountingMonth.value = applyNext && day >= 28 ? nextMonth(dateValue) : monthStart(dateValue);
    },

    _updateSavePreview() {
        if (!this.savePreview) { return; }
        const amountInput = this.el.querySelector('input[name="amount"]');
        const raw = amountInput ? amountInput.value : '';
        this.savePreview.textContent = raw ? raw + 'vnđ' : '0vnđ';
    },

    async _refreshSuggestions(forceShow = false) {
        if (!this.titleInput || !this.titleList || !this.categorySelect) { return; }
        const categoryId = this.categorySelect.value;
        if (!categoryId) {
            this.titleList.innerHTML = '';
            this.titleList.classList.add('d-none');
            return;
        }
        const query = this.titleInput.value || '';
        const requestId = ++this._suggestionRequest;
        const url = `/my/apps/expenses/title_suggestions?category_id=${encodeURIComponent(categoryId)}&q=${encodeURIComponent(query)}`;
        try {
            const response = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            if (!response.ok) { throw new Error('network'); }
            const rows = await response.json();
            if (requestId !== this._suggestionRequest) { return; }
            this.titleList.innerHTML = '';
            rows.forEach((row) => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'dt-autocomplete-item';
                button.textContent = row.label;
                button.addEventListener('click', (event) => {
                    event.preventDefault();
                    this.titleInput.value = row.label;
                    this.titleList.classList.add('d-none');
                });
                this.titleList.appendChild(button);
            });
            this.titleList.classList.toggle('d-none', rows.length === 0 && !forceShow);
        } catch (_e) {
            this.titleList.innerHTML = '';
            this.titleList.classList.add('d-none');
        }
    },

    _onTitleInput() { this._refreshSuggestions(true); },
    _onTitleFocus() { this._refreshSuggestions(true); },
});

publicWidget.registry.DTExpensePage = publicWidget.Widget.extend({
    selector: '.dt-expense-page',
    events: {
        'click [data-balance-card="1"]': '_showBalanceForm',
        'click [data-balance-cancel="1"]': '_hideBalanceForm',
        'click [data-month-nav-dir]': '_onMonthNavClick',
    },

    start() {
        this.balanceForm = this.el.querySelector('[data-balance-form="1"]');
        this.entryList = this.el.querySelector('[data-entry-list="1"]');
        this.sentinel = this.el.querySelector('[data-scroll-sentinel="1"]');
        this.loadingEl = this.el.querySelector('[data-scroll-loading="1"]');
        this._loading = false;
        this._observer = null;
        if (this.sentinel && this.sentinel.dataset.hasMore) { this._initInfiniteScroll(); }
        return this._super(...arguments);
    },

    _showBalanceForm(ev) {
        ev.preventDefault();
        if (!this.balanceForm) { return; }
        this.balanceForm.classList.remove('d-none');
        const input = this.balanceForm.querySelector('input[name="current_amount"]');
        if (input) { input.focus(); }
    },

    _hideBalanceForm(ev) {
        if (ev) { ev.preventDefault(); }
        if (this.balanceForm) { this.balanceForm.classList.add('d-none'); }
    },

    _onMonthNavClick(ev) {
        ev.preventDefault();
        const dir = parseInt(ev.currentTarget.dataset.monthNavDir, 10);
        const nav = this.el.querySelector('[data-month-nav="1"]');
        if (!nav || !nav.dataset.dateFrom) { return; }
        const parts = nav.dataset.dateFrom.split('-').map((n) => parseInt(n, 10));
        let year = parts[0];
        let month = parts[1] + dir;
        if (month > 12) { year += 1; month = 1; }
        if (month < 1) { year -= 1; month = 12; }
        const lastDay = new Date(year, month, 0).getDate();
        const newDateFrom = `${year}-${String(month).padStart(2, '0')}-01`;
        const newDateTo = `${year}-${String(month).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;
        const url = new URL(window.location.href);
        url.searchParams.set('date_from', newDateFrom);
        url.searchParams.set('date_to', newDateTo);
        window.location.href = url.toString();
    },

    _initInfiniteScroll() {
        this._observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && !this._loading) { this._loadMore(); }
        }, { rootMargin: '300px' });
        this._observer.observe(this.sentinel);
    },

    async _loadMore() {
        if (this._loading) { return; }
        const sentinel = this.sentinel;
        if (!sentinel || !sentinel.dataset.hasMore) { return; }
        this._loading = true;
        if (this.loadingEl) { this.loadingEl.classList.remove('d-none'); }
        const params = new URLSearchParams({
            offset: sentinel.dataset.nextOffset || '0',
            scope: sentinel.dataset.scope || 'mine',
            search: sentinel.dataset.search || '',
            member_id: sentinel.dataset.memberId || '',
            date_from: sentinel.dataset.dateFrom || '',
            date_to: sentinel.dataset.dateTo || '',
            entry_type: sentinel.dataset.entryType || '',
            parent_id: sentinel.dataset.parentId || '',
            category_id: sentinel.dataset.categoryId || '',
            wallet_id: sentinel.dataset.walletId || '',
        });
        const memberIdsRaw = sentinel.dataset.memberIds || '';
        if (memberIdsRaw) {
            memberIdsRaw.split(',').filter(Boolean).forEach((id) => params.append('member_ids', id));
        }
        try {
            const response = await fetch(`/my/apps/expenses/history/entries?${params}`, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            if (!response.ok) { throw new Error('network'); }
            const data = await response.json();
            if (data.html && this.entryList) { this.entryList.insertAdjacentHTML('beforeend', data.html); }
            if (data.has_more) { sentinel.dataset.nextOffset = data.next_offset; }
            else {
                delete sentinel.dataset.hasMore;
                if (this._observer) { this._observer.unobserve(sentinel); }
            }
        } catch (_e) {
            // The page remains usable; refresh retries the load.
        } finally {
            this._loading = false;
            if (this.loadingEl) { this.loadingEl.classList.add('d-none'); }
        }
    },
});
