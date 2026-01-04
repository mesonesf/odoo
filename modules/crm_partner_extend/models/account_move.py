# import logging
# from odoo import models, fields, api

# _logger = logging.getLogger(__name__)

# class AccountMove(models.Model):
#     _inherit = 'account.move'

#     def action_post(self):
#         # 1. Ejecutar la validación original de Odoo
#         res = super(AccountMove, self).action_post()
        
#         # 2. Cambiar tipo de cuenta al validar factura de cliente
#         for move in self:
#             if move.move_type == 'out_invoice' and move.partner_id:
#                 _logger.info(">>> Actualizando cliente %s a Mantenimiento", move.partner_id.name)
#                 # El cambio se hace en la ficha del contacto principal
#                 move.partner_id.tipo_cuenta = 'mantenimiento'
        
#         return res
from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        res = super(AccountMove, self).action_post()
        for move in self:
            if move.move_type == 'out_invoice' and move.partner_id:
                move.partner_id.tipo_cuenta = 'mantenimiento'
        return res