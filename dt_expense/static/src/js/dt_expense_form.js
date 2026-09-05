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

function renderSuggestionList(listEl, rows, onPick, forceShow) {
    listEl.innerHTML = "";
    rows.forEach((row) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "dt-autocomplete-item";
        const label = document.createElement("span");
        label.className = "dt-autocomplete-item__label";
        label.textContent = row.label;
        button.appendChild(label);
        // Suggestions learned from past entries carry the amount last used for that
        // description, so the user can see it before picking.
        if (row.amount) {
            const hint = document.createElement("span");
            hint.className = "dt-autocomplete-item__amount";
            hint.textContent = row.amount;
            button.appendChild(hint);
        }
        button.addEventListener("click", (event) => {
            event.preventDefault();
            onPick(row.label, row);
        });
        listEl.appendChild(button);
    });
    listEl.classList.toggle("d-none", rows.length === 0 && !forceShow);
}

function hideListOnBlur(listEl) {
    window.setTimeout(() => {
        if (listEl && !listEl.matches(":hover")) { listEl.classList.add("d-none"); }
    }, 150);
}

publicWidget.registry.DTExpenseForm = publicWidget.Widget.extend({
    selector: 'form[data-expense-form="1"]',
    events: {
        'click [data-entry-tab]': '_onTabClick',
        'click [data-category-id]': '_onQuickCategoryClick',
        'click [data-show-all-categories]': '_showAllCategories',
        'click [data-hide-all-categories]': '_hideAllCategories',
        'click [data-toggle-parent-list="1"]': '_onToggleParentList',
        'change [data-entry-type-hidden="1"]': '_updateState',
        'change [data-category-select="1"]': '_onCategoryChange',
        'input [data-title-input="1"]': '_onTitleInput',
        'focusin [data-title-input="1"]': '_onTitleFocus',
        'focusout [data-title-input="1"]': '_onTitleBlur',
        'click [data-category-dialog-close="1"]': '_hideAllCategories',
        'click [data-cat-clear-parent-filter="1"]': '_onClearParentFilter',
        'input [data-category-search="1"]': '_onCategorySearch',
        'change [data-expense-date="1"]': '_onDateChange',
        'input input[name="amount"]': '_updateSavePreview',
        'submit': '_onFormSubmit',
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
        this.parentListPanel = this.el.querySelector('[data-parent-list="1"]');
        this.parentListToggle = this.el.querySelector('[data-toggle-parent-list="1"]');
        this._suggestionRequest = 0;
        this.quickRow = this.el.querySelector('.dt-quick-cats__row');
        this._snapshotOriginalQuickRow();
        this._snapshotCategoryGroups();
        this._updateState();
        this._rebuildQuickRow();
        this._updateSavePreview();
        this._submitting = false;
        this._pendingUploads = 0;
        this._submitQueued = false;
        this.saveButton = this.el.querySelector('.dt-save-bar button[type="submit"]');
        if (this.saveButton) {
            // Snapshot the markup, not the rendered amount: the preview span is filled in
            // later, and restoring a stale copy would both wipe the amount and detach the
            // live [data-save-amount-preview] node.
            this._saveButtonDefaultHtml = this.saveButton.innerHTML;
        }
        this._onPageShow = (ev) => {
            if (!ev.persisted) { return; }
            this._resetSubmitState();
            // Media staged before the previous save now belongs to that entry.
            this._pendingUploads = 0;
            this._submitQueued = false;
            this.el.dispatchEvent(new CustomEvent('dt-uploads-reset', { bubbles: true }));
        };
        window.addEventListener('pageshow', this._onPageShow);
        this._onUploadsChanged = (ev) => this._onUploadsProgress(ev);
        this.el.addEventListener('dt-uploads-changed', this._onUploadsChanged);
        return this._super(...arguments);
    },

    destroy() {
        if (this._onPageShow) { window.removeEventListener('pageshow', this._onPageShow); }
        if (this._onUploadsChanged) { this.el.removeEventListener('dt-uploads-changed', this._onUploadsChanged); }
        if (this._submitTimer) { window.clearTimeout(this._submitTimer); }
        return this._super(...arguments);
    },

    // Deferred so the browser has already captured the submitter before it goes
    // disabled — disabling it in the same tick can abort the submission outright.
    _lockSaveButton(html) {
        if (!this.saveButton) { return; }
        this.saveButton.classList.add('is-loading');
        this.saveButton.innerHTML = html;
        window.setTimeout(() => {
            if (this._submitting && this.saveButton) { this.saveButton.disabled = true; }
        }, 0);
    },

    _resetSubmitState() {
        this._submitting = false;
        if (this._submitTimer) { window.clearTimeout(this._submitTimer); this._submitTimer = null; }
        if (this.saveButton) {
            this.saveButton.disabled = false;
            this.saveButton.classList.remove('is-loading');
            this.saveButton.innerHTML = this._saveButtonDefaultHtml;
            // innerHTML replaced the preview node, so re-acquire it and redraw the amount
            // — otherwise the button would be stuck showing the amount as of page load.
            this.savePreview = this.el.querySelector('[data-save-amount-preview="1"]');
            this._updateSavePreview();
        }
    },

    // Safety net: a successful save navigates away, so this only ever fires when the
    // request failed or stalled. Without it the button would stay locked for good and
    // the entry could not be saved at all.
    _onSubmitStalled() {
        this._resetSubmitState();
        if (!this.saveButton || !this.saveButton.parentElement) { return; }
        const bar = this.saveButton.parentElement;
        let note = bar.querySelector('[data-save-stalled-note="1"]');
        if (!note) {
            note = document.createElement('div');
            note.className = 'dt-save-stalled-note';
            note.dataset.saveStalledNote = '1';
            bar.appendChild(note);
        }
        note.textContent = 'Lưu lâu bất thường. Hãy kiểm tra Lịch sử giao dịch trước khi bấm lại, tránh tạo trùng.';
    },

    _onUploadsProgress(ev) {
        const detail = (ev && ev.detail) || {};
        this._pendingUploads = detail.pending || 0;
        if (this._pendingUploads > 0) {
            if (this.saveButton && this._submitQueued) {
                const done = (detail.total || 0) - this._pendingUploads;
                this.saveButton.innerHTML =
                    `<span class="dt-btn-spinner"></span> Đang tải ảnh (${done}/${detail.total || 0})...`;
            }
            return;
        }
        // Last upload finished. If the user already pressed save, go now.
        if (this._submitQueued) {
            this._submitQueued = false;
            this._submitting = false;
            this.el.requestSubmit ? this.el.requestSubmit() : this.el.submit();
        }
    },

    // Guard against double-submit: tapping "Thêm giao dịch" more than once while the
    // request (often with an image upload) is still in flight used to create several
    // duplicate transactions. Lock the button and show a processing state on first
    // submit; a successful save navigates the browser away, so no reset is needed there
    // — only bfcache back-navigation (pageshow) restores the button.
    _onFormSubmit(ev) {
        if (this._submitting) {
            ev.preventDefault();
            return;
        }
        // Photos upload in the background from the moment they are picked. If one is
        // still in flight, queue the save instead of blocking the user: it fires by
        // itself as soon as the last upload lands.
        if (this._pendingUploads > 0) {
            ev.preventDefault();
            this._submitQueued = true;
            this._submitting = true;
            this._lockSaveButton('<span class="dt-btn-spinner"></span> Đang tải ảnh...');
            return;
        }
        this._submitting = true;
        this._lockSaveButton('<span class="dt-btn-spinner"></span> Đang lưu...');
        if (this._submitTimer) { window.clearTimeout(this._submitTimer); }
        this._submitTimer = window.setTimeout(() => this._onSubmitStalled(), 25000);
    },

    _snapshotOriginalQuickRow() {
        this.originalChipsByType = { expense: [], income: [] };
        this.addMoreBtn = null;
        if (!this.quickRow) { return; }
        Array.from(this.quickRow.children).forEach((child) => {
            if (child.dataset && child.dataset.showAllCategories) {
                this.addMoreBtn = child.cloneNode(true);
            } else if (child.dataset && child.dataset.categoryId) {
                const t = child.dataset.entryType;
                if (this.originalChipsByType[t]) { this.originalChipsByType[t].push(child.cloneNode(true)); }
            }
        });
    },

    _snapshotCategoryGroups() {
        if (!this.allCategories) { return; }
        const body = this.allCategories.querySelector('.dt-cat-modal__body');
        if (body) { this._catGroupsOriginalOrder = Array.from(body.querySelectorAll('[data-cat-group="1"]')); }
    },

    _restoreCatGroupOrder() {
        if (!this.allCategories || !this._catGroupsOriginalOrder) { return; }
        const body = this.allCategories.querySelector('.dt-cat-modal__body');
        if (body) { this._catGroupsOriginalOrder.forEach((g) => body.appendChild(g)); }
    },

    _showFilterBar(parentName) {
        const bar = this.allCategories && this.allCategories.querySelector('[data-cat-filter-bar="1"]');
        if (!bar) { return; }
        const label = bar.querySelector('[data-cat-filter-bar-label="1"]');
        if (label) { label.textContent = parentName || ''; }
        bar.classList.remove('d-none');
    },

    _hideFilterBar() {
        const bar = this.allCategories && this.allCategories.querySelector('[data-cat-filter-bar="1"]');
        if (bar) { bar.classList.add('d-none'); }
    },

    _onClearParentFilter(ev) {
        ev.preventDefault();
        if (!this.allCategories) { return; }
        const currentType = (this.entryTypeInput && this.entryTypeInput.value) || 'expense';
        this._restoreCatGroupOrder();
        this._hideFilterBar();
        const searchInput = this.allCategories.querySelector('[data-category-search="1"]');
        if (searchInput) { searchInput.value = ''; }
        this.allCategories.querySelectorAll('[data-cat-item="1"]').forEach((n) => { n.style.display = ''; });
        this.allCategories.querySelectorAll('[data-cat-group="1"]').forEach((group) => {
            const groupType = group.dataset.catGroupType;
            group.style.display = (!groupType || groupType === currentType) ? '' : 'none';
        });
    },

    _chipFromTile(tile) {
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'dt-quick-cat';
        chip.dataset.categoryId = tile.dataset.categoryId;
        chip.dataset.entryType = tile.dataset.entryType;
        chip.dataset.nextMonthRule = tile.dataset.nextMonthRule || '0';
        const icon = document.createElement('span');
        const iconSource = tile.querySelector('.dt-cat-tile__icon');
        const iconImg = iconSource ? iconSource.querySelector('img') : null;
        if (iconImg) {
            icon.appendChild(iconImg.cloneNode(true));
        } else {
            icon.textContent = (iconSource ? iconSource.textContent : '💸').trim() || '💸';
        }
        const name = document.createElement('small');
        const nameText = tile.querySelector('.dt-cat-tile__name');
        name.textContent = (nameText ? nameText.textContent : '').trim();
        chip.appendChild(icon);
        chip.appendChild(name);
        return chip;
    },

    _getParentIdForCategory(categoryId) {
        if (!this.allCategories || !categoryId) { return null; }
        const tile = this.allCategories.querySelector(`[data-cat-item="1"][data-category-id="${categoryId}"]`);
        if (!tile) { return null; }
        const group = tile.closest('[data-cat-group="1"]');
        return group ? (group.dataset.parentId || null) : null;
    },

    _resolveActiveChipId(activeId, chips) {
        if (!activeId) { return ''; }
        const chipIds = chips.map((c) => c.dataset.categoryId);
        if (chipIds.includes(activeId)) { return activeId; }
        // activeId might be a child — find its parent in the quick row
        const parentId = this._getParentIdForCategory(activeId);
        return (parentId && chipIds.includes(parentId)) ? parentId : '';
    },

    _buildChipForCategory(categoryId, currentType) {
        if (!this.allCategories || !categoryId) { return null; }
        const tile = this.allCategories.querySelector(`[data-cat-item="1"][data-category-id="${categoryId}"]`);
        if (!tile) { return null; }
        if (tile.dataset.entryType && tile.dataset.entryType !== currentType) { return null; }
        return this._chipFromTile(tile);
    },

    _rebuildQuickRow() {
        if (!this.quickRow) { return; }
        const currentType = (this.entryTypeInput && this.entryTypeInput.value) || 'expense';
        const activeId = (this.categorySelect && this.categorySelect.value) || '';
        let chips = (this.originalChipsByType[currentType] || []).map((c) => c.cloneNode(true));
        const activeChipId = this._resolveActiveChipId(activeId, chips);

        if (activeChipId) {
            // Move active chip to first position
            const idx = chips.findIndex((c) => c.dataset.categoryId === activeChipId);
            if (idx > 0) {
                const [active] = chips.splice(idx, 1);
                chips.unshift(active);
            }
        } else if (activeId) {
            // Selected category not in quick row — build a chip for it, drop last to keep count
            const extraChip = this._buildChipForCategory(activeId, currentType);
            if (extraChip) {
                chips.pop();
                chips.unshift(extraChip);
            }
        }

        this.quickRow.innerHTML = '';
        chips.forEach((c) => {
            c.hidden = false;
            c.removeAttribute('hidden');
            const isActive = !!activeId && (
                c.dataset.categoryId === activeId ||
                (activeChipId && c.dataset.categoryId === activeChipId)
            );
            c.classList.toggle('is-active', isActive);
            this.quickRow.appendChild(c);
        });
        if (this.addMoreBtn) { this.quickRow.appendChild(this.addMoreBtn.cloneNode(true)); }
        this.quickRow.scrollLeft = 0;
    },

    _onToggleParentList(ev) {
        ev.preventDefault();
        if (!this.parentListPanel) { return; }
        this.parentListPanel.classList.toggle('d-none');
        const expanded = !this.parentListPanel.classList.contains('d-none');
        if (this.parentListToggle) { this.parentListToggle.setAttribute('aria-expanded', expanded ? 'true' : 'false'); }
    },

    _onTabClick(ev) {
        ev.preventDefault();
        const tab = ev.currentTarget.dataset.entryTab || 'expense';
        if (this.entryTypeInput) { this.entryTypeInput.value = tab; }
        this.el.querySelectorAll('[data-entry-tab]').forEach((button) => {
            button.classList.toggle('is-active', button.dataset.entryTab === tab);
        });
        this._hideAllCategories();
        this._updateState();
    },

    _showAllCategories(ev, filterParentId) {
        if (ev) { ev.preventDefault(); }
        if (!this.allCategories) { return; }
        const currentType = (this.entryTypeInput && this.entryTypeInput.value) || 'expense';
        this.allCategories.dataset.activeType = currentType;

        // Always restore original group order before re-applying
        this._restoreCatGroupOrder();

        // Reset all tiles visible
        this.allCategories.querySelectorAll('[data-cat-item="1"]').forEach((n) => {
            n.hidden = false; n.removeAttribute('hidden'); n.style.display = '';
        });

        const searchInput = this.allCategories.querySelector('[data-category-search="1"]');
        if (searchInput) { searchInput.value = ''; }

        // Show all groups of current type first
        this.allCategories.querySelectorAll('[data-cat-group="1"]').forEach((group) => {
            const groupType = group.dataset.catGroupType;
            group.style.display = (!groupType || groupType === currentType) ? '' : 'none';
        });

        if (filterParentId) {
            // Pin the target group to top of list
            const body = this.allCategories.querySelector('.dt-cat-modal__body');
            const targetGroup = body && body.querySelector(`[data-cat-group="1"][data-parent-id="${filterParentId}"]`);
            if (targetGroup && body) { body.insertBefore(targetGroup, body.firstChild); }
            // Show filter bar with parent name
            const parentName = targetGroup ? (targetGroup.dataset.catName || '') : '';
            this._showFilterBar(parentName);
        } else {
            this._hideFilterBar();
        }

        this.allCategories.classList.remove('d-none');
        document.body.style.overflow = 'hidden';
    },

    _hideAllCategories(ev) {
        if (ev) { ev.preventDefault(); }
        if (!this.allCategories) { return; }
        this._restoreCatGroupOrder();
        this._hideFilterBar();
        this.allCategories.classList.add('d-none');
        document.body.style.overflow = '';
    },

    _onCategorySearch(ev) {
        const q = (ev.currentTarget.value || '').trim().toLowerCase();
        const currentType = (this.entryTypeInput && this.entryTypeInput.value) || 'expense';
        if (!this.allCategories) { return; }

        // Typing always clears active parent filter and restores original order
        this._restoreCatGroupOrder();
        this._hideFilterBar();

        this.allCategories.querySelectorAll('[data-cat-group="1"]').forEach((group) => {
            const groupType = group.dataset.catGroupType;
            // Hide wrong-type groups
            if (groupType && groupType !== currentType) { group.style.display = 'none'; return; }

            const groupName = (group.dataset.catName || '').toLowerCase();
            const tiles = Array.from(group.querySelectorAll('[data-cat-item="1"]'));

            if (!q || groupName.includes(q)) {
                // Parent name matches (or no query) → show entire group
                tiles.forEach((n) => { n.style.display = ''; });
                group.style.display = '';
            } else {
                // Check individual tile names
                let anyVisible = false;
                tiles.forEach((n) => {
                    const visible = (n.dataset.catName || '').toLowerCase().includes(q);
                    n.style.display = visible ? '' : 'none';
                    if (visible) { anyVisible = true; }
                });
                group.style.display = anyVisible ? '' : 'none';
            }
        });
    },

    _onTitleBlur() {
        hideListOnBlur(this.titleList);
    },

    _onQuickCategoryClick(ev) {
        ev.preventDefault();
        const button = ev.currentTarget;
        const categoryId = button.dataset.categoryId;
        const entryType = button.dataset.entryType;
        const hasChildren = button.dataset.hasChildren === '1';
        const fromModal = !!(this.allCategories && button.closest('[data-all-categories]'));

        // Sync tab type (only when triggered from quick row, not modal)
        if (!fromModal && entryType && this.entryTypeInput) {
            this.entryTypeInput.value = entryType;
            this.el.querySelectorAll('[data-entry-tab]').forEach((tab) => tab.classList.toggle('is-active', tab.dataset.entryTab === entryType));
        }

        // Parent with children tapped from quick row → open modal filtered to this group
        if (hasChildren && !fromModal) {
            this._showAllCategories(ev, categoryId);
            return;
        }

        // Select directly (parent-no-children or any tile from modal)
        if (this.categorySelect && categoryId) {
            this.categorySelect.value = categoryId;
            this.el.querySelectorAll('[data-category-id]').forEach((chip) => chip.classList.toggle('is-active', chip.dataset.categoryId === categoryId));
        }
        if (fromModal) { this._hideAllCategories(); }
        // Picked from the expanded "show more" panel — collapse it, the choice is made.
        if (this.parentListPanel && button.closest('[data-parent-list="1"]')) {
            this.parentListPanel.classList.add('d-none');
            if (this.parentListToggle) { this.parentListToggle.setAttribute('aria-expanded', 'false'); }
        }
        this._onCategoryChange();
    },

    _updateState() {
        const currentType = (this.entryTypeInput && this.entryTypeInput.value) || 'expense';
        const isAdjustment = currentType === 'adjustment';
        this.categoryFields.forEach((field) => {
            if (isAdjustment) { field.setAttribute('hidden', 'hidden'); }
            else { field.removeAttribute('hidden'); }
        });
        if (this.adjustmentField) {
            if (isAdjustment) { this.adjustmentField.removeAttribute('hidden'); }
            else { this.adjustmentField.setAttribute('hidden', 'hidden'); }
        }
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
        this.el.querySelectorAll('[data-cat-item="1"]').forEach((chip) => {
            chip.classList.toggle('is-active', this.categorySelect && chip.dataset.categoryId === this.categorySelect.value);
        });
        if (this.parentListPanel) {
            this.parentListPanel.querySelectorAll('[data-category-id]').forEach((btn) => {
                btn.hidden = btn.dataset.entryType !== currentType;
            });
        }
        this._rebuildQuickRow();
        this._onDateChange();
        this._refreshSuggestions();
        this._updateSavePreview();
    },

    _onCategoryChange() {
        if (this.categorySelect) {
            const categoryId = this.categorySelect.value;
            this.el.querySelectorAll('[data-cat-item="1"]').forEach((chip) => chip.classList.toggle('is-active', chip.dataset.categoryId === categoryId));
        }
        this._rebuildQuickRow();
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
        this.savePreview.textContent = raw || '0';
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
            renderSuggestionList(this.titleList, rows, (label, row) => {
                this.titleInput.value = label;
                // Prefill the amount from the last time this description was used. Only
                // when the field is still empty, so we never overwrite what the user typed.
                const amountInput = this.el.querySelector('input[name="amount"]');
                if (amountInput && row && row.amount && !(amountInput.value || '').trim()) {
                    amountInput.value = row.amount;
                    amountInput.dispatchEvent(new Event('input', { bubbles: true }));
                }
                this.titleList.classList.add('d-none');
            }, forceShow);
        } catch (_e) {
            this.titleList.innerHTML = '';
            this.titleList.classList.add('d-none');
        }
    },

    _onTitleInput() { this._refreshSuggestions(true); },
    _onTitleFocus() { this._refreshSuggestions(true); },
});

