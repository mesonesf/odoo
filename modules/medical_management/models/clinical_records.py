from odoo import models, fields, api, Command
from odoo.exceptions import ValidationError, UserError
import logging  # Importar logging
_logger = logging.getLogger(__name__) # Definir el logger

class MedicalClinicalRecord(models.Model):
    _name = 'medical.clinical.record'
    _description = 'Ficha Clínica'
    _order = 'date desc'
    
    name = fields.Char(string='Referencia', readonly=True, default='Nuevo')
    
    # --- CAMBIO: Añadido ondelete='restrict' ---
    # Esto previene que un Paciente sea borrado si tiene fichas.
    patient_id = fields.Many2one('medical.patient', string='Paciente', required=True, ondelete='restrict')
    specialty_id = fields.Many2one('medical.specialty', string='Especialidad', required=True, ondelete='restrict')
    practitioner_id = fields.Many2one('hr.employee', string='Especialista', required=True, ondelete='restrict')
    # --- FIN CAMBIO ---

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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('medical.clinical.record') or 'Nuevo'
        records = super().create(vals_list)
        return records

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

    @api.onchange('template_id')
    def _onchange_template_id(self):
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
        """Completar ficha clínica y crear evaluación (PLAN B)"""
        _logger.warning("="*50)
        _logger.warning("*** DEBUG: Ficha Clínica action_complete() EJECUTADO ***")
        _logger.warning("="*50)

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