/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.DTBalanceToggle = publicWidget.Widget.extend({
    selector: '[data-balance-toggle="1"]',
    events: {
        click: "_onClick",
    },

    _onClick() {
        const isVisible = document.cookie.split('; ').some((c) => c === 'dt_balance_visible=1');
        if (isVisible) {
            document.cookie = 'dt_balance_visible=; max-age=0; path=/';
        } else {
            document.cookie = 'dt_balance_visible=1; max-age=1800; path=/';
        }
        window.location.reload();
    },
});
