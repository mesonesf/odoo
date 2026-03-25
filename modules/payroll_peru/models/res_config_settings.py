# -*- coding: utf-8 -*-
from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Definimos los campos que se verán en Ajustes
    # El parámetro 'config_parameter' hace que se guarden automáticamente en Parámetros del Sistema
    peru_uit = fields.Float(
        string="UIT Actual (S/)", 
        config_parameter='payroll_peru.peru_uit', 
        default=5150.0
    )
    peru_rmv = fields.Float(
        string="RMV Actual (S/)", 
        config_parameter='payroll_peru.peru_rmv', 
        default=1025.0
    )