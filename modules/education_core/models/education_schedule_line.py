from odoo import models, fields, api
from odoo.exceptions import ValidationError

class EducationScheduleLine(models.Model):
    _name = 'education.schedule.line'
    _description = 'Línea de Horario Semanal'

    section_id = fields.Many2one('education.section', string="Sección", required=True, ondelete='cascade')
    day_of_week = fields.Selection([
        ('0', 'Lunes'), ('1', 'Martes'), ('2', 'Miércoles'), 
        ('3', 'Jueves'), ('4', 'Viernes'), ('5', 'Sábado'), ('6', 'Domingo')
    ], string="Día de la Semana", required=True)
    
    start_time = fields.Float(string="Hora Inicio", required=True)
    end_time = fields.Float(string="Hora Fin", required=True)
    classroom_id = fields.Many2one('education.classroom', string="Aula", required=True)

    @api.constrains('day_of_week', 'start_time', 'end_time', 'classroom_id', 'section_id')
    def _check_strict_schedule_clashes(self):
        days_map = {'0': 'Lunes', '1': 'Martes', '2': 'Miércoles', '3': 'Jueves', '4': 'Viernes', '5': 'Sábado', '6': 'Domingo'}
        
        # 1. VALIDACIÓN EN MEMORIA (Cruces dentro de la misma tabla que estás editando)
        for section in self.mapped('section_id'):
            lines = section.schedule_line_ids
            for i in range(len(lines)):
                for j in range(i + 1, len(lines)):
                    l1, l2 = lines[i], lines[j]
                    # Si chocan el mismo día a la misma hora
                    if l1.day_of_week == l2.day_of_week and l1.start_time < l2.end_time and l1.end_time > l2.start_time:
                        day_name = days_map.get(l1.day_of_week, '')
                        raise ValidationError(
                            f"⛔ Error de Configuración Interna: Has asignado dos horarios que se cruzan "
                            f"el día {day_name} dentro de esta misma sección."
                        )

        # 2. VALIDACIÓN EN BASE DE DATOS (Cruces con otras secciones ya guardadas)
        for line in self:
            teacher = line.section_id.teacher_id
            period = line.section_id.period_id
            
            if not period:
                continue

            # A. Revisar cruce de AULAS
            domain_classroom = [
                ('id', 'not in', self.ids), # Excluimos las líneas actuales en memoria
                ('classroom_id', '=', line.classroom_id.id),
                ('section_id.period_id', '=', period.id),
                ('day_of_week', '=', line.day_of_week),
                ('start_time', '<', line.end_time),
                ('end_time', '>', line.start_time),
            ]
            clash_class = self.search(domain_classroom)
            if clash_class:
                day_name = days_map.get(line.day_of_week, '')
                raise ValidationError(
                    f"⛔ Cruce de Aula: El ambiente '{line.classroom_id.name}' ya está ocupado "
                    f"el {day_name} de {clash_class[0].start_time} a {clash_class[0].end_time} "
                    f"por la sección '{clash_class[0].section_id.name}'."
                )

            # B. Revisar cruce del PROFESOR
            if teacher:
                domain_teacher = [
                    ('id', 'not in', self.ids),
                    ('section_id.teacher_id', '=', teacher.id),
                    ('section_id.period_id', '=', period.id),
                    ('day_of_week', '=', line.day_of_week),
                    ('start_time', '<', line.end_time),
                    ('end_time', '>', line.start_time),
                ]
                clash_teacher = self.search(domain_teacher)
                if clash_teacher:
                    day_name = days_map.get(line.day_of_week, '')
                    raise ValidationError(
                        f"⛔ Cruce de Docente: El profesor {teacher.name} ya dicta clases "
                        f"el {day_name} de {clash_teacher[0].start_time} a {clash_teacher[0].end_time} "
                        f"en la sección '{clash_teacher[0].section_id.name}'."
                    )