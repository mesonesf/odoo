from odoo import models, fields

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # 4. Hipervínculo (Usamos Char, Odoo lo vuelve link si parece URL, o widget="url")
    enlace_externo = fields.Char(string='Link Documentación / Carpeta')