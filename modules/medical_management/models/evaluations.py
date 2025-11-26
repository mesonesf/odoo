from odoo import models, fields, api, Command
from odoo.exceptions import ValidationError, UserError
import logging
_logger = logging.getLogger(__name__)

class MedicalEvaluation(models.Model):
    _name = 'medical.evaluation'
    _description = 'Evaluación Médica'
    _order = 'date desc'
    
    name = fields.Char(string='Referencia', readonly=True, default='Nuevo')
    patient_id = fields.Many2one('medical.patient', string='Paciente', required=True, ondelete='restrict')
    specialty_id = fields.Many2one('medical.specialty', string='Especialidad', required=True, ondelete='restrict')
    date = fields.Datetime(string='Fecha de Evaluación', default=fields.Datetime.now, required=True)
    practitioner_id = fields.Many2one('hr.employee', string='Especialista', required=True, ondelete='restrict')
    
    clinical_record_id = fields.Many2one('medical.clinical.record', string='Ficha Clínica', 
                                       readonly=True, ondelete='restrict')
    
    template_id = fields.Many2one(
        'medical.template', 
        string='Plantilla',
        domain="[('template_type', '=', 'evaluation'), ('specialty_id', '=', specialty_id), ('active', '=', True)]",
        required=True,
        ondelete='restrict'
    )
    answer_ids = fields.One2many('medical.record.answer', 'evaluation_id', string='Respuestas')
    
    attachment_image = fields.Binary(string='Imagen Adjunta')
    attachment_filename = fields.Char(string='Nombre Archivo')
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('completed', 'Completada')
    ], string='Estado', default='draft')
    
    # Campo comentado temporalmente para evitar warning en la instalación
    # Cuando creemos el modelo 'medical.treatment', quitaremos el '#'
    treatment_id = fields.Many2one('medical.treatment', string='Tratamiento Relacionado', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        _logger.warning("="*50)
        _logger.warning("*** DEBUG: Evaluación create() EJECUTADO ***")
        _logger.warning("="*50)

        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('medical.evaluation') or 'Nuevo'
            
            if 'template_id' not in vals and 'specialty_id' in vals:
                template = self.env['medical.template'].search([
                    ('specialty_id', '=', vals['specialty_id']),
                    ('template_type', '=', 'evaluation'),
                    ('active', '=', True)
                ], limit=1)
                
                if template:
                    vals['template_id'] = template.id
                else:
                    specialty_name = self.env['medical.specialty'].browse(vals['specialty_id']).name
                    raise ValidationError(
                        f"No se puede crear la Evaluación. "
                        f"No se encontró una Plantilla de Evaluación activa "
                        f"para la especialidad '{specialty_name}'.\n\n"
                        f"Por favor, vaya a Configuración > Plantillas y cree una."
                    )

        records = super().create(vals_list)
        
        for record in records:
            if record.template_id and not record.answer_ids:
                record._create_answers_from_template()
        
        return records

    def write(self, vals):
        for record in self:
            if record.state == 'completed' and any(field in vals for field in ['answer_ids', 'template_id']):
                raise UserError('No se puede modificar una evaluación completada.')
        return super().write(vals)

    def _create_answers_from_template(self):
        """Crear respuestas vacías desde la plantilla (para backend)"""
        vals_list = []
        for question in self.template_id.question_ids:
            vals_list.append({
                'evaluation_id': self.id,
                'question_id': question.id,
            })
        if vals_list:
            self.env['medical.record.answer'].create(vals_list)

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Actualizar respuestas cuando cambia la plantilla (para UI)"""
        if not self.template_id:
            self.answer_ids = [Command.clear()]
            return
            
        if self.state == 'draft':
            new_answers = [Command.clear()]
            for question in self.template_id.question_ids:
                new_answers.append(Command.create({
                    'question_id': question.id,
                }))
            self.answer_ids = new_answers

    def action_complete(self):
        self.ensure_one()
        if not self.answer_ids:
            raise ValidationError('Debe completar las respuestas de la evaluación.')
        
        if self.template_id:
            required_questions = self.template_id.question_ids.filtered(lambda q: q.required)
            for question in required_questions:
                answer = self.answer_ids.filtered(lambda a: a.question_id == question)
                is_answered = False
                if answer:
                    if question.question_type == 'boolean':
                        is_answered = True
                    elif question.question_type == 'text':
                        is_answered = bool(answer.text_answer)
                
                if not is_answered:
                    raise ValidationError(f'La pregunta "{question.text}" es requerida.')
        
        self.state = 'completed'

    def action_create_treatment(self):
        self.ensure_one()
        if self.state != 'completed':
            raise ValidationError('Debe completar la evaluación antes de crear un tratamiento.')
        
        if self.treatment_id:
             raise ValidationError('Esta evaluación ya tiene un tratamiento relacionado.')
        
        treatment = self.env['medical.treatment'].create({
             'patient_id': self.patient_id.id,
             'evaluation_id': self.id,
             'specialty_id': self.specialty_id.id,
             'practitioner_id': self.practitioner_id.id,
         })
        self.treatment_id = treatment.id
        
        return {
             'type': 'ir.actions.act_window',
             'name': 'Plan de Tratamiento',
             'res_model': 'medical.treatment',
             'res_id': treatment.id,
             'view_mode': 'form',
             'target': 'current',
         }
        #raise UserError("La creación de tratamientos aún no está implementada.")


    def action_view_treatment(self):
        """Ver tratamiento relacionado"""
        self.ensure_one()
        if not self.treatment_id:
             raise UserError('No hay tratamiento relacionado con esta evaluación.')
        return {
             'type': 'ir.actions.act_window',
             'name': 'Tratamiento',
             'res_model': 'medical.treatment',
             'res_id': self.treatment_id.id,
             'view_mode': 'form',
             'target': 'current',
         }
        #raise UserError("La vista de tratamientos aún no está implementada.")

    
    def action_view_clinical_record(self):
        """Ver ficha clínica relacionada"""
        self.ensure_one()
        if not self.clinical_record_id:
             raise UserError('No hay ficha clínica vinculada.')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ficha Clínica',
            'res_model': 'medical.clinical.record',
            'res_id': self.clinical_record_id.id,
            'view_mode': 'form',
            'target': 'current',
        }