# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import markupsafe
import logging

_logger = logging.getLogger(__name__)

class MedicalWhatsappCampaign(models.Model):
    _name = 'medical.whatsapp.campaign'
    _description = 'Campaña de Marketing WhatsApp'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nombre de la Campaña', required=True, tracking=True)
    gateway_id = fields.Many2one(
        'mail.gateway', 
        string='Pasarela WhatsApp', 
        domain=[('gateway_type', '=', 'whatsapp')], 
        required=True,
        tracking=True
    )
    
    template_id = fields.Many2one(
        'mail.whatsapp.template', 
        string='Plantilla de WhatsApp',
        required=True,
        help="Selecciona la plantilla oficial sincronizada desde Meta."
    )
    
    partner_ids = fields.Many2many('res.partner', string='Destinatarios (Pacientes)', required=True)
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('sent', 'Enviado'),
        ('error', 'Error')
    ], string='Estado', default='draft', tracking=True)
    
    send_date = fields.Datetime(string='Fecha de Envío', readonly=True)

    def action_send_campaign(self):
        self.ensure_one()
        if not self.partner_ids:
            raise UserError('Debe seleccionar al menos un destinatario.')
        if not self.gateway_id:
            raise UserError('Debe seleccionar una pasarela de WhatsApp configurada.')
        if not self.template_id:
            raise UserError('Debe seleccionar una Plantilla de WhatsApp aprobada.')

        success_count = 0
        error_count = 0

        for partner in self.partner_ids:
            phone_field = 'mobile' if partner.mobile else ('phone' if partner.phone else False)
            if not phone_field:
                _logger.error("El paciente %s no tiene número de teléfono registrado.", partner.name)
                error_count += 1
                continue
            
            try:
                channel = partner._whatsapp_get_channel(phone_field, self.gateway_id)
                if not channel:
                    _logger.error("No se pudo obtener el canal de WhatsApp para el paciente: %s", partner.name)
                    error_count += 1
                    continue

                # Renderizar texto de la plantilla inyectando el paciente para resolución de variables
                template_ctx = self.template_id.with_context(default_res_id=partner.id)
                body_text = template_ctx.render_body_message()
                body_content = markupsafe.Markup(body_text) if body_text else markupsafe.Markup('')
                
                kwargs = {
                    'body': body_content,
                    'subtype_xmlid': "mail.mt_comment",
                    'message_type': "comment",
                }
                
                # Pasar contexto crítico a la pasarela para estructura JSON de Meta
                channel = channel.with_context(
                    whatsapp_template_id=self.template_id.id,
                    default_res_id=partner.id
                )
                
                channel.message_post(**kwargs)
                success_count += 1
                
            except Exception as e:
                _logger.error("Fallo crítico al enviar WhatsApp a %s: %s", partner.name, str(e), exc_info=True)
                error_count += 1

        self.write({
            'state': 'sent' if success_count > 0 else 'error',
            'send_date': fields.Datetime.now()
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Campaña Procesada',
                'message': f'Mensajes encolados con éxito: {success_count}. Errores: {error_count}.',
                'type': 'success' if error_count == 0 else 'warning',
                'sticky': False,
            }
        }