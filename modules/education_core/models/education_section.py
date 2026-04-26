from odoo import models, fields, api
from odoo.exceptions import ValidationError

class EducationSection(models.Model):
    _name = 'education.section'
    _description = 'Sección / Grupo de Clase'

    name = fields.Char(string="Nombre de Sección", required=True)
    course_id = fields.Many2one('education.course', string="Materia", required=True)
    period_id = fields.Many2one('education.academic.period', string="Periodo Académico", required=True)
    teacher_id = fields.Many2one('hr.employee', string="Docente Principal", domain=[('is_teacher', '=', True)])
    
    # ELIMINAMOS classroom_id de aquí.
    # Ahora el aforo se calcula en base a los horarios asignados.
    max_capacity = fields.Integer(compute='_compute_max_capacity', string="Aforo Permitido", store=True)
    enrolled_count = fields.Integer(compute='_compute_enrolled_count', string="Matriculados")

    enrollment_ids = fields.One2many('education.enrollment', 'section_id', string="Lista de Matrículas")
    schedule_line_ids = fields.One2many('education.schedule.line', 'section_id', string="Horarios")

    @api.depends('schedule_line_ids.classroom_id.capacity')
    def _compute_max_capacity(self):
        for record in self:
            if record.schedule_line_ids:
                # Extraemos las capacidades de todas las aulas usadas en la semana
                capacities = record.schedule_line_ids.mapped('classroom_id.capacity')
                # El límite lo dicta el aula más pequeña
                record.max_capacity = min(capacities) if capacities else 0
            else:
                record.max_capacity = 0

    @api.depends('enrollment_ids', 'enrollment_ids.state')
    def _compute_enrolled_count(self):
        for record in self:
            active_enrollments = record.enrollment_ids.filtered(lambda e: e.state == 'active')
            record.enrolled_count = len(active_enrollments)

    @api.constrains('enrollment_ids', 'max_capacity')
    def _check_capacity(self):
        for record in self:
            if record.max_capacity == 0 and record.enrolled_count > 0:
                raise ValidationError(f"No puedes matricular alumnos en la sección '{record.name}' sin antes asignarle un horario y un aula.")
            
            if record.max_capacity > 0 and record.enrolled_count > record.max_capacity:
                raise ValidationError(
                    f"La sección '{record.name}' ha superado el aforo permitido. "
                    f"Aforo Máximo: {record.max_capacity}, Intentando matricular: {record.enrolled_count}"
                )