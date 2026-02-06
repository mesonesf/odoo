from odoo import models, fields, api, Command
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

class MedicalClinicalRecord(models.Model):
    _name = 'medical.clinical.record'
    _description = 'Ficha Clínica'
    _order = 'date desc'
    
    name = fields.Char(string='Referencia', readonly=True, default='Nuevo')
    
    patient_id = fields.Many2one('medical.patient', string='Paciente', required=True, ondelete='restrict')
    specialty_id = fields.Many2one('medical.specialty', string='Especialidad', required=True, ondelete='restrict')
    practitioner_id = fields.Many2one('hr.employee', string='Especialista', required=True, ondelete='restrict')

    date = fields.Datetime(string='Fecha de Atención', default=fields.Datetime.now, required=True)
    
    template_id = fields.Many2one(
        'medical.template', 
        string='Plantilla', 
        domain="[('template_type', '=', 'clinical_record'), ('specialty_id', '=', specialty_id), ('active', '=', True)]"
    )
    answer_ids = fields.One2many('medical.record.answer', 'clinical_record_id', string='Respuestas')
    
    attachment_image = fields.Binary(string='Imagen Adjunta')
    attachment_filename = fields.Char(string='Nombre Archivo')
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('completed', 'Completada')
    ], string='Estado', default='draft')
    
    evaluation_id = fields.Many2one('medical.evaluation', string='Evaluación Relacionada', readonly=True)

    # --- PUNTO 3: AUTO-COMPLETADO BASADO EN HISTORIAL ---
    
    @api.onchange('patient_id')
    def _onchange_patient_id_load_history(self):
        """Al elegir paciente, sugerir especialidad y especialista de su última atención"""
        if self.patient_id and self.state == 'draft':
            last_record = self.search([
                ('patient_id', '=', self.patient_id.id),
                ('state', '=', 'completed')
            ], order='date desc', limit=1)
            
            if last_record:
                self.specialty_id = last_record.specialty_id
                self.practitioner_id = last_record.practitioner_id
                # El cambio de specialty_id disparará _onchange_specialty_id automáticamente

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Cargar respuestas de la plantilla o heredar de la última atención si coinciden"""
        if not self.template_id:
            self.answer_ids = [Command.clear()]
            return
        
        if self.state == 'draft':
            # Buscamos si el paciente tiene una ficha previa CON ESTA MISMA PLANTILLA
            last_record = self.search([
                ('patient_id', '=', self.patient_id.id),
                ('template_id', '=', self.template_id.id),
                ('state', '=', 'completed')
            ], order='date desc', limit=1)

            new_answers = [Command.clear()]
            
            if last_record:
                # HEREDAR: Copiamos los valores de la ficha anterior
                for old_ans in last_record.answer_ids:
                    new_answers.append(Command.create({
                        'question_id': old_ans.question_id.id,
                        'boolean_answer': old_ans.boolean_answer,
                        'text_answer': old_ans.text_answer,
                    }))
                _logger.info(f"Heredando datos de la Ficha {last_record.name} para el paciente {self.patient_id.name}")
            else:
                # NUEVO: Crear respuestas vacías basadas en la plantilla
                for question in self.template_id.question_ids:
                    new_answers.append(Command.create({
                        'question_id': question.id,
                    }))
            
            self.answer_ids = new_answers

    # --- FIN PUNTO 3 ---

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('medical.clinical.record') or 'Nuevo'
        return super().create(vals_list)

    def write(self, vals):
        for record in self:
            if record.state == 'completed' and any(field in vals for field in ['answer_ids', 'template_id']):
                raise UserError('No se puede modificar una ficha clínica completada.')
        return super().write(vals)

    @api.onchange('specialty_id')
    def _onchange_specialty_id(self):
        if self.specialty_id:
            if self.template_id and self.template_id.specialty_id != self.specialty_id:
                self.template_id = False
            
            templates = self.env['medical.template'].search([
                ('specialty_id', '=', self.specialty_id.id),
                ('template_type', '=', 'clinical_record'),
                ('active', '=', True)
            ])
            if len(templates) == 1:
                self.template_id = templates.id
        else:
            self.template_id = False

    def action_complete(self):
        self.ensure_one()
        if not self.answer_ids:
            raise ValidationError('Debe completar las respuestas de la ficha clínica.')
        
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
        
        evaluation = self.env['medical.evaluation'].create({
            'patient_id': self.patient_id.id,
            'specialty_id': self.specialty_id.id,
            'practitioner_id': self.practitioner_id.id,
            'clinical_record_id': self.id,
        })
        self.evaluation_id = evaluation.id
        self.state = 'completed'
        return True

    def action_view_evaluation(self):
        self.ensure_one()
        if not self.evaluation_id:
            raise UserError('No hay evaluación relacionada.')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Evaluación',
            'res_model': 'medical.evaluation',
            'res_id': self.evaluation_id.id,
            'view_mode': 'form',
            'target': 'current',
        }