from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Campo de Selección con tus valores específicos
    tamano_empresa = fields.Selection([
        ('MICRO', 'Microempresa (1-10)'),
        ('PEQUEÑA', 'Pequeña (11-50)'),
        ('MEDIANA', 'Mediana (51-250)'),
        ('GRANDE', 'Grande (250+)'),
        ('CORPORATIVA', 'Corporación')
    ], string='Tamaño de Empresa', help="Clasificación para segmentación de CRM")

    # Campo Numérico para escribir la cantidad exacta (ej. 45, 120)
    # Esto te permitirá sacar promedios en el CRM.
    numero_trabajadores = fields.Integer(string='Nº Trabajadores')