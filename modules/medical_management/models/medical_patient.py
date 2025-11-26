from odoo import models, fields, api

class MedicalPatient(models.Model):
    _name = 'medical.patient'
    _description = 'Paciente'
    _inherits = {'res.partner': 'partner_id'}
    
    partner_id = fields.Many2one('res.partner', string='Contacto', required=True, ondelete='cascade')
    
    # Datos médicos
    blood_type = fields.Selection([
        ('a_positive', 'A+'), ('a_negative', 'A-'),
        ('b_positive', 'B+'), ('b_negative', 'B-'),
        ('ab_positive', 'AB+'), ('ab_negative', 'AB-'),
        ('o_positive', 'O+'), ('o_negative', 'O-'),
    ], string='Tipo de Sangre')
    skin_color = fields.Char(string='Color de Piel')
    gender = fields.Selection([
        ('male', 'Masculino'),
        ('female', 'Femenino'),
        ('other', 'Otro')
    ], string='Sexo')
    birth_date = fields.Date(string='Fecha de Nacimiento')
    allergies = fields.Text(string='Alergias Conocidas')
    medical_notes = fields.Text(string='Notas Médicas Generales')

    # El campo 'name' se elimina de aquí porque se hereda 
    # automáticamente de 'res.partner' a través de 'partner_id'.