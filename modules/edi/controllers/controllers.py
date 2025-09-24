# -*- coding: utf-8 -*-
# from odoo import http


# class Edi(http.Controller):
#     @http.route('/edi/edi', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/edi/edi/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('edi.listing', {
#             'root': '/edi/edi',
#             'objects': http.request.env['edi.edi'].search([]),
#         })

#     @http.route('/edi/edi/objects/<model("edi.edi"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('edi.object', {
#             'object': obj
#         })

#########################################################################################################
from odoo import http
import requests

class APIController(http.Controller):
    
    @http.route('/api/verify_invoice', type='json', auth='none')
    def verify_invoice(self, **kw):
        # Endpoint alternativo si necesitas recibir callbacks
        return {'status': 'received'}
