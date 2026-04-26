from odoo import models, fields

class EducationAcademicPeriod(models.Model):
    _name = 'education.academic.period'
    _description = 'Periodo Académico (Año Escolar / Ciclo Universitario)'

    name = fields.Char(string="Nombre del Periodo", required=True, help="Ej. Ciclo 2026-I, Año Escolar 2026")
    start_date = fields.Date(string="Fecha de Inicio", required=True)
    end_date = fields.Date(string="Fecha de Fin", required=True)
    active = fields.Boolean(default=True)