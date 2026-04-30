/** @odoo-module **/

(function () {
    function syncExpenseForm(form) {
        const entryTypeSelect = form.querySelector('[data-entry-type-select="1"]');
        const categoryField = form.querySelector('[data-category-field="1"]');
        const categorySelect = form.querySelector('[data-category-select="1"]');
        const adjustmentField = form.querySelector('[data-adjustment-only="1"]');
        if (!entryTypeSelect || !categoryField || !categorySelect || !adjustmentField) {
            return;
        }

        const updateState = function () {
            const currentType = entryTypeSelect.value || 'expense';
            const isAdjustment = currentType === 'adjustment';
            categoryField.style.display = isAdjustment ? 'none' : '';
            adjustmentField.style.display = isAdjustment ? '' : 'none';
            categorySelect.required = !isAdjustment;
            let hasSelectedVisibleOption = false;
            Array.from(categorySelect.options).forEach(function (option, index) {
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
            if (isAdjustment) {
                categorySelect.value = '';
            } else if (!hasSelectedVisibleOption) {
                categorySelect.value = '';
            }
        };

        entryTypeSelect.addEventListener('change', updateState);
        updateState();
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('form[data-expense-form="1"]').forEach(syncExpenseForm);
    });
})();
