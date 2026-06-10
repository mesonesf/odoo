from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Agregamos el campo en contactos
    birth_date = fields.Date(string='Fecha de Nacimiento')