from odoo import models, fields

class PayloadDebug(models.TransientModel):
    _name = 'payload.debug'
    _description = 'Detalle del Payload'

    invoice_id = fields.Many2one('account.move', string='Factura')
    payload_data = fields.Text(string='JSON del Payload')
    line_details = fields.Text(string='Detalle de Líneas')
