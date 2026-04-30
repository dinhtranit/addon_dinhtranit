# -*- coding: utf-8 -*-
from odoo import http
from odoo.addons.portal.controllers.web import is_user_internal, Home as PortalHome
from odoo.http import request


class Home(PortalHome):

    @http.route()
    def index(self, *args, **kw):
        if request.session.uid and not is_user_internal(request.session.uid):
            return request.redirect_query('/my/apps/expenses', query=request.params)
        return super().index(*args, **kw)

    def _login_redirect(self, uid, redirect=None):
        if not redirect:
            redirect = '/my/apps/expenses'
        return super()._login_redirect(uid, redirect=redirect)

    @http.route()
    def web_client(self, s_action=None, **kw):
        if request.session.uid and not is_user_internal(request.session.uid):
            return request.redirect_query('/my/apps/expenses', query=request.params)
        return super().web_client(s_action, **kw)

class DtHomeController(http.Controller):

    @http.route('/', type='http', auth='public', website=True)
    def dt_home_redirect(self, **kw):
        if request.env.user and not request.env.user._is_public():
            return request.redirect('/my/apps/expenses')
        return request.redirect('/web/login')