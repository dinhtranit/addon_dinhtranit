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
const DISCARD_URL = (id) => `/my/family/media/${id}/discard`;

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

    /**
     * Drop a file the user picked by mistake. Anything already stored server-side is
     * discarded there too, so a wrong photo does not linger as an orphan.
     */
    async _removeItem(index) {
        const item = this.items[index];
        if (!item) { return; }
        this.items.splice(index, 1);
        this._render();
        this._syncForm();
        if (item.mediaId) {
            try {
                const data = new FormData();
                const token = this.form && this.form.querySelector('input[name="csrf_token"]');
                if (token) { data.append("csrf_token", token.value); }
                await fetch(DISCARD_URL(item.mediaId), { method: "POST", body: data });
            } catch (_e) {
                // Nothing to do: the sweep of unattached uploads will collect it later.
            }
        }
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
            const remove = document.createElement("button");
            remove.type = "button";
            remove.className = "dt-media-tile__remove";
            remove.setAttribute("aria-label", "Bỏ ảnh này");
            remove.innerHTML = '<i class="fa fa-times"></i>';
            remove.addEventListener("click", (ev) => {
                ev.preventDefault();
                ev.stopPropagation();
                this._removeItem(index);
            });
            tile.appendChild(remove);
            this.holder.appendChild(tile);
        });
    },
});

/**
 * Confirmation dialog for destructive forms.
 *
 * These used to rely on `onsubmit="return confirm(...)"`. Once a browser blocks dialogs
 * for a page - Chrome offers exactly that after a few of them - `confirm()` returns
 * false without showing anything, the submit is cancelled, and the button looks
 * completely dead. An in-page dialog cannot fail that way.
 *
 * The trigger is a plain button rather than a submit: if this script ever fails to
 * load, the worst case is a button that does nothing, not a transaction deleted
 * without asking.
 */
publicWidget.registry.DTConfirmSubmit = publicWidget.Widget.extend({
    selector: 'form[data-confirm-form="1"]',
    events: {
        'click [data-confirm-open="1"]': '_onOpen',
        'click [data-confirm-cancel="1"]': '_onCancel',
        'click [data-confirm-submit="1"]': '_onConfirm',
    },

    start() {
        this.dialog = this.el.querySelector('[data-confirm-dialog="1"]');
        this._onKeydown = (ev) => {
            if (ev.key === 'Escape') { this._close(); }
        };
        return this._super(...arguments);
    },

    destroy() {
        this._close();
        return this._super(...arguments);
    },

    _onOpen(ev) {
        ev.preventDefault();
        if (!this.dialog) { return; }
        this.dialog.classList.remove('d-none');
        document.body.style.overflow = 'hidden';
        document.addEventListener('keydown', this._onKeydown);
    },

    _onCancel(ev) {
        ev.preventDefault();
        this._close();
    },

    _close() {
        if (!this.dialog) { return; }
        this.dialog.classList.add('d-none');
        document.body.style.overflow = '';
        document.removeEventListener('keydown', this._onKeydown);
    },

    /**
     * Send the deletion ourselves instead of letting the form navigate.
     *
     * A plain submit did reach the server and returned its 303, but the browser never
     * followed it: the page just sat there, which read as "the button does nothing"
     * and had people tapping it over and over. Owning the request means the outcome is
     * ours to decide - we know when it finished, we can show progress meanwhile, and
     * we go to the list explicitly rather than hoping a redirect is followed.
     */
    async _onConfirm(ev) {
        ev.preventDefault();
        if (this._busy) { return; }
        this._busy = true;

        const button = ev.currentTarget;
        const originalHtml = button.innerHTML;
        const cancelButton = this.el.querySelector('[data-confirm-cancel="1"]');
        button.innerHTML = '<span class="dt-btn-spinner"></span> Đang xoá...';
        button.disabled = true;
        if (cancelButton) { cancelButton.disabled = true; }

        const returnInput = this.el.querySelector('input[name="return_to"]');
        const target = (returnInput && returnInput.value) || '/my/apps/expenses/history';

        try {
            const response = await fetch(this.el.action, {
                method: 'POST',
                body: new FormData(this.el),
            });
            if (!response.ok) { throw new Error('delete failed'); }
            // replace(), not assign(): the record is gone, so its detail page should not
            // stay in history for the back button to land on.
            window.location.replace(target);
        } catch (_e) {
            this._busy = false;
            button.disabled = false;
            button.innerHTML = originalHtml;
            if (cancelButton) { cancelButton.disabled = false; }
            const text = this.el.querySelector('.dt-confirm__text');
            if (text) { text.textContent = 'Xoá không thành công. Bạn thử lại giúp mình nhé.'; }
        }
    },
});


