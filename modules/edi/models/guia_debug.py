from odoo import models, fields

class GuiaDebug(models.TransientModel):
    _name = 'guia.debug'
    _description = 'Detalle de la guia'

    guia_id = fields.Many2one('stock.picking', string='Guia')
    guia_data = fields.Text(string='JSON de la Guía')
    line_details = fields.Text(string='Detalle de Líneas')