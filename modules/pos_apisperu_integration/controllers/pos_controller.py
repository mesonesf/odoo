from odoo import http
from odoo.http import request

class CustomPosController(http.Controller):

    @http.route('/api/pos/confirmar', type='json', auth='user', csrf=False)
    def confirmar_pedido(self, **payload):
        """
        Endpoint nativo que reemplaza al controlador de Laravel.
        Recibe el mismo JSON desde tu frontend/app.
        """
        return request.env['pos.order'].sudo().procesar_pedido_custom(payload)
