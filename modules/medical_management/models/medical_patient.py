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
    birth_date = fields.Date(
        string='Fecha de Nacimiento',
        related='partner_id.birth_date', 
        store=True, 
        readonly=True
    )
    allergies = fields.Text(string='Alergias Conocidas')
    medical_notes = fields.Text(string='Notas Médicas Generales')

    # El campo 'name' se elimina de aquí porque se hereda 
    # automáticamente de 'res.partner' a través de 'partner_id'.

    
    # # Al elegir el contacto en la UI, jala la fecha automáticamente a la pantalla del paciente
    # @api.onchange('partner_id')
    # def _onchange_partner_id_birth_date(self):
    #     if self.partner_id and self.partner_id.birth_date:
    #         self.birth_date = self.partner_id.birth_date

    # # Al crearse desde backend o procesos automatizados, asegura el guardado duplicado si no viene explícito
    # @api.model_create_multi
    # def create(self, vals_list):
    #     for vals in vals_list:
    #         if vals.get('partner_id') and 'birth_date' not in vals:
    #             partner = self.env['res.partner'].browse(vals['partner_id'])
    #             if partner.birth_date:
    #                 vals['birth_date'] = partner.birth_date
    #     return super().create(vals_list)