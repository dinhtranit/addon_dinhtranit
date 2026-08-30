/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

function digitsOnly(value) {
    return (value || "").replace(/\D+/g, "");
}

function formatNumberString(value) {
    const numericPart = digitsOnly(value);
    if (!numericPart) {
        return "";
    }
    return numericPart.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

function formatSignedValue(value) {
    const trimmed = (value || "").trim();
    const negative = trimmed.startsWith("-");
    const formatted = formatNumberString(trimmed);
    return negative && formatted ? `-${formatted}` : formatted;
}

function resolveMultipliers(input) {
    const rawConfig = (input.dataset.moneySuggestions || "").trim();
    if (!rawConfig) {
        return [1000, 10000, 100000, 1000000];
    }
    const parsed = rawConfig
        .split(",")
        .map((item) => parseInt((item || "").trim(), 10))
        .filter((item) => Number.isFinite(item) && item > 0);
    return parsed.length ? parsed : [1000, 10000, 100000, 1000000];
}

publicWidget.registry.DTMoneyInput = publicWidget.Widget.extend({
    selector: 'input[data-money-input="1"]',
    events: {
        input: "_onInput",
        focus: "_onFocus",
        blur: "_onBlur",
    },

    start() {
        this._ensureSuggestionHolder();
        this.el.value = formatSignedValue(this.el.value);
        this._updateFontSize();
        this.holder.style.display = "none";
        return this._super(...arguments);
    },

    _ensureSuggestionHolder() {
        const nextElement = this.el.nextElementSibling;
        if (nextElement && nextElement.classList.contains("dt-money-suggestions")) {
            this.holder = nextElement;
            return;
        }
        this.holder = document.createElement("div");
        this.holder.className = "dt-money-suggestions";
        this.el.insertAdjacentElement("afterend", this.holder);
    },

    _buildSuggestions() {
        const rawValue = (this.el.value || "").trim();
        const baseDigits = digitsOnly(rawValue);
        this.holder.innerHTML = "";

        if (!baseDigits || rawValue.startsWith("-")) {
            this.holder.style.display = "none";
            return;
        }

        const baseNumber = parseInt(baseDigits, 10);
        if (!baseNumber) {
            this.holder.style.display = "none";
            return;
        }

        const powers = [10, 100, 1000, 10000, 100000, 1000000];
        const seen = new Set();
        const results = [];

        for (const p of powers) {
            const amount = baseNumber * p;
            if (amount > baseNumber && amount > 10000 && amount < 500000000 && amount % 1000 === 0 && !seen.has(amount)) {
                seen.add(amount);
                results.push(amount);
            }
        }

        results.slice(0, 4).forEach((amount) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "dt-money-suggestion";
            button.textContent = formatNumberString(String(amount)) + 'đ';
            button.addEventListener("click", (ev) => {
                ev.preventDefault();
                this.el.value = formatNumberString(String(amount));
                this.el.dispatchEvent(new Event("input", { bubbles: true }));
                this.el.focus();
            });
            this.holder.appendChild(button);
        });

        this.holder.style.display = this.holder.children.length ? "flex" : "none";
    },

    _updateFontSize() {
        if (this.el.dataset.moneyInputSize === 'sm') {
            this.el.style.fontSize = '';
            return;
        }
        const len = (this.el.value || '').length;
        const size = len <= 7 ? 58 : len <= 10 ? 44 : len <= 12 ? 36 : 30;
        this.el.style.fontSize = size + 'px';
    },

    _onInput() {
        const formatted = formatSignedValue(this.el.value);
        this.el.value = formatted;
        this._updateFontSize();
        if (document.activeElement === this.el) { this._buildSuggestions(); }
    },

    _onFocus() {
        this._buildSuggestions();
    },

    _onBlur() {
        window.setTimeout(() => {
            if (!this.holder.matches(":hover")) {
                this.holder.style.display = "none";
            }
        }, 150);
    },
});
