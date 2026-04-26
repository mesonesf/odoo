from odoo import models, fields

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    is_teacher = fields.Boolean(string="Es Docente", default=False)
    academic_degree = fields.Selection([
        ('technical', 'Técnico'),
        ('bachelor', 'Bachiller'),
        ('professional', 'Titulado'),
        ('master', 'Magíster'),
        ('doctor', 'Doctor')
    ], string="Grado Académico")
    specialty = fields.Char(string="Especialidad / Facultad")