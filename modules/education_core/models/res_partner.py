from odoo import models, fields, api
from datetime import date

class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_student = fields.Boolean(string="Es Alumno", default=False)
    is_parent = fields.Boolean(string="Es Apoderado", default=False)
    student_code = fields.Char(string="Código de Alumno", copy=False)
    date_of_birth = fields.Date(string="Fecha de Nacimiento")
    age = fields.Integer(string="Edad", compute="_compute_age", store=True)
    
    parent_id = fields.Many2one('res.partner', string="Apoderado", domain=[('is_parent', '=', True)])

    @api.depends('date_of_birth')
    def _compute_age(self):
        for record in self:
            if record.date_of_birth:
                today = date.today()
                record.age = today.year - record.date_of_birth.year - (
                    (today.month, today.day) < (record.date_of_birth.month, record.date_of_birth.day)
                )
            else:
                record.age = 0