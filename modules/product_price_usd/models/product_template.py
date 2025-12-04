# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Campo auxiliar para definir que este precio es en Dólares
    currency_usd_id = fields.Many2one(
        'res.currency', 
        string='Moneda USD', 
        default=lambda self: self.env.ref('base.USD').id,
        readonly=True
    )

    # El campo donde escribirás el precio (ej. 120.00)
    price_usd = fields.Monetary(
        string='Precio Venta USD',
        currency_field='currency_usd_id',
        help="Ingrese aquí el precio fijo en dólares para este producto."
    )