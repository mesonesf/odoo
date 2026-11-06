# -*- coding: utf-8 -*-
import logging

from markupsafe import Markup

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    bot_state = fields.Selection(
        selection=[
            ("0_new", "0 - Nuevo"),
            ("1_ask_name", "1 - Esperando Nombre"),
            ("2_ask_zone", "2 - Esperando Zona"),
            ("3_ask_crop", "3 - Esperando Cultivo / Interés"),
            ("4_assigned", "4 - Asignado a Comercial"),
        ],
        string="Estado del Bot (Silverio)",
        default="0_new",
        required=True,
        index=True,
        help="Controla la máquina de estados del bot conversacional Silverio en WhatsApp.",
    )
    wa_temp_name = fields.Char(
        string="Nombre Capturado (WA)",
        help="Respuesta temporal del cliente en el paso 1 (Nombre).",
    )
    wa_temp_zone = fields.Char(
        string="Zona Capturada (WA)",
        help="Respuesta temporal del cliente en el paso 2 (Zona geográfica).",
    )
    wa_temp_crop = fields.Char(
        string="Cultivo/Interés Capturado (WA)",
        help="Respuesta temporal del cliente en el paso 3 (Cultivo o herramienta Makita).",
    )
    crm_lead_id = fields.Many2one(
        comodel_name="crm.lead",
        string="Lead / Oportunidad CRM",
        ondelete="set null",
        index=True,
        help="Oportunidad en el CRM generada automáticamente al completar el flujo del bot.",
    )
    assigned_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Ingeniero / Comercial Asignado",
        related="crm_lead_id.user_id",
        store=True,
        readonly=False,
    )
    wa_last_customer_msg_dt = fields.Datetime(
        string="Último Mensaje del Cliente",
        compute="_compute_wa_sla_metrics",
    )
    wa_waiting_minutes = fields.Integer(
        string="Minutos sin Respuesta",
        compute="_compute_wa_sla_metrics",
    )
    wa_sla_semaphore = fields.Selection(
        selection=[
            ("green", "En Tiempo (< 60 min)"),
            ("yellow", "Por Vencer (60 - 120 min)"),
            ("red", "SLA Vencido (> 2 Horas - Rebotado a Lima)"),
        ],
        string="Semáforo Central Telefónica",
        compute="_compute_wa_sla_metrics",
    )

    def _compute_wa_sla_metrics(self):
        now = fields.Datetime.now()
        comment_subtype = self.env.ref("mail.mt_comment", raise_if_not_found=False)
        for channel in self:
            domain = [
                ("model", "=", "discuss.channel"),
                ("res_id", "=", channel.id),
                ("message_type", "=", "comment"),
            ]
            if comment_subtype:
                domain.append(("subtype_id", "=", comment_subtype.id))
            last_msg = self.env["mail.message"].search(
                domain, order="date desc, id desc", limit=1
            )
            if not last_msg or not last_msg.date:
                channel.wa_last_customer_msg_dt = False
                channel.wa_waiting_minutes = 0
                channel.wa_sla_semaphore = "green"
                continue

            internal_users = last_msg.author_id.user_ids.filtered(lambda u: not u.share)
            if internal_users:
                channel.wa_last_customer_msg_dt = False
                channel.wa_waiting_minutes = 0
                channel.wa_sla_semaphore = "green"
            else:
                channel.wa_last_customer_msg_dt = last_msg.date
                minutes = int((now - last_msg.date).total_seconds() // 60)
                channel.wa_waiting_minutes = max(minutes, 0)
                if minutes > 120:
                    channel.wa_sla_semaphore = "red"
                elif minutes >= 60:
                    channel.wa_sla_semaphore = "yellow"
                else:
                    channel.wa_sla_semaphore = "green"

    @api.model
    def _cron_check_whatsapp_sla(self):
        """Verifica el SLA de 2 horas (7200s) en canales asignados y reasigna a Karina (Lima)."""
        now = fields.Datetime.now()
        assigned_channels = self.search([
            ("bot_state", "=", "4_assigned"),
            ("channel_type", "=", "gateway"),
        ])
        if not assigned_channels:
            return

        karina_user = (
            self.env["res.users"].search(
                [("name", "ilike", "Karina"), ("share", "=", False)],
                limit=1,
            )
            or self.env.ref("base.user_admin", raise_if_not_found=False)
            or self.env.user
        )
        comment_subtype = self.env.ref("mail.mt_comment", raise_if_not_found=False)

        for channel in assigned_channels:
            domain = [
                ("model", "=", "discuss.channel"),
                ("res_id", "=", channel.id),
                ("message_type", "=", "comment"),
            ]
            if comment_subtype:
                domain.append(("subtype_id", "=", comment_subtype.id))

            last_msg = self.env["mail.message"].search(
                domain, order="date desc, id desc", limit=1
            )
            if not last_msg or not last_msg.date:
                continue

            author_users = last_msg.author_id.user_ids.filtered(lambda u: not u.share)
            if author_users:
                continue

            elapsed_seconds = (now - last_msg.date).total_seconds()
            if elapsed_seconds <= 7200:
                continue

            lead = channel.crm_lead_id
            previous_user_name = (
                lead.user_id.name if lead and lead.user_id else "Sin comercial"
            )
            if lead:
                lead.sudo().write({"user_id": karina_user.id})
                if karina_user.partner_id:
                    lead.sudo().message_subscribe(partner_ids=[karina_user.partner_id.id])

            if karina_user.partner_id:
                channel.sudo().add_members(
                    partner_ids=[karina_user.partner_id.id],
                    post_joined_message=False,
                )
                channel.sudo().message_subscribe(partner_ids=[karina_user.partner_id.id])

            hours_waited = round(elapsed_seconds / 3600.0, 1)
            alert_html = Markup(
                '<div style="border-left: 4px solid #d9534f; background-color: #fdf2f2; '
                'padding: 10px; color: #a94442; font-weight: bold;">'
                "🚨 ALERTA ROJA SLA WHATSAPP (CONAGRA)<br/>"
                "El cliente lleva <b>%s horas</b> (%s seg) esperando respuesta sin atención "
                "del comercial asignado (%s).<br/>"
                "Se ha reasignado automáticamente el Canal y el Lead a <b>%s (Oficina Lima)</b>."
                "</div>"
            ) % (
                hours_waited,
                int(elapsed_seconds),
                previous_user_name,
                karina_user.name,
            )

            channel.with_context(no_gateway_notification=True).sudo().message_post(
                body=alert_html,
                message_type="notification",
                subtype_xmlid="mail.mt_note",
            )
            if lead:
                lead.sudo().message_post(
                    body=alert_html,
                    message_type="notification",
                    subtype_xmlid="mail.mt_note",
                )
