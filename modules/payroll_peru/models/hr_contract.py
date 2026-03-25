# -*- coding: utf-8 -*-
from odoo import models, fields

class HrContract(models.Model):
    _inherit = 'hr.contract'

    labor_regime = fields.Selection([
        ('728', 'General (D.L. 728)'),
        ('mype_micro', 'MYPE - Micro Empresa'),
        ('mype_pequena', 'MYPE - Pequeña Empresa'),
        ('agrario', 'Agrario')
    ], string="Régimen Laboral", default='728')

    pension_system_id = fields.Many2one('hr.pension.system', string="Sistema de Pensiones")
    cuspp = fields.Char("Código CUSPP")
    has_family_allowance = fields.Boolean("¿Percibe Asignación Familiar?", default=False)

    # Datos para Quinta Categoría
    other_incomes = fields.Float("Otros Ingresos (Otros Empleadores)", default=0.0)
    accumulated_retention = fields.Float("Retención Acumulada del Año", default=0.0)
    accumulated_remuneration = fields.Float("Remuneración Acumulada del Año", default=0.0)