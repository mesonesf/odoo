from odoo import models, api
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'

    def _update_last_login(self):
        """
        Auditoría de Login para Odoo 18 (Compatible con VPS/Proxy y GeoIP).
        """
        # 1. INTENTAR GUARDAR AUDITORÍA (Blindado ante fallos)
        try:
            if request:
                # Usamos self.id porque es 100% seguro en este punto
                user_id = self.id 
                
                # A. Detección de IP (Soporte para Nginx/Proxy)
                forwarded_for = request.httprequest.headers.get('X-Forwarded-For')
                if forwarded_for:
                    ip = forwarded_for.split(',')[0]
                else:
                    ip = request.httprequest.remote_addr

                # B. Datos del Navegador
                user_agent = request.httprequest.user_agent.string or "Desconocido"

                # C. Detección de País (si GeoIP está instalado)
                country = request.session.get('geoip', {}).get('country_code') or 'N/A'

                # D. Guardado con Cursor Independiente (Commit Inmediato)
                with self.pool.cursor() as cr:
                    env = api.Environment(cr, self.env.uid, self.env.context)
                    if 'audit.login.log' in env:
                        env['audit.login.log'].sudo().create({
                            'user_id': user_id,
                            'ip_address': ip,
                            'user_agent': user_agent,
                            'country_code': country,
                        })

        except Exception as e:
            # En caso de error, solo lo registramos en el log sin bloquear al usuario
            _logger.error(f"AUDIT ERROR: No se pudo registrar el login: {str(e)}")

        # 2. EJECUTAR LÓGICA ORIGINAL DE ODOO
        super(ResUsers, self)._update_last_login()