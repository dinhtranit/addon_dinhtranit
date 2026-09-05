# -*- coding: utf-8 -*-
import base64
import json
import re
from email.utils import formatdate

from odoo import http
from odoo.http import request
from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.wrappers import Response


class FamilyMediaPortal(http.Controller):

    # Models the portal is allowed to stage uploads for. Anything else is refused so a
    # crafted request cannot create attachments pointing at arbitrary models.
    STAGED_UPLOAD_MODELS = ("dt.expense.entry", "dt.memoire.diary")

    @http.route("/my/family/media/upload", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def media_upload(self, res_model="", **kw):
        """Upload a single file before its record exists.

        The portal calls this as soon as a photo is picked, so the slow part (transfer
        plus image processing) overlaps with the user filling in the rest of the form.
        Saving the form afterwards only has to reference the returned media id.
        """
        if res_model not in self.STAGED_UPLOAD_MODELS:
            return self._json_response({"error": "res_model_not_allowed"}, status=400)
        upload = request.httprequest.files.get("file")
        if not upload:
            return self._json_response({"error": "no_file"}, status=400)
        try:
            media = request.env["dt.media"].sudo().create_staged_upload(
                upload, res_model, owner_user=request.env.user
            )
        except Exception:
            request.env.cr.rollback()
            return self._json_response({"error": "upload_failed"}, status=500)
        if not media:
            return self._json_response({"error": "empty_file"}, status=400)
        return self._json_response({
            "id": media.id,
            "url": media.image_url(),
            "media_type": media.media_type,
            "name": media.name,
        })

    def _json_response(self, payload, status=200):
        return request.make_response(
            json.dumps(payload),
            headers=[("Content-Type", "application/json")],
            status=status,
        )

    @http.route("/my/family/media/<int:media_id>/content", type="http", auth="user", website=True)
    def media_content(self, media_id, download="", **kw):
        media = request.env["dt.media"].sudo().browse(media_id)
        if not media.exists() or not media.attachment_id.exists():
            raise NotFound()
        if not media.can_read(request.env.user):
            raise Forbidden()
        attachment = media.attachment_id.sudo()
        raw = base64.b64decode(attachment.datas or b"")
        total = len(raw)
        mimetype = media.mimetype or attachment.mimetype or "application/octet-stream"
        filename = (media.original_filename or attachment.name or media.name or "file").replace('"', "")
        disposition_type = "attachment" if str(download).lower() in ("1", "true", "yes") else "inline"
        headers = [
            ("Content-Type", mimetype),
            ("Accept-Ranges", "bytes"),
            ("Cache-Control", "private, max-age=3600"),
            ("Last-Modified", formatdate(usegmt=True)),
            ("Content-Disposition", f'{disposition_type}; filename="{filename}"'),
        ]
        range_header = request.httprequest.headers.get("Range")
        if range_header and total:
            match = re.match(r"bytes=(\d*)-(\d*)", range_header)
            if match:
                start_s, end_s = match.groups()
                if start_s:
                    start = int(start_s)
                    end = int(end_s) if end_s else total - 1
                else:
                    suffix = int(end_s or 0)
                    start = max(total - suffix, 0)
                    end = total - 1
                start = max(0, min(start, total - 1))
                end = max(start, min(end, total - 1))
                chunk = raw[start:end + 1]
                headers.extend([
                    ("Content-Range", f"bytes {start}-{end}/{total}"),
                    ("Content-Length", str(len(chunk))),
                ])
                return Response(chunk, status=206, headers=headers)
        headers.append(("Content-Length", str(total)))
        return Response(raw, status=200, headers=headers)
