from odoo import models, fields

class EducationClassroom(models.Model):
    _name = 'education.classroom'
    _description = 'Aula o Laboratorio'

    name = fields.Char(string="Nombre del Aula", required=True)
    location = fields.Char(string="Pabellón / Piso")
    capacity = fields.Integer(string="Aforo Máximo", required=True, default=30)
    classroom_type = fields.Selection([
        ('theory', 'Aula de Teoría'),
        ('lab', 'Laboratorio'),
        ('workshop', 'Taller'),
        ('auditorium', 'Auditorio')
    ], string="Tipo de Ambiente", default='theory')