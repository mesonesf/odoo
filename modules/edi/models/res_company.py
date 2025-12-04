# -*- coding: utf-8 -*-
from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    # Campo para el Token (36 caracteres)
    service_token = fields.Char(
         string='Token de Servicio',
         size=36,
         help="Token de seguridad de 36 caracteres para integración."
     )

     # Campo para el Código (5 caracteres)
    service_code = fields.Char(
         string='Código de Servicio',
         size=5,
         help="Código corto de 5 caracteres."
     )

     # NUEVO CAMPO: URL del Servicio
    service_url = fields.Char(
         string='URL del API',
         help="Dirección web del servicio (Endpoint). Ej: https://api.miservicio.com"
     )