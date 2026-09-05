/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

// Phone photos arrive at 3-8 MB. Sending them raw was the slowest part of saving an
// entry: the bytes go over the wire, then Odoo decodes the image and resizes it down to
// ~1920px anyway. Doing that resize here first turns a multi-second save into a fraction
// of a second, and stores a smaller file.
const MAX_DIMENSION = 1920;
const JPEG_QUALITY = 0.82;
// Anything already this small is not worth re-encoding.
const SKIP_BELOW_BYTES = 600 * 1024;
const UPLOAD_URL = "/my/family/media/upload";

function compressImage(file) {
    return new Promise((resolve) => {
        const isCompressible =
            file &&
            file.type &&
            file.type.startsWith("image/") &&
            file.type !== "image/gif" &&
            file.size > SKIP_BELOW_BYTES;
        if (!isCompressible) {
            resolve(file);
            return;
        }
        const url = URL.createObjectURL(file);
        const img = new Image();
        img.onload = () => {
            URL.revokeObjectURL(url);
            try {
                const longestSide = Math.max(img.naturalWidth, img.naturalHeight);
                const scale = Math.min(1, MAX_DIMENSION / (longestSide || 1));
                const width = Math.max(1, Math.round(img.naturalWidth * scale));
                const height = Math.max(1, Math.round(img.naturalHeight * scale));
                const canvas = document.createElement("canvas");
                canvas.width = width;
                canvas.height = height;
                canvas.getContext("2d").drawImage(img, 0, 0, width, height);
                canvas.toBlob(
                    (blob) => {
                        // Keep the original whenever re-encoding did not actually help.
                        if (!blob || blob.size >= file.size) {
                            resolve(file);
                            return;
                        }
                        const baseName = file.name.replace(/\.[^.]+$/, "") || "anh";
                        resolve(new File([blob], `${baseName}.jpg`, {
                            type: "image/jpeg",
                            lastModified: Date.now(),
                        }));
                    },
                    "image/jpeg",
                    JPEG_QUALITY
                );
            } catch (_e) {
                resolve(file);
            }
        };
        // Formats the browser cannot decode (HEIC on Chrome, for one) land here and are
        // uploaded untouched, exactly as before.
        img.onerror = () => {
            URL.revokeObjectURL(url);
            resolve(file);
        };
        img.src = url;
    });
}

