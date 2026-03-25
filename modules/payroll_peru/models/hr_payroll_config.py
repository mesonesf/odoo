from odoo import models, fields, api

class HrPayrollConfigPeru(models.Model):
    _name = 'hr.payroll.config.peru'
    _description = 'Parámetros Globales de Planilla Perú'

    name = fields.Char(string="Año", required=True)
    uit_value = fields.Float(string="Valor UIT", default=5150.0)
    rmv_value = fields.Float(string="Sueldo Mínimo (RMV)", default=1025.0)
    active = fields.Boolean(default=True)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Campos que aparecerán en Ajustes
    peru_uit = fields.Float(string="UIT Actual", config_parameter='payroll_peru.uit')
    peru_rmv = fields.Float(string="RMV Actual", config_parameter='payroll_peru.rmv')