publicWidget.registry.DTDebtForm = publicWidget.Widget.extend({
    selector: 'form[data-debt-form="1"]',
    events: {
        'change input[name="debt_type"]': '_onDebtTypeChange',
        'input [data-counterparty-input="1"]': '_onCounterpartyInput',
        'focusin [data-counterparty-input="1"]': '_onCounterpartyFocus',
        'focusout [data-counterparty-input="1"]': '_onCounterpartyBlur',
    },

    start() {
        this.counterpartyInput = this.el.querySelector('[data-counterparty-input="1"]');
        this.counterpartyList = this.el.querySelector('[data-counterparty-suggestion-list="1"]');
        this._suggestionRequest = 0;
        return this._super(...arguments);
    },

    _onDebtTypeChange(ev) {
        const value = ev.currentTarget.value;
        this.el.querySelectorAll('.dt-segment label').forEach((label) => {
            const radio = label.querySelector('input[name="debt_type"]');
            label.classList.toggle('is-active', !!radio && radio.value === value);
        });
    },

    async _refreshCounterpartySuggestions(forceShow = false) {
        if (!this.counterpartyInput || !this.counterpartyList) { return; }
        const requestId = ++this._suggestionRequest;
        const url = `/my/apps/expenses/debts/counterparty_suggestions?q=${encodeURIComponent(this.counterpartyInput.value || '')}`;
        try {
            const response = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            if (!response.ok) { throw new Error('network'); }
            const rows = await response.json();
            if (requestId !== this._suggestionRequest) { return; }
            renderSuggestionList(this.counterpartyList, rows, (label) => {
                this.counterpartyInput.value = label;
                this.counterpartyList.classList.add('d-none');
            }, forceShow);
        } catch (_e) {
            this.counterpartyList.innerHTML = '';
            this.counterpartyList.classList.add('d-none');
        }
    },

    _onCounterpartyInput() { this._refreshCounterpartySuggestions(true); },
    _onCounterpartyFocus() { this._refreshCounterpartySuggestions(true); },
    _onCounterpartyBlur() { hideListOnBlur(this.counterpartyList); },
});

