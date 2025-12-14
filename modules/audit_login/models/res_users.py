# audit_login/models/res_users.py
from odoo import models, api
from odoo.http import request

class ResUsers(models.Model):
    _inherit = 'res.users'

    @classmethod
    def _update_last_login(cls):
        """
        Sobrescribe el método que actualiza el último login para registrar
        la auditoría.
        """
        # Ejecuta la lógica original de Odoo primero
        super(ResUsers, cls)._update_last_login()
        
        # Obtenemos el usuario actual (uid ya está en el entorno tras el login)
        # Nota: Usamos request para obtener IP y Headers
        if request:
            user_id = request.session.uid
            if user_id:
                ip = request.httprequest.remote_addr
                # Si estás detrás de un proxy (Nginx), a veces se necesita:
                # ip = request.httprequest.headers.get('X-Forwarded-For', request.httprequest.remote_addr)
                
                user_agent = request.httprequest.user_agent.string
                
                # Creamos el registro en modo sudo() para evitar problemas de permisos
                request.env['audit.login.log'].sudo().create({
                    'user_id': user_id,
                    'ip_address': ip,
                    'user_agent': user_agent,
                })