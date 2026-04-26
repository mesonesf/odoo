from odoo import models, fields, api
from odoo.exceptions import ValidationError

class EducationEnrollment(models.Model):
    _name = 'education.enrollment'
    _description = 'Matrícula de Alumno en Sección'

    student_id = fields.Many2one('res.partner', string="Alumno", required=True, domain=[('is_student', '=', True)])
    section_id = fields.Many2one('education.section', string="Sección", required=True)
    enrollment_date = fields.Date(string="Fecha de Matrícula", default=fields.Date.context_today)
    state = fields.Selection([
        ('draft', 'Borrador'), ('active', 'Activo'), 
        ('withdrawn', 'Retirado'), ('finished', 'Finalizado')
    ], string="Estado", default='draft', required=True)

    _sql_constraints = [
        ('unique_student_section', 'unique(student_id, section_id)', 'El alumno ya está matriculado en esta sección.')
    ]

    @api.constrains('student_id', 'section_id', 'state')
    def _check_student_schedule_clash(self):
        days_map = {'0': 'Lunes', '1': 'Martes', '2': 'Miércoles', '3': 'Jueves', '4': 'Viernes', '5': 'Sábado', '6': 'Domingo'}
        
        for enrollment in self:
            # Solo validamos si la matrícula está en proceso o activa
            if enrollment.state not in ['draft', 'active']:
                continue
            
            new_schedules = enrollment.section_id.schedule_line_ids
            if not new_schedules:
                continue

            # Buscar otras matrículas del mismo alumno en el mismo periodo
            other_enrollments = self.search([
                ('id', '!=', enrollment.id),
                ('student_id', '=', enrollment.student_id.id),
                ('section_id.period_id', '=', enrollment.section_id.period_id.id),
                ('state', 'in', ['draft', 'active'])
            ])

            # Cruzar los horarios
            for other in other_enrollments:
                for exist_line in other.section_id.schedule_line_ids:
                    for new_line in new_schedules:
                        # Condición de cruce
                        if (exist_line.day_of_week == new_line.day_of_week and 
                            exist_line.start_time < new_line.end_time and 
                            exist_line.end_time > new_line.start_time):
                            
                            day_name = days_map.get(new_line.day_of_week, '')
                            raise ValidationError(
                                f"⛔ Cruce de horario para el alumno {enrollment.student_id.name}.\n"
                                f"La nueva sección '{enrollment.section_id.name}' se cruza con "
                                f"su curso actual '{other.section_id.name}' el día {day_name}."
                            )