publicWidget.registry.DTExpensePage = publicWidget.Widget.extend({
    selector: '.dt-expense-page',
    events: {
        'click [data-payment-toggle]': '_onPaymentToggle',
        'click [data-month-nav-dir]': '_onMonthNavClick',
        'click [data-filter-toggle="1"]': '_onFilterToggle',
        'click [data-member-open="1"]': '_onMemberOpen',
        'click [data-member-close="1"]': '_onMemberClose',
        'click [data-member-apply="1"]': '_onMemberApply',
        'change select[name="scope"]': '_onScopeChange',
        'click [data-date-picker-open="1"]': '_onDatePickerOpen',
        'click [data-date-close="1"]': '_onDatePickerClose',
        'click [data-date-tab]': '_onDateTabClick',
        'click [data-date-apply="1"]': '_onDateApply',
        'click [data-cat-filter-open="1"]': '_onCatFilterOpen',
        'click [data-cat-filter-close="1"]': '_onCatFilterClose',
        'click [data-cat-filter-tile="1"]': '_onCatFilterTilePick',
        'click [data-cat-filter-group="1"]': '_onCatFilterGroupPick',
        'click [data-cat-filter-clear="1"]': '_onCatFilterClear',
        'input [data-cat-filter-search="1"]': '_onCatFilterSearch',
        'click [data-multi-filter]': '_onMultiFilterToggle',
    },

    start() {
        this.entryList = this.el.querySelector('[data-entry-list="1"]');
        this.sentinel = this.el.querySelector('[data-scroll-sentinel="1"]');
        this.loadingEl = this.el.querySelector('[data-scroll-loading="1"]');
        this._loading = false;
        this._observer = null;
        if (this.sentinel && this.sentinel.dataset.hasMore) { this._initInfiniteScroll(); }
        return this._super(...arguments);
    },

    _onFilterToggle(ev) {
        ev.preventDefault();
        const adv = this.el.querySelector('[data-filter-advanced="1"]');
        if (adv) { adv.classList.toggle('d-none'); }
    },

    _onMultiFilterToggle(ev) {
        const btn = ev.currentTarget;
        const key = btn.dataset.multiFilter;
        const value = btn.dataset.multiFilterValue;
        const url = new URL(window.location.href);
        const current = url.searchParams.getAll(key);
        const isActive = current.includes(value);
        const next = isActive ? current.filter((v) => v !== value) : [...current, value];
        url.searchParams.delete(key);
        next.forEach((v) => url.searchParams.append(key, v));
        window.location.href = url.toString();
    },

    _onMemberOpen(ev) {
        ev.preventDefault();
        const dlg = this.el.querySelector('[data-member-dialog="1"]');
        if (dlg) { dlg.classList.remove('d-none'); document.body.style.overflow = 'hidden'; }
    },

    _onMemberClose(ev) {
        if (ev) { ev.preventDefault(); }
        const dlg = this.el.querySelector('[data-member-dialog="1"]');
        if (dlg) { dlg.classList.add('d-none'); document.body.style.overflow = ''; }
    },

    _onScopeChange(ev) {
        const isFamily = ev.currentTarget.value === 'family';
        const memberFilter = this.el.querySelector('[data-member-filter="1"]');
        if (memberFilter) { memberFilter.classList.toggle('d-none', !isFamily); }
    },

    _onMemberApply(ev) {
        ev.preventDefault();
        const dlg = this.el.querySelector('[data-member-dialog="1"]');
        const form = this.el.querySelector('[data-filter-form="1"]');
        if (!dlg || !form) { return; }
        form.querySelectorAll('input[data-member-hidden="1"]').forEach((n) => n.remove());
        const container = form.querySelector('.dt-filter-members');
        dlg.querySelectorAll('input[data-member-checkbox="1"]:checked').forEach((cb) => {
            const hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = 'member_ids';
            hidden.value = cb.value;
            hidden.dataset.memberHidden = '1';
            container.appendChild(hidden);
        });
        this._onMemberClose();
        form.submit();
    },

    _onPaymentToggle(ev) {
        ev.preventDefault();
        const key = ev.currentTarget.dataset.paymentToggle;
        const form = this.el.querySelector(`[data-payment-form="${key}"]`);
        if (form) { form.classList.toggle('d-none'); }
    },

    _onMonthNavClick(ev) {
        ev.preventDefault();
        const dir = parseInt(ev.currentTarget.dataset.monthNavDir, 10);
        const nav = this.el.querySelector('[data-month-nav="1"]');
        if (!nav || !nav.dataset.dateFrom) { return; }
        const kind = nav.dataset.periodKind || 'month';
        const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
        const parts = nav.dataset.dateFrom.split('-').map((n) => parseInt(n, 10));
        let newDateFrom, newDateTo;
        if (kind === 'year') {
            const y = parts[0] + dir;
            newDateFrom = `${y}-01-01`;
            newDateTo = `${y}-12-31`;
        } else if (kind === 'week') {
            const start = new Date(parts[0], parts[1] - 1, parts[2]);
            start.setDate(start.getDate() + dir * 7);
            const end = new Date(start);
            end.setDate(start.getDate() + 6);
            newDateFrom = fmt(start);
            newDateTo = fmt(end);
        } else {
            let year = parts[0];
            let month = parts[1] + dir;
            if (month > 12) { year += 1; month = 1; }
            if (month < 1) { year -= 1; month = 12; }
            const lastDay = new Date(year, month, 0).getDate();
            newDateFrom = `${year}-${String(month).padStart(2, '0')}-01`;
            newDateTo = `${year}-${String(month).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;
        }
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
            debt_flow: sentinel.dataset.debtFlow || '',
            debt_id: sentinel.dataset.debtId || '',
            plan_id: sentinel.dataset.planId || '',
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

    _onDatePickerOpen(ev) {
        ev.preventDefault();
        const dlg = this.el.querySelector('[data-date-modal="1"]');
        if (dlg) { dlg.classList.remove('d-none'); document.body.style.overflow = 'hidden'; }
    },

    _onDatePickerClose(ev) {
        if (ev) { ev.preventDefault(); }
        const dlg = this.el.querySelector('[data-date-modal="1"]');
        if (dlg) { dlg.classList.add('d-none'); document.body.style.overflow = ''; }
    },

    _onDateTabClick(ev) {
        ev.preventDefault();
        const tab = ev.currentTarget.dataset.dateTab;
        const dlg = this.el.querySelector('[data-date-modal="1"]');
        if (!dlg) { return; }
        dlg.querySelectorAll('[data-date-tab]').forEach((b) => b.classList.toggle('is-active', b.dataset.dateTab === tab));
        dlg.querySelectorAll('[data-date-panel]').forEach((p) => p.classList.toggle('d-none', p.dataset.datePanel !== tab));
    },

    _onDateApply(ev) {
        ev.preventDefault();
        const dlg = this.el.querySelector('[data-date-modal="1"]');
        if (!dlg) { return; }
        const activeTab = dlg.querySelector('[data-date-tab].is-active')?.dataset.dateTab || 'month';
        const input = dlg.querySelector(`[data-date-input="${activeTab}"]`);
        if (!input || !input.value) { return; }
        let dateFrom, dateTo;
        if (activeTab === 'month') {
            const [y, m] = input.value.split('-').map(Number);
            const last = new Date(y, m, 0).getDate();
            dateFrom = `${y}-${String(m).padStart(2, '0')}-01`;
            dateTo = `${y}-${String(m).padStart(2, '0')}-${String(last).padStart(2, '0')}`;
        } else if (activeTab === 'year') {
            const y = parseInt(input.value, 10);
            if (!y) { return; }
            dateFrom = `${y}-01-01`;
            dateTo = `${y}-12-31`;
        } else if (activeTab === 'week') {
            // input.value: YYYY-Www
            const [yStr, wStr] = input.value.split('-W');
            const y = parseInt(yStr, 10);
            const w = parseInt(wStr, 10);
            const jan4 = new Date(y, 0, 4);
            const jan4Day = jan4.getDay() || 7;
            const week1Mon = new Date(y, 0, 4 - jan4Day + 1);
            const monday = new Date(week1Mon);
            monday.setDate(week1Mon.getDate() + (w - 1) * 7);
            const sunday = new Date(monday);
            sunday.setDate(monday.getDate() + 6);
            const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
            dateFrom = fmt(monday);
            dateTo = fmt(sunday);
        }
        const url = new URL(window.location.href);
        url.searchParams.set('date_from', dateFrom);
        url.searchParams.set('date_to', dateTo);
        window.location.href = url.toString();
    },

    _onCatFilterOpen(ev) {
        ev.preventDefault();
        const dlg = this.el.querySelector('[data-filter-cat-modal="1"]');
        if (dlg) { dlg.classList.remove('d-none'); document.body.style.overflow = 'hidden'; }
    },

    _onCatFilterClose(ev) {
        if (ev) { ev.preventDefault(); }
        const dlg = this.el.querySelector('[data-filter-cat-modal="1"]');
        if (dlg) { dlg.classList.add('d-none'); document.body.style.overflow = ''; }
    },

    _submitFilterForm() {
        const form = this.el.querySelector('[data-filter-form="1"]');
        if (form) { form.submit(); }
    },

    _onCatFilterTilePick(ev) {
        ev.preventDefault();
        const btn = ev.currentTarget;
        const form = this.el.querySelector('[data-filter-form="1"]');
        if (!form) { return; }
        form.querySelector('[data-cat-filter-category="1"]').value = btn.dataset.categoryId || '';
        form.querySelector('[data-cat-filter-parent="1"]').value = '';
        this._submitFilterForm();
    },

    _onCatFilterGroupPick(ev) {
        ev.preventDefault();
        const btn = ev.currentTarget;
        const form = this.el.querySelector('[data-filter-form="1"]');
        if (!form) { return; }
        form.querySelector('[data-cat-filter-parent="1"]').value = btn.dataset.parentId || '';
        form.querySelector('[data-cat-filter-category="1"]').value = '';
        this._submitFilterForm();
    },

    _onCatFilterClear(ev) {
        ev.preventDefault();
        const form = this.el.querySelector('[data-filter-form="1"]');
        if (!form) { return; }
        form.querySelector('[data-cat-filter-parent="1"]').value = '';
        form.querySelector('[data-cat-filter-category="1"]').value = '';
        this._submitFilterForm();
    },

    _onCatFilterSearch(ev) {
        const q = (ev.currentTarget.value || '').trim().toLowerCase();
        const dlg = this.el.querySelector('[data-filter-cat-modal="1"]');
        if (!dlg) { return; }
        dlg.querySelectorAll('[data-cat-filter-tile="1"]').forEach((tile) => {
            const name = (tile.dataset.catName || '').toLowerCase();
            tile.style.display = !q || name.includes(q) ? '' : 'none';
        });
        dlg.querySelectorAll('[data-cat-group="1"]').forEach((group) => {
            const groupName = (group.dataset.catName || '').toLowerCase();
            const anyTile = Array.from(group.querySelectorAll('[data-cat-filter-tile="1"]')).some((n) => n.style.display !== 'none');
            const matchGroup = !q || groupName.includes(q);
            group.style.display = (anyTile || matchGroup) ? '' : 'none';
        });
    },
});
