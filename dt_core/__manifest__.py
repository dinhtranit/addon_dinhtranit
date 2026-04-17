# -*- coding: utf-8 -*-
{
    "name": "DT Core",
    "version": "19.0.1.0.0",
    "summary": "Khung app chung cho bộ module DT",
    "category": "Website",
    "author": "DT",
    "license": "LGPL-3",
    "depends": ["base", "mail", "portal", "website", "web"],
    "data": [
        "security/ir.model.access.csv",
        "data/dt_core_data.xml",
        "views/dt_core_backend_views.xml",
        "templates/dt_core_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "dt_core/static/src/css/dt_core_portal.scss",
        ],
    },
    "application": False,
    "installable": True,
}
