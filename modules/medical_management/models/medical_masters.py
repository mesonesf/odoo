from odoo import models, fields, api
from odoo.exceptions import ValidationError

class MedicalSpecialty(models.Model):
    _name = 'medical.specialty'
    _description = 'Especialidad Médica'
    
    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código', required=True)
    description = fields.Text(string='Descripción')
    active = fields.Boolean(string='Activa', default=True)

class MedicalTemplate(models.Model):
    _name = 'medical.template'
    _description = 'Plantilla Médica'
    
    name = fields.Char(string='Nombre Plantilla', required=True)
    template_type = fields.Selection([
        ('clinical_record', 'Ficha Clínica'),
        ('evaluation', 'Evaluación Médica')
    ], string='Tipo de Plantilla', required=True)
    specialty_id = fields.Many2one('medical.specialty', string='Especialidad', required=True)
    active = fields.Boolean(string='Activa', default=True)
    
    # AÑADIR ESTE CAMPO - RELACIÓN CON PREGUNTAS
    question_ids = fields.One2many('medical.template.question', 'template_id', string='Preguntas')

class MedicalTemplateQuestion(models.Model):
    _name = 'medical.template.question'
    _description = 'Pregunta de Plantilla'
    _rec_name = 'question_text'  # <--- AÑADE ESTA LÍNEA

    template_id = fields.Many2one('medical.template', string='Plantilla', required=True)
    sequence = fields.Integer(string='Orden', default=10)
    question_text = fields.Text(string='Pregunta', required=True)
    question_type = fields.Selection([
        ('boolean', 'Sí/No'),
        ('text', 'Texto Abierto')
    ], string='Tipo de Pregunta', required=True, default='text')
    required = fields.Boolean(string='Requerida', default=False)
