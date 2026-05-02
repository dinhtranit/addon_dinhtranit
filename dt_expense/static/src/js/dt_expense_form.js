/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

function monthStart(value) {
    if (!value) {
        return "";
    }
    const parts = value.split("-");
    if (parts.length !== 3) {
        return value;
    }
    return `${parts[0]}-${parts[1]}-01`;
}

function nextMonth(value) {
    if (!value) {
        return "";
    }
    const [year, month] = value.split("-").map((item) => parseInt(item, 10));
    if (!year || !month) {
        return value;
    }
    if (month === 12) {
        return `${year + 1}-01-01`;
    }
    return `${year}-${String(month + 1).padStart(2, "0")}-01`;
}

publicWidget.registry.DTExpenseForm = publicWidget.Widget.extend({
    selector: 'form[data-expense-form="1"]',
    events: {
        'click [data-entry-tab]': '_onTabClick',
        'change [data-entry-type-hidden="1"]': '_updateState',
        'change [data-category-select="1"]': '_onCategoryChange',
        'input [data-title-input="1"]': '_onTitleInput',
        'focusin [data-title-input="1"]': '_onTitleFocus',
        'change [data-expense-date="1"]': '_onDateChange',
        'click [data-balance-cancel="1"]': '_hideBalanceForm',
    },

    start() {
        this.entryTypeInput = this.el.querySelector('[data-entry-type-hidden="1"]');
        this.categoryField = this.el.querySelector('[data-category-field="1"]');
        this.categorySelect = this.el.querySelector('[data-category-select="1"]');
        this.adjustmentField = this.el.querySelector('[data-adjustment-only="1"]');
        this.titleInput = this.el.querySelector('[data-title-input="1"]');
        this.titleList = this.el.querySelector('[data-title-suggestion-list="1"]');
        this.expenseDate = this.el.querySelector('[data-expense-date="1"]');
        this.accountingMonth = this.el.querySelector('[data-accounting-month="1"]');
        this._suggestionRequest = 0;
        this._updateState();
        return this._super(...arguments);
    },

    _onTabClick(ev) {
        ev.preventDefault();
        const tab = ev.currentTarget.dataset.entryTab || 'expense';
        if (this.entryTypeInput) {
            this.entryTypeInput.value = tab;
        }
        this.el.querySelectorAll('[data-entry-tab]').forEach((button) => {
            button.classList.toggle('is-active', button.dataset.entryTab === tab);
        });
        this._updateState();
    },

    _updateState() {
        const currentType = (this.entryTypeInput && this.entryTypeInput.value) || 'expense';
        const isAdjustment = currentType === 'adjustment';
        if (this.categoryField) {
            this.categoryField.style.display = isAdjustment ? 'none' : '';
        }
        if (this.adjustmentField) {
            this.adjustmentField.style.display = isAdjustment ? '' : 'none';
        }
        if (this.categorySelect) {
            this.categorySelect.required = !isAdjustment;
            Array.from(this.categorySelect.options).forEach((option) => {
                if (!option.value) {
                    option.hidden = false;
                    return;
                }
                const visible = option.dataset.entryType === currentType;
                option.hidden = !visible;
                if (!visible && option.selected) {
                    option.selected = false;
                }
            });
            if (isAdjustment) {
                this.categorySelect.value = '';
            }
        }
        this._refreshSuggestions();
    },

    _onCategoryChange() {
        this._onDateChange();
        this._refreshSuggestions(true);
    },

    _onDateChange() {
        if (!this.expenseDate || !this.accountingMonth) {
            return;
        }
        const categoryOption = this.categorySelect && this.categorySelect.selectedOptions.length ? this.categorySelect.selectedOptions[0] : null;
        const dateValue = this.expenseDate.value;
        if (!dateValue) {
            return;
        }
        const day = parseInt(dateValue.split('-')[2], 10);
        const applyNext = categoryOption && categoryOption.dataset.nextMonthRule === '1';
        this.accountingMonth.value = applyNext && day >= 28 ? nextMonth(dateValue) : monthStart(dateValue);
    },

    async _refreshSuggestions(forceShow = false) {
        if (!this.titleInput || !this.titleList || !this.categorySelect) {
            return;
        }
        const categoryId = this.categorySelect.value;
        if (!categoryId) {
            this.titleList.innerHTML = '';
            this.titleList.classList.add('d-none');
            return;
        }
        const query = this.titleInput.value || '';
        const requestId = ++this._suggestionRequest;
        const url = `/my/apps/expenses/title_suggestions?category_id=${encodeURIComponent(categoryId)}&q=${encodeURIComponent(query)}`;
        const response = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
        if (!response.ok) {
            this.titleList.innerHTML = '';
            this.titleList.classList.add('d-none');
            return;
        }
        const rows = await response.json();
        if (requestId !== this._suggestionRequest) {
            return;
        }
        this.titleList.innerHTML = '';
        rows.forEach((row) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'dt-autocomplete-item';
            button.textContent = row.label;
            button.addEventListener('click', (ev) => {
                ev.preventDefault();
                this.titleInput.value = row.label;
                this.titleList.classList.add('d-none');
            });
            this.titleList.appendChild(button);
        });
        this.titleList.classList.toggle('d-none', rows.length === 0 && !forceShow);
    },

    _onTitleInput() {
        this._refreshSuggestions(true);
    },

    _onTitleFocus() {
        this._refreshSuggestions(true);
    },
});

publicWidget.registry.DTExpenseBalance = publicWidget.Widget.extend({
    selector: '.dt-section',
    events: {
        'click [data-balance-card="1"]': '_showBalanceForm',
        'click [data-balance-cancel="1"]': '_hideBalanceForm',
        'click [data-filter-toggle="1"]': '_toggleFilter',
    },

    start() {
        this.balanceCard = this.el.querySelector('[data-balance-card="1"]');
        this.balanceForm = this.el.querySelector('[data-balance-form="1"]');
        this.filterPanel = this.el.querySelector('[data-filter-panel="1"]');
        return this._super(...arguments);
    },

    _showBalanceForm(ev) {
        if (!this.balanceCard || !this.balanceForm || ev.target.closest('[data-balance-cancel="1"]')) {
            return;
        }
        this.balanceForm.classList.remove('d-none');
        const input = this.balanceForm.querySelector('input[name="current_amount"]');
        if (input) {
            input.focus();
        }
    },

    _hideBalanceForm(ev) {
        if (ev) {
            ev.preventDefault();
        }
        if (this.balanceForm) {
            this.balanceForm.classList.add('d-none');
        }
    },

    _toggleFilter(ev) {
        ev.preventDefault();
        if (this.filterPanel) {
            this.filterPanel.classList.toggle('d-none');
        }
    },
});
