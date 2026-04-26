from odoo import models, fields

class EducationCourse(models.Model):
    _name = 'education.course'
    _description = 'Catálogo de Cursos / Materias'

    name = fields.Char(string="Nombre de la Materia", required=True)
    code = fields.Char(string="Código", required=True)
    credits = fields.Float(string="Créditos Académicos", default=1.0)
    active = fields.Boolean(default=True)