/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

function debounce(fn, delay = 180) {
    let timer = null;
    return function (...args) {
        window.clearTimeout(timer);
        timer = window.setTimeout(() => fn.apply(this, args), delay);
    };
}

publicWidget.registry.DTExpenseHome = publicWidget.Widget.extend({
    selector: '.dt-section',
    events: {
        'click [data-balance-card="1"]': '_onOpenBalance',
        'keydown [data-balance-card="1"]': '_onBalanceKeydown',
        'click [data-balance-close="1"]': '_onCloseBalance',
        'click [data-toggle-target]': '_onToggleOpen',
        'click [data-toggle-close]': '_onToggleClose',
    },

    start() {
        this.balancePanel = this.el.querySelector('[data-balance-panel="1"]');
        return this._super(...arguments);
    },

    _togglePanel(selector, open) {
        const panel = selector ? this.el.querySelector(selector) : this.balancePanel;
        if (!panel) {
            return;
        }
        panel.classList.toggle('d-none', !open);
        if (open) {
            const focusTarget = panel.querySelector('input, textarea, select, button');
            if (focusTarget) {
                focusTarget.focus();
            }
        }
    },

    _onOpenBalance(ev) {
        if (!this.balancePanel) {
            return;
        }
        if (ev.target.closest('button, a, form, input, select, textarea')) {
            return;
        }
        this._togglePanel(null, true);
    },

    _onBalanceKeydown(ev) {
        if (ev.key === 'Enter' || ev.key === ' ') {
            ev.preventDefault();
            this._togglePanel(null, true);
        }
    },

    _onCloseBalance(ev) {
        ev.preventDefault();
        this._togglePanel(null, false);
    },

    _onToggleOpen(ev) {
        const selector = ev.currentTarget.dataset.toggleTarget;
        if (!selector) {
            return;
        }
        ev.preventDefault();
        this._togglePanel(selector, true);
    },

    _onToggleClose(ev) {
        const selector = ev.currentTarget.dataset.toggleClose;
        if (!selector) {
            return;
        }
        ev.preventDefault();
        this._togglePanel(selector, false);
    },
});

publicWidget.registry.DTExpenseForm = publicWidget.Widget.extend({
    selector: 'form[data-expense-form="1"]',
    events: {
        'change [data-entry-type-select="1"]': '_onEntryTypeChange',
        'change [data-category-select="1"]': '_onCategoryChange',
        'input [data-title-input="1"]': '_onTitleInput',
        'click .dt-title-suggestion': '_onSuggestionClick',
    },

    start() {
        this.entryTypeSelect = this.el.querySelector('[data-entry-type-select="1"]');
        this.categoryField = this.el.querySelector('[data-category-field="1"]');
        this.categorySelect = this.el.querySelector('[data-category-select="1"]');
        this.adjustmentField = this.el.querySelector('[data-adjustment-only="1"]');
        this.privacyField = this.el.querySelector('[data-privacy-field="1"]');
        this.titleField = this.el.querySelector('[data-title-field="1"]');
        this.titleInput = this.el.querySelector('[data-title-input="1"]');
        this.suggestionBox = this.el.querySelector('[data-title-suggestions="1"]');
        this.suggestionUrl = this.titleField ? this.titleField.dataset.suggestionUrl : '';
        this._debouncedFetch = debounce(this._fetchSuggestions.bind(this), 180);
        this._updateState();
        return this._super(...arguments);
    },

    _onEntryTypeChange() {
        this._updateState();
        this._fetchSuggestions();
    },

    _onCategoryChange() {
        this._fetchSuggestions();
    },

    _onTitleInput() {
        this._debouncedFetch();
    },

    _onSuggestionClick(ev) {
        ev.preventDefault();
        const value = ev.currentTarget.dataset.value || ev.currentTarget.textContent || '';
        if (this.titleInput) {
            this.titleInput.value = value.trim();
            this.titleInput.focus();
        }
    },

    _updateState() {
        if (!this.entryTypeSelect || !this.categoryField || !this.categorySelect || !this.adjustmentField) {
            return;
        }
        const currentType = this.entryTypeSelect.value || 'expense';
        const isAdjustment = currentType === 'adjustment';
        this.categoryField.style.display = isAdjustment ? 'none' : '';
        this.adjustmentField.style.display = isAdjustment ? '' : 'none';
        if (this.privacyField) {
            this.privacyField.style.display = isAdjustment ? 'none' : '';
        }
        this.categorySelect.required = !isAdjustment;

        let hasSelectedVisibleOption = false;
        Array.from(this.categorySelect.options).forEach((option, index) => {
            if (!option.value) {
                option.hidden = false;
                if (index === 0) {
                    return;
                }
            }
            if (!option.value) {
                return;
            }
            const visible = option.dataset.entryType === currentType;
            option.hidden = !visible;
            if (!visible && option.selected) {
                option.selected = false;
            }
            if (visible && option.selected) {
                hasSelectedVisibleOption = true;
            }
        });
        if (isAdjustment || !hasSelectedVisibleOption) {
            this.categorySelect.value = '';
        }
        if (this.titleField) {
            this.titleField.style.display = isAdjustment ? 'none' : '';
        }
        if (isAdjustment && this.suggestionBox) {
            this.suggestionBox.innerHTML = '';
        }
    },

    _renderSuggestions(items = []) {
        if (!this.suggestionBox) {
            return;
        }
        this.suggestionBox.innerHTML = '';
        if (!items.length) {
            return;
        }
        items.forEach((item) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'dt-title-suggestion';
            button.dataset.value = item.label;
            button.textContent = item.label;
            this.suggestionBox.appendChild(button);
        });
    },

    async _fetchSuggestions() {
        if (!this.suggestionUrl || !this.categorySelect || !this.titleInput || !this.suggestionBox) {
            return;
        }
        const categoryId = this.categorySelect.value;
        if (!categoryId) {
            this._renderSuggestions([]);
            return;
        }
        const query = (this.titleInput.value || '').trim();
        const url = new URL(this.suggestionUrl, window.location.origin);
        url.searchParams.set('category_id', categoryId);
        url.searchParams.set('q', query);
        url.searchParams.set('limit', '8');
        try {
            const response = await window.fetch(url.toString(), {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (!response.ok) {
                return;
            }
            const payload = await response.json();
            this._renderSuggestions(payload.items || []);
        } catch (_error) {
            // ignore quietly on portal form
        }
    },
});
