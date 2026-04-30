/** @odoo-module **/

(function () {
    function digitsOnly(value) {
        return (value || '').replace(/\D+/g, '');
    }

    function formatNumberString(value) {
        const numericPart = digitsOnly(value);
        if (!numericPart) {
            return '';
        }
        return numericPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    }

    function formatSignedValue(value) {
        const negative = (value || '').trim().startsWith('-');
        const formatted = formatNumberString(value);
        return negative && formatted ? `-${formatted}` : formatted;
    }

    function resolveMultipliers(input) {
        const rawConfig = (input.dataset.moneySuggestions || '').trim();
        if (!rawConfig) {
            return [1000, 10000, 100000, 1000000];
        }
        const parsed = rawConfig
            .split(',')
            .map((item) => parseInt((item || '').trim(), 10))
            .filter((item) => Number.isFinite(item) && item > 0);
        return parsed.length ? parsed : [1000, 10000, 100000, 1000000];
    }

    function buildSuggestions(input, holder) {
        const rawValue = (input.value || '').trim();
        const baseDigits = digitsOnly(rawValue);
        holder.innerHTML = '';
        if (!baseDigits || rawValue.startsWith('-')) {
            holder.style.display = 'none';
            return;
        }
        const baseNumber = parseInt(baseDigits, 10);
        if (!baseNumber) {
            holder.style.display = 'none';
            return;
        }

        const multipliers = resolveMultipliers(input);
        const seen = new Set();
        multipliers.forEach((multiplier) => {
            const amount = baseNumber * multiplier;
            if (seen.has(amount)) {
                return;
            }
            seen.add(amount);
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'dt-money-suggestion';
            button.textContent = `${formatNumberString(String(amount))} đ`;
            button.addEventListener('click', function () {
                input.value = formatNumberString(String(amount));
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.focus();
            });
            holder.appendChild(button);
        });
        holder.style.display = holder.children.length ? 'flex' : 'none';
    }

    function attachMoneyInput(input) {
        if (input.dataset.moneyBound === '1') {
            return;
        }
        input.dataset.moneyBound = '1';
        const holder = document.createElement('div');
        holder.className = 'dt-money-suggestions';
        input.insertAdjacentElement('afterend', holder);

        input.addEventListener('input', function () {
            const caretToEnd = input.value.length;
            input.value = formatSignedValue(input.value);
            try {
                input.setSelectionRange(caretToEnd, caretToEnd);
            } catch (error) {
                // Some mobile browsers do not support setSelectionRange on all input states.
            }
            buildSuggestions(input, holder);
        });

        input.addEventListener('focus', function () {
            buildSuggestions(input, holder);
        });

        input.addEventListener('blur', function () {
            window.setTimeout(function () {
                if (!holder.matches(':hover')) {
                    holder.style.display = holder.children.length ? 'flex' : 'none';
                }
            }, 150);
        });

        input.value = formatSignedValue(input.value);
        buildSuggestions(input, holder);
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('input[data-money-input="1"]').forEach(attachMoneyInput);
    });
})();
