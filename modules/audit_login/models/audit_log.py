# audit_login/models/audit_log.py
from odoo import models, fields

class AuditLoginLog(models.Model):
    _name = 'audit.login.log'
    _description = 'Registro de Auditoría de Login'
    _order = 'create_date desc'

    name = fields.Char(string='Referencia', default='Login Detectado')
    user_id = fields.Many2one('res.users', string='Usuario', required=True, readonly=True)
    login_datetime = fields.Datetime(string='Fecha y Hora', default=fields.Datetime.now, readonly=True)
    ip_address = fields.Char(string='Dirección IP', readonly=True)
    user_agent = fields.Char(string='User Agent / OS', readonly=True, help="Información del navegador y sistema operativo")
    browser_os_info = fields.Char(string='Sistema Operativo (Detalle)', compute='_compute_os_info', store=True)

    def _compute_os_info(self):
        """Intenta extraer un nombre legible del sistema operativo desde el User Agent"""
        for record in self:
            ua = record.user_agent or ""
            if "Windows" in ua:
                record.browser_os_info = "Windows"
            elif "Macintosh" in ua or "Mac OS" in ua:
                record.browser_os_info = "macOS"
            elif "Linux" in ua:
                record.browser_os_info = "Linux"
            elif "Android" in ua:
                record.browser_os_info = "Android"
            elif "iPhone" in ua or "iPad" in ua:
                record.browser_os_info = "iOS"
            else:
                record.browser_os_info = "Desconocido/Otro"