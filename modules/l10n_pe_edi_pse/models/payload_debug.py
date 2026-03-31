from odoo import models, fields

class PayloadDebug(models.TransientModel):
    _name = 'payload.debug'
    _description = 'Visor de JSON para PSE'

    invoice_id = fields.Many2one('account.move', string='Factura Referencia')
    payload_data = fields.Text(string='JSON a Enviar')
    line_details = fields.Text(string='Detalle de Líneas')