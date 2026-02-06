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
    
    treatment_id = fields.Many2one('medical.treatment', string='Tratamiento Relacionado', readonly=True)

    # --- MÉTODO REFORZADO: CREATE ---
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('medical.evaluation') or 'Nuevo'
            
            # 1. Autoselección de plantilla si no viene en los valores
            if 'template_id' not in vals and 'specialty_id' in vals:
                template = self.env['medical.template'].search([
                    ('specialty_id', '=', vals['specialty_id']),
                    ('template_type', '=', 'evaluation'),
                    ('active', '=', True)
                ], limit=1)
                if template:
                    vals['template_id'] = template.id

        records = super().create(vals_list)
        
        # 2. Carga de respuestas (Nueva lógica que busca historial)
        for record in records:
            if record.template_id and not record.answer_ids:
                record._load_answers_logic()
        
        return records

    def _load_answers_logic(self):
        """Busca historial o crea respuestas vacías (Funciona para UI y para el servidor)"""
        self.ensure_one()
        
        # Buscamos la última evaluación completada de este paciente con esta misma plantilla
        last_eval = self.search([
            ('patient_id', '=', self.patient_id.id),
            ('template_id', '=', self.template_id.id),
            ('state', '=', 'completed'),
            ('id', '!=', self.id) # Que no sea la actual
        ], order='date desc', limit=1)

        vals_list = []
        if last_eval:
            _logger.info(f"HEREDANDO HISTORIAL: Evaluación {self.name} copia a {last_eval.name}")
            for old_ans in last_eval.answer_ids:
                vals_list.append({
                    'evaluation_id': self.id,
                    'question_id': old_ans.question_id.id,
                    'boolean_answer': old_ans.boolean_answer,
                    'text_answer': old_ans.text_answer,
                })
        else:
            # Si no hay historial, cargar plantilla vacía
            for question in self.template_id.question_ids:
                vals_list.append({
                    'evaluation_id': self.id,
                    'question_id': question.id,
                })
        
        if vals_list:
            self.env['medical.record.answer'].create(vals_list)

    # --- UI ONCHANGES (Para cuando creas manualmente en el módulo) ---

    @api.onchange('patient_id')
    def _onchange_patient_id_load_history(self):
        if self.patient_id and self.state == 'draft':
            last_eval = self.search([
                ('patient_id', '=', self.patient_id.id),
                ('state', '=', 'completed')
            ], order='date desc', limit=1)
            
            if last_eval:
                self.specialty_id = last_eval.specialty_id
                self.practitioner_id = last_eval.practitioner_id

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Actualiza la vista previa de respuestas en la web"""
        if not self.template_id:
            self.answer_ids = [Command.clear()]
            return
        
        if self.state == 'draft':
            # Limpiamos y dejamos que el sistema cargue
            self.answer_ids = [Command.clear()]
            # Esta llamada simula la lógica de búsqueda de historial en la UI
            last_eval = self.search([
                ('patient_id', '=', self.patient_id.id),
                ('template_id', '=', self.template_id.id),
                ('state', '=', 'completed')
            ], order='date desc', limit=1)

            new_answers = []
            if last_eval:
                for old_ans in last_eval.answer_ids:
                    new_answers.append(Command.create({
                        'question_id': old_ans.question_id.id,
                        'boolean_answer': old_ans.boolean_answer,
                        'text_answer': old_ans.text_answer,
                    }))
            else:
                for question in self.template_id.question_ids:
                    new_answers.append(Command.create({
                        'question_id': question.id,
                    }))
            self.answer_ids = new_answers

    # --- ACCIONES RESTANTES ---

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

    def action_view_treatment(self):
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

    def action_view_clinical_record(self):
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