publicWidget.registry.DTFileInput = publicWidget.Widget.extend({
    selector: 'input[data-file-input="1"]',
    events: {
        change: "_onFileChange",
    },

    start() {
        this.form = this.el.closest("form");
        this.holder = this.form ? this.form.querySelector('[data-file-preview="1"]') : null;
        this.uploadModel = this.el.dataset.uploadModel || "";
        this.fileButton =
            this.el.nextElementSibling && this.el.nextElementSibling.classList.contains("dt-file-button")
                ? this.el.nextElementSibling
                : null;
        // One entry per picked file: {file, mediaId, state}
        this.items = [];
        // Coming back to this page via the browser's back/forward cache restores tiles
        // that look uploaded, but their media now belongs to the entry that was saved.
        // Clear them so the next save cannot silently reference claimed media.
        this._onUploadsReset = () => this._clearPicked();
        if (this.form) { this.form.addEventListener('dt-uploads-reset', this._onUploadsReset); }
        return this._super(...arguments);
    },

    destroy() {
        if (this.form && this._onUploadsReset) {
            this.form.removeEventListener('dt-uploads-reset', this._onUploadsReset);
        }
        return this._super(...arguments);
    },

    _clearPicked() {
        if (!this.items.length) { return; }
        this.items = [];
        this.el.value = "";
        this._render();
        this._syncForm();
    },

    async _onFileChange() {
        const picked = Array.from(this.el.files || []);
        if (!picked.length) {
            this.items = [];
            this._render();
            this._syncForm();
            return;
        }
        const label = this.fileButton ? this.fileButton.innerHTML : null;
        if (this.fileButton) { this.fileButton.textContent = "Đang xử lý ảnh..."; }
        let files = picked;
        try {
            const processed = await Promise.all(picked.map(compressImage));
            // Assigning .files does not re-fire "change", so there is no loop here.
            if (processed.some((file, index) => file !== picked[index])) {
                const transfer = new DataTransfer();
                processed.forEach((file) => transfer.items.add(file));
                this.el.files = transfer.files;
            }
            files = processed;
        } catch (_e) {
            files = picked;
        }
        if (this.fileButton && label !== null) { this.fileButton.innerHTML = label; }

        this.items = files.map((file) => ({
            file,
            mediaId: null,
            // Without an upload model configured we keep the old behaviour: the file rides
            // along in the form POST and is processed when the entry is saved.
            state: this.uploadModel ? "uploading" : "inline",
        }));
        this._render();
        this._syncForm();
        if (this.uploadModel) {
            this.items.forEach((item) => this._upload(item));
        }
    },

    async _upload(item) {
        item.state = "uploading";
        this._render();
        this._syncForm();
        try {
            const data = new FormData();
            data.append("file", item.file, item.file.name);
            data.append("res_model", this.uploadModel);
            const token = this.form && this.form.querySelector('input[name="csrf_token"]');
            if (token) { data.append("csrf_token", token.value); }
            const response = await fetch(UPLOAD_URL, { method: "POST", body: data });
            if (!response.ok) { throw new Error("upload failed"); }
            const payload = await response.json();
            if (!payload || !payload.id) { throw new Error("no id"); }
            item.mediaId = payload.id;
            item.state = "done";
        } catch (_e) {
            item.mediaId = null;
            item.state = "error";
        }
        this._render();
        this._syncForm();
    },

    /**
     * Keep the form in sync with upload state:
     *  - hidden `media_ids` lists everything already stored server-side;
     *  - `input.files` keeps only what still has to ride along in the POST, so a file is
     *    never uploaded twice;
     *  - `data-uploads-pending` lets the save button know whether to wait.
     */
    _syncForm() {
        if (!this.form) { return; }
        const done = this.items.filter((item) => item.state === "done");
        const pending = this.items.filter((item) => item.state === "uploading");
        const fallback = this.items.filter((item) => item.state !== "done");

        let hidden = this.form.querySelector('input[data-media-ids="1"]');
        if (!hidden) {
            hidden = document.createElement("input");
            hidden.type = "hidden";
            hidden.name = "media_ids";
            hidden.dataset.mediaIds = "1";
            this.form.appendChild(hidden);
        }
        hidden.value = done.map((item) => item.mediaId).join(",");

        const transfer = new DataTransfer();
        fallback.forEach((item) => transfer.items.add(item.file));
        this.el.files = transfer.files;

        this.form.dataset.uploadsPending = String(pending.length);
        this.form.dataset.uploadsTotal = String(this.items.length);
        this.form.dispatchEvent(new CustomEvent("dt-uploads-changed", {
            bubbles: true,
            detail: { pending: pending.length, total: this.items.length, done: done.length },
        }));
    },

    _render() {
        if (!this.holder) { return; }
        this.holder.innerHTML = "";
        if (!this.items.length) {
            this.holder.classList.add("d-none");
            return;
        }
        this.holder.classList.remove("d-none");
        this.items.forEach((item, index) => {
            const tile = document.createElement("div");
            tile.className = `dt-media-tile dt-media-tile--new is-${item.state}`;
            if (item.file.type.startsWith("image/")) {
                const img = document.createElement("img");
                img.src = URL.createObjectURL(item.file);
                tile.appendChild(img);
            } else {
                const label = document.createElement("span");
                label.textContent = "📎 " + item.file.name;
                tile.appendChild(label);
            }
            if (item.state === "uploading") {
                const overlay = document.createElement("span");
                overlay.className = "dt-media-tile__overlay";
                overlay.innerHTML = '<span class="dt-btn-spinner"></span><small>Đang tải...</small>';
                tile.appendChild(overlay);
            } else if (item.state === "error") {
                const overlay = document.createElement("button");
                overlay.type = "button";
                overlay.className = "dt-media-tile__overlay dt-media-tile__overlay--error";
                overlay.innerHTML = '<small>Tải lỗi</small><small><u>Thử lại</u></small>';
                overlay.addEventListener("click", (ev) => {
                    ev.preventDefault();
                    ev.stopPropagation();
                    if (item.state === "error") { this._upload(item); }
                });
                tile.appendChild(overlay);
            } else {
                const badge = document.createElement("span");
                badge.className = "dt-media-tile__badge";
                badge.textContent = "✓";
                tile.appendChild(badge);
            }
            this.holder.appendChild(tile);
        });
    },
});
