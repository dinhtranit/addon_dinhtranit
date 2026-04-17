# -*- coding: utf-8 -*-
{
    "name": "DT Memoire",
    "version": "19.0.1.0.0",
    "summary": "Timeline kỷ niệm mobile-first cho gia đình",
    "category": "Website",
    "author": "DT",
    "license": "LGPL-3",
    "depends": ["dt_core", "mail", "portal", "website", "web"],
    "data": [
        "security/ir.model.access.csv",
        "data/dt_memoire_data.xml",
        "views/dt_memoire_backend_views.xml",
        "templates/dt_memoire_templates.xml",
    ],
    "assets": {"web.assets_frontend": ["dt_memoire/static/src/css/dt_memoire_portal.scss"]},
    "application": True,
    "installable": True,
}
