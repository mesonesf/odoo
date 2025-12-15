from odoo import models, fields

class AuditLoginLog(models.Model):
    _name = 'audit.login.log'
    _description = 'Registro de Auditoria de Login'
    _order = 'create_date desc'

    name = fields.Char(string='Referencia', default='Login Detectado')
    user_id = fields.Many2one('res.users', string='Usuario', required=True, readonly=True)
    login_datetime = fields.Datetime(string='Fecha y Hora', default=fields.Datetime.now, readonly=True)
    ip_address = fields.Char(string='Dirección IP', readonly=True)
    user_agent = fields.Char(string='User Agent / OS', readonly=True)
    
    # IMPORTANTE: Este campo debe existir aquí para que funcione tu vista
    country_code = fields.Char(string='Código País', readonly=True)