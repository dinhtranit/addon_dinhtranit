/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.DTFileInput = publicWidget.Widget.extend({
    selector: 'input[data-file-input="1"]',
    events: {
        change: "_onFileChange",
    },

    start() {
        const form = this.el.closest("form");
        this.holder = form ? form.querySelector('[data-file-preview="1"]') : null;
        return this._super(...arguments);
    },

    _onFileChange() {
        if (!this.holder) { return; }
        this.holder.innerHTML = "";
        const files = Array.from(this.el.files || []);
        if (!files.length) { this.holder.classList.add("d-none"); return; }
        this.holder.classList.remove("d-none");
        files.forEach((file) => {
            const tile = document.createElement("div");
            tile.className = "dt-media-tile dt-media-tile--new";
            if (file.type.startsWith("image/")) {
                const img = document.createElement("img");
                img.src = URL.createObjectURL(file);
                tile.appendChild(img);
            } else {
                const label = document.createElement("span");
                label.textContent = "📎 " + file.name;
                tile.appendChild(label);
            }
            const badge = document.createElement("span");
            badge.className = "dt-media-tile__badge";
            badge.textContent = "✓";
            tile.appendChild(badge);
            this.holder.appendChild(tile);
        });
    },
});