/**
 * Full-screen image viewer with pinch zoom, drag, double-tap zoom and swipe between
 * images.
 *
 * Attaches to any container marked data-lightbox-group; every image inside becomes a
 * tap target. Receipts are the reason this exists - they are unreadable at thumbnail
 * size, and the browser's own zoom does not reach a fixed-position gallery.
 */
const MAX_ZOOM = 5;
const DOUBLE_TAP_ZOOM = 2.5;

publicWidget.registry.DTLightbox = publicWidget.Widget.extend({
    selector: '[data-lightbox-group="1"]',
    events: {
        'click img': '_onImageClick',
    },

    start() {
        this.index = 0;
        this.scale = 1;
        this.tx = 0;
        this.ty = 0;
        this._pointers = new Map();
        this._buildOverlay();
        return this._super(...arguments);
    },

    destroy() {
        if (this.overlay && this.overlay.parentNode) { this.overlay.remove(); }
        document.removeEventListener('keydown', this._onKeydown);
        document.body.style.overflow = '';
        return this._super(...arguments);
    },

    _sources() {
        return Array.from(this.el.querySelectorAll('img')).map((img) => img.currentSrc || img.src);
    },

    _buildOverlay() {
        const overlay = document.createElement('div');
        overlay.className = 'dt-lightbox d-none';
        overlay.innerHTML = `
            <button type="button" class="dt-lightbox__close" aria-label="Đóng"><i class="fa fa-times"></i></button>
            <button type="button" class="dt-lightbox__nav dt-lightbox__nav--prev" aria-label="Ảnh trước"><i class="fa fa-chevron-left"></i></button>
            <button type="button" class="dt-lightbox__nav dt-lightbox__nav--next" aria-label="Ảnh sau"><i class="fa fa-chevron-right"></i></button>
            <div class="dt-lightbox__stage"><img class="dt-lightbox__img" alt=""/></div>
            <div class="dt-lightbox__dots"></div>
            <div class="dt-lightbox__hint">Chụm để phóng to · chạm đúp để phóng nhanh</div>
        `;
        document.body.appendChild(overlay);
        this.overlay = overlay;
        this.stage = overlay.querySelector('.dt-lightbox__stage');
        this.image = overlay.querySelector('.dt-lightbox__img');
        this.dots = overlay.querySelector('.dt-lightbox__dots');

        overlay.querySelector('.dt-lightbox__close').addEventListener('click', () => this._close());
        overlay.querySelector('.dt-lightbox__nav--prev').addEventListener('click', () => this._step(-1));
        overlay.querySelector('.dt-lightbox__nav--next').addEventListener('click', () => this._step(1));
        // Tapping the backdrop closes, but only when it is the backdrop itself: a drag
        // that ends on the stage must not be read as "dismiss".
        overlay.addEventListener('click', (ev) => { if (ev.target === overlay) { this._close(); } });

        this._onKeydown = (ev) => {
            if (this.overlay.classList.contains('d-none')) { return; }
            if (ev.key === 'Escape') { this._close(); }
            if (ev.key === 'ArrowLeft') { this._step(-1); }
            if (ev.key === 'ArrowRight') { this._step(1); }
        };

        this._bindGestures();
    },

    _bindGestures() {
        const stage = this.stage;
        stage.addEventListener('pointerdown', (ev) => {
            stage.setPointerCapture(ev.pointerId);
            this._pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
            if (this._pointers.size === 1) {
                this._dragFrom = { x: ev.clientX, y: ev.clientY, tx: this.tx, ty: this.ty, t: Date.now() };
            } else if (this._pointers.size === 2) {
                this._pinchFrom = { dist: this._pointerDistance(), scale: this.scale };
            }
        });

        stage.addEventListener('pointermove', (ev) => {
            if (!this._pointers.has(ev.pointerId)) { return; }
            this._pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
            if (this._pointers.size === 2 && this._pinchFrom) {
                const ratio = this._pointerDistance() / (this._pinchFrom.dist || 1);
                this.scale = Math.min(MAX_ZOOM, Math.max(1, this._pinchFrom.scale * ratio));
                this._apply();
            } else if (this._pointers.size === 1 && this._dragFrom && this.scale > 1) {
                // Panning only makes sense once zoomed in; below that the same gesture
                // is a swipe between images.
                this.tx = this._dragFrom.tx + (ev.clientX - this._dragFrom.x);
                this.ty = this._dragFrom.ty + (ev.clientY - this._dragFrom.y);
                this._apply();
            }
        });

        const release = (ev) => {
            const start = this._dragFrom;
            const wasSingle = this._pointers.size === 1;
            this._pointers.delete(ev.pointerId);
            if (this._pointers.size < 2) { this._pinchFrom = null; }
            if (!wasSingle || !start) { return; }
            const dx = ev.clientX - start.x;
            const dy = ev.clientY - start.y;
            const elapsed = Date.now() - start.t;
            if (this.scale === 1 && Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy)) {
                this._step(dx < 0 ? 1 : -1);
            } else if (elapsed < 250 && Math.abs(dx) < 8 && Math.abs(dy) < 8) {
                this._handleTap();
            }
            this._dragFrom = null;
        };
        stage.addEventListener('pointerup', release);
        stage.addEventListener('pointercancel', (ev) => { this._pointers.delete(ev.pointerId); this._pinchFrom = null; });

        // Trackpad / mouse wheel zoom, for desktop.
        stage.addEventListener('wheel', (ev) => {
            ev.preventDefault();
            this.scale = Math.min(MAX_ZOOM, Math.max(1, this.scale - ev.deltaY * 0.002));
            if (this.scale === 1) { this.tx = 0; this.ty = 0; }
            this._apply();
        }, { passive: false });
    },

    _pointerDistance() {
        const [a, b] = Array.from(this._pointers.values());
        return Math.hypot(a.x - b.x, a.y - b.y);
    },

    _handleTap() {
        const now = Date.now();
        if (this._lastTap && now - this._lastTap < 300) {
            this._lastTap = 0;
            this.scale = this.scale > 1 ? 1 : DOUBLE_TAP_ZOOM;
            this.tx = 0;
            this.ty = 0;
            this._apply();
        } else {
            this._lastTap = now;
        }
    },

    _apply() {
        this.image.style.transform = `translate(${this.tx}px, ${this.ty}px) scale(${this.scale})`;
        this.stage.classList.toggle('is-zoomed', this.scale > 1);
    },

    _reset() {
        this.scale = 1;
        this.tx = 0;
        this.ty = 0;
        this._apply();
    },

    _step(direction) {
        const sources = this._sources();
        if (sources.length < 2) { return; }
        this.index = (this.index + direction + sources.length) % sources.length;
        this._show();
    },

    _show() {
        const sources = this._sources();
        this.image.src = sources[this.index] || '';
        this._reset();
        this.dots.innerHTML = '';
        if (sources.length > 1) {
            sources.forEach((_src, i) => {
                const dot = document.createElement('span');
                dot.className = 'dt-lightbox__dot' + (i === this.index ? ' is-active' : '');
                this.dots.appendChild(dot);
            });
        }
        const multiple = sources.length > 1;
        this.overlay.querySelectorAll('.dt-lightbox__nav').forEach((btn) => { btn.hidden = !multiple; });
    },

    _onImageClick(ev) {
        const images = Array.from(this.el.querySelectorAll('img'));
        const clicked = images.indexOf(ev.currentTarget);
        if (clicked < 0) { return; }
        ev.preventDefault();
        this.index = clicked;
        this._show();
        this.overlay.classList.remove('d-none');
        document.body.style.overflow = 'hidden';
        document.addEventListener('keydown', this._onKeydown);
    },

    _close() {
        this.overlay.classList.add('d-none');
        document.body.style.overflow = '';
        document.removeEventListener('keydown', this._onKeydown);
        this._reset();
    },
});
