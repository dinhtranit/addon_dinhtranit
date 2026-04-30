/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.DTExpenseForm = publicWidget.Widget.extend({
    selector: 'form[data-expense-form="1"]',
    events: {
        'change [data-entry-type-select="1"]': "_onEntryTypeChange",
    },

    start() {
        this.entryTypeSelect = this.el.querySelector('[data-entry-type-select="1"]');
        this.categoryField = this.el.querySelector('[data-category-field="1"]');
        this.categorySelect = this.el.querySelector('[data-category-select="1"]');
        this.adjustmentField = this.el.querySelector('[data-adjustment-only="1"]');
        this._updateState();
        return this._super(...arguments);
    },

    _onEntryTypeChange() {
        this._updateState();
    },

    _updateState() {
        if (!this.entryTypeSelect || !this.categoryField || !this.categorySelect || !this.adjustmentField) {
            return;
        }

        const currentType = this.entryTypeSelect.value || "expense";
        const isAdjustment = currentType === "adjustment";
        this.categoryField.style.display = isAdjustment ? "none" : "";
        this.adjustmentField.style.display = isAdjustment ? "" : "none";
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
            const optionType = option.dataset.entryType;
            const visible = optionType === currentType;
            option.hidden = !visible;
            if (!visible && option.selected) {
                option.selected = false;
            }
            if (visible && option.selected) {
                hasSelectedVisibleOption = true;
            }
        });

        if (isAdjustment || !hasSelectedVisibleOption) {
            this.categorySelect.value = "";
        }
    },
});
