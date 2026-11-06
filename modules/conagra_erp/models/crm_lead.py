# -*- coding: utf-8 -*-
import markupsafe

from odoo import api, fields, models
from odoo.exceptions import UserError


class CrmTeam(models.Model):
    _inherit = "crm.team"

    conagra_zone_keywords = fields.Char(
        string="Palabras Clave de Zona (Bot Silverio)",
        help="Lista de provincias/valles separados por coma que atiende este equipo comercial (ej. Piura, Sullana, Tambo Grande).",
    )


class CrmLead(models.Model):
    _inherit = "crm.lead"

    wa_zona_id = fields.Many2one(
        comodel_name="conagra.master.zona",
        string="Zona Agrícola (Tabla Maestra)",
        tracking=True,
        help="Zona agrícola parametrizable en Tablas Maestras CONAGRA.",
    )
    wa_cultivo_id = fields.Many2one(
        comodel_name="conagra.master.cultivo",
        string="Cultivo / Interés (Tabla Maestra)",
        tracking=True,
        help="Cultivo o línea de interés parametrizable en Tablas Maestras CONAGRA.",
    )
    wa_zona = fields.Char(
        string="Texto Zona Capturado (Bot WA)",
        tracking=True,
        help="Respuesta textual de zona declarada por el cliente en el Bot Silverio.",
    )
    wa_cultivo = fields.Char(
        string="Texto Cultivo / Interés (Bot WA)",
        tracking=True,
        help="Respuesta textual de cultivo o herramienta Makita solicitada en WhatsApp.",
    )
    wa_codigo_herramienta = fields.Char(
        string="Código Herramienta / Producto (Variable 3 Meta)",
        tracking=True,
        help="Tercera variable utilizada en las plantillas masivas de WhatsApp de CONAGRA (Makita / Foliares).",
    )
    discuss_channel_id = fields.Many2one(
        comodel_name="discuss.channel",
        string="Canal de WhatsApp",
        ondelete="set null",
        index=True,
        help="Canal de conversación de WhatsApp que originó esta oportunidad.",
    )
    ficha_product_id = fields.Many2one(
        comodel_name="product.template",
        string="Producto para Enviar Ficha Técnica",
        help="Selecciona un nutriente foliar o herramienta Makita para enviar su Ficha Técnica PDF por WhatsApp.",
    )

    @api.onchange("wa_zona_id")
    def _onchange_wa_zona_id(self):
        if self.wa_zona_id:
            self.wa_zona = self.wa_zona_id.name
            if self.wa_zona_id.salesperson_id:
                self.user_id = self.wa_zona_id.salesperson_id
            if self.wa_zona_id.team_id:
                self.team_id = self.wa_zona_id.team_id

    @api.onchange("wa_cultivo_id")
    def _onchange_wa_cultivo_id(self):
        if self.wa_cultivo_id:
            self.wa_cultivo = self.wa_cultivo_id.name

    def action_open_whatsapp_channel(self):
        """Abre directamente el canal de WhatsApp vinculado desde el Lead."""
        self.ensure_one()
        if not self.discuss_channel_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": "Canal de WhatsApp",
            "res_model": "discuss.channel",
            "res_id": self.discuss_channel_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_send_ficha_tecnica_whatsapp(self):
        """Envía la Ficha Técnica PDF del producto seleccionado directamente al canal de WhatsApp del Lead."""
        self.ensure_one()
        if not self.discuss_channel_id:
            raise UserError("Este Lead no tiene un canal de WhatsApp vinculado.")
        if not self.ficha_product_id or not self.ficha_product_id.ficha_tecnica_pdf:
            raise UserError(
                "Seleccione un producto que tenga cargada su Ficha Técnica en PDF."
            )

        attachment = self.env["ir.attachment"].create({
            "name": self.ficha_product_id.ficha_tecnica_filename
            or f"Ficha_Tecnica_{self.ficha_product_id.name}.pdf",
            "type": "binary",
            "datas": self.ficha_product_id.ficha_tecnica_pdf,
            "res_model": "discuss.channel",
            "res_id": self.discuss_channel_id.id,
            "mimetype": "application/pdf",
        })
        body_msg = markupsafe.Markup(
            f"📄 Te compartimos la *Ficha Técnica* de *{self.ficha_product_id.name}*."
        )
        self.discuss_channel_id.with_context(no_gateway_notification=False).message_post(
            body=body_msg,
            attachment_ids=[attachment.id],
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        return True

    def action_send_mass_whatsapp_template(self):
        """Envía campaña de plantilla de 4 variables (Teléfono, Nombre, Herramienta/Producto, Zona) desde selección de Leads."""
        gateway = self.env["mail.gateway"].search(
            [("gateway_type", "=", "whatsapp"), ("integrated_webhook_state", "=", "integrated")],
            limit=1,
        )
        if not gateway:
            raise UserError("No se encontró una pasarela de WhatsApp activa e integrada.")

        template = self.env["mail.whatsapp.template"].search(
            [("gateway_id", "=", gateway.id), ("state", "=", "approved")],
            limit=1,
        )
        sent_count = 0
        for lead in self:
            partner = lead.partner_id
            if not partner:
                continue
            phone_field = "mobile" if partner.mobile else ("phone" if partner.phone else False)
            if not phone_field:
                continue
            channel = partner._whatsapp_get_channel(phone_field, gateway)
            if not channel:
                continue
            if not lead.discuss_channel_id:
                lead.discuss_channel_id = channel.id
                channel.crm_lead_id = lead.id

            if template:
                body_text = template.with_context(default_res_id=partner.id).render_body_message()
                channel.with_context(
                    no_gateway_notification=False,
                    whatsapp_template_id=template.id,
                    default_res_id=partner.id,
                ).message_post(
                    body=markupsafe.Markup(body_text or ""),
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )
            else:
                zona_label = lead.wa_zona_id.name or lead.wa_zona or partner.city or ""
                cultivo_label = (
                    lead.wa_codigo_herramienta
                    or lead.wa_cultivo_id.name
                    or lead.wa_cultivo
                    or "nuestros productos"
                )
                fallback_body = markupsafe.Markup(
                    f"Hola *{lead.contact_name or partner.name}*, te saludamos de *CONAGRA* "
                    f"respecto a *{cultivo_label}* en tu zona *{zona_label}*."
                )
                channel.with_context(no_gateway_notification=False).message_post(
                    body=fallback_body,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )
            sent_count += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Campaña WhatsApp CONAGRA",
                "message": f"Se enviaron {sent_count} mensajes por WhatsApp exitosamente.",
                "type": "success",
            },
        }
