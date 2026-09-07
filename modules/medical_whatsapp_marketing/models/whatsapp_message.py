# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
import json
import logging

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    meta_phone_number_id = fields.Char(
        string='Phone Number ID (Meta)',
        config_parameter='meta.whatsapp.phone_number_id'
    )
    meta_access_token = fields.Char(
        string='Permanent Access Token (Meta)',
        config_parameter='meta.whatsapp.access_token'
    )


class MedicalWhatsappMessage(models.Model):
    _name = 'medical.whatsapp.message'
    _description = 'Mensaje de WhatsApp Marketing'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Nombre de la Campaña', required=True, tracking=True)
    partner_ids = fields.Many2many('res.partner', string='Destinatarios (Selección Manual)', required=True)
    message_body = fields.Text(string='Mensaje de Texto / Descripción', required=True)
    
    # Manejo de Multimedia
    image_attachment = fields.Binary(string='Imagen Adjunta', attachment=True)
    image_filename = fields.Char(string='Nombre de Archivo de Imagen')

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('sent', 'Enviado'),
        ('error', 'Error de Envío')
    ], string='Estado', default='draft', tracking=True)
    
    send_date = fields.Datetime(string='Fecha de Envío', readonly=True)

    def action_send_whatsapp(self):
        self.ensure_one()
        if not self.partner_ids:
            raise UserError('Debe seleccionar al menos un destinatario.')

        get_param = self.env['ir.config_parameter'].sudo().get_param
        phone_number_id = get_param('meta.whatsapp.phone_number_id')
        access_token = get_param('meta.whatsapp.access_token')

        if not phone_number_id or not access_token:
            _logger.error("WHATSAPP MARKETING ERROR: Faltan configurar las credenciales de Meta.")
            raise UserError('Faltan configurar las credenciales de WhatsApp en Ajustes WhatsApp.')
        
        api_url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        # Generar enlace público dinámico para que Meta descargue la imagen adjunta en Odoo
        base_url = get_param('web.base.url')
        image_url = f"{base_url}/web/image/medical.whatsapp.message/{self.id}/image_attachment" if self.image_attachment else False

        success_count = 0
        error_count = 0

        for partner in self.partner_ids:
            phone = partner.mobile or partner.phone
            if not phone:
                _logger.warning(f"WHATSAPP MARKETING WARNING: El contacto '{partner.name}' no tiene teléfono.")
                error_count += 1
                continue
            
            phone_clean = "".join(filter(str.isdigit, phone))

            # Estructurar payload dinámico (Imagen con pie de foto o Texto plano)
            if image_url:
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": phone_clean,
                    "type": "image",
                    "image": {
                        "link": image_url,
                        "caption": self.message_body
                    }
                }
            else:
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": phone_clean,
                    "type": "text",
                    "text": {
                        "body": self.message_body
                    }
                }

            try:
                _logger.info(f"WHATSAPP MARKETING: Enviando a {partner.name} ({phone_clean})...")
                response = requests.post(api_url, data=json.dumps(payload), headers=headers, timeout=30)
                res_data = response.json()

                if response.status_code == 200 and "messages" in res_data:
                    success_count += 1
                    _logger.info(f"WHATSAPP MARKETING SUCCESS: Mensaje entregado a {partner.name}.")
                else:
                    error_count += 1
                    _logger.error(f"WHATSAPP MARKETING META API ERROR: {json.dumps(res_data, indent=2)}")
            except Exception as e:
                error_count += 1
                _logger.error(f"WHATSAPP MARKETING EXCEPTION: {str(e)}")

        self.write({
            'state': 'sent' if success_count > 0 else 'error',
            'send_date': fields.Datetime.now()
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Campaña Procesada',
                'message': f'Enviados con éxito: {success_count}. Errores: {error_count}.',
                'type': 'success' if error_count == 0 else 'warning',
                'sticky': False,
            }
        }