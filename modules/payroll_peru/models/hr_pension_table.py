# -*- coding: utf-8 -*-
from odoo import models, fields

class HrPensionSystem(models.Model):
    _name = 'hr.pension.system'
    _description = 'Sistema de Pensiones Peruano (AFP/ONP)'

    name = fields.Char("Nombre", required=True)
    type = fields.Selection([('afp', 'AFP'), ('onp', 'ONP')], string="Tipo", required=True)
    
    # Porcentajes expresados en decimales (Ej: 0.10 para 10%)
    ao_percent = fields.Float("Aporte Obligatorio %", digits=(12, 4))
    ps_percent = fields.Float("Prima de Seguro %", digits=(12, 4))
    cf_percent = fields.Float("Comisión Flujo %", digits=(12, 4))
    cm_percent = fields.Float("Comisión Mixta %", digits=(12, 4))

class HrQuintaEscala(models.Model):
    _name = 'hr.quinta.escala'
    _description = 'Escalas de Impuesto a la Renta de Quinta Categoría'
    _order = 'sequence'

    sequence = fields.Integer(string="Orden", default=10)
    name = fields.Char(string="Tramo", required=True)
    limit_uit = fields.Float(string="Límite hasta (UIT)")
    rate = fields.Float(string="Tasa de Impuesto (%)")