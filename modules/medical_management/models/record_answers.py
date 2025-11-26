from odoo import models, fields, api
from odoo.exceptions import ValidationError

class MedicalRecordAnswer(models.Model):
    _name = 'medical.record.answer'
    _description = 'Respuesta de Ficha/Evaluación'
    
    # --- CAMBIO: Añadido ondelete='restrict' ---
    clinical_record_id = fields.Many2one('medical.clinical.record', string='Ficha Clínica', ondelete='cascade')
    evaluation_id = fields.Many2one('medical.evaluation', string='Evaluación', ondelete='cascade')
    question_id = fields.Many2one('medical.template.question', string='Pregunta', required=True, ondelete='restrict')
    # --- FIN CAMIO ---

    # --- CAMPO FALTANTE ---
    # Este es el campo que tu log dice que falta. ¡Asegúrate de que esté aquí!
    question_type = fields.Selection(related='question_id.question_type', readonly=True)
    # --- FIN CAMPO FALTANTE ---

    sequence = fields.Integer(related='question_id.sequence', readonly=True, store=True)
    
    # Campos de respuesta según tipo
    boolean_answer = fields.Boolean(string='Sí/No')
    text_answer = fields.Text(string='Respuesta Texto')
    
    _sql_constraints = [
        ('answer_source_check',
         'CHECK((clinical_record_id IS NOT NULL AND evaluation_id IS NULL) OR (clinical_record_id IS NULL AND evaluation_id IS NOT NULL))',
         'Una respuesta debe pertenecer a una Ficha Clínica o a una Evaluación.'),
        ('question_unique_per_record',
         'UNIQUE(clinical_record_id, question_id)',
         'No puede haber respuestas duplicadas para la misma pregunta en una ficha clínica.'),
        ('question_unique_per_evaluation',
         'UNIQUE(evaluation_id, question_id)',
         'No puede haber respuestas duplicadas para la misma pregunta en una evaluación.'),
    ]

    @api.constrains('clinical_record_id', 'evaluation_id')
    def _check_answer_belongs_to_one(self):
        """Verificar que la respuesta pertenezca a solo un documento"""
        for record in self:
            if record.clinical_record_id or record.evaluation_id:
                if bool(record.clinical_record_id) == bool(record.evaluation_id):
                    raise ValidationError('La respuesta debe pertenecer a una Ficha Clínica o a una Evaluación, no a ambas.')