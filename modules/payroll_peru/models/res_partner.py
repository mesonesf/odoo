# -*- coding: utf-8 -*-
from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_derechohabiente = fields.Boolean("Es Derechohabiente (T-Registro)")
    parent_employee_id = fields.Many2one('hr.employee', string="Empleado Relacionado")
    relationship_type = fields.Selection([
        ('01', 'Cónyuge'),
        ('02', 'Concubino'),
        ('03', 'Hijo Menor de Edad'),
        ('04', 'Hijo Mayor Incapacitado')
    ], string="Tipo de Vínculo")