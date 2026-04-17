# -*- coding: utf-8 -*-
{
    "name": "DT Expense",
    "version": "19.0.1.0.0",
    "summary": "Quản lý chi tiêu hằng ngày mobile-first",
    "category": "Website",
    "author": "DT",
    "license": "LGPL-3",
    "depends": ["dt_core", "portal", "website", "web"],
    "data": [
        "security/ir.model.access.csv",
        "data/dt_expense_data.xml",
        "views/dt_expense_backend_views.xml",
        "templates/dt_expense_templates.xml",
    ],
    "assets": {"web.assets_frontend": ["dt_expense/static/src/css/dt_expense_portal.scss"]},
    "application": True,
    "installable": True,
}
