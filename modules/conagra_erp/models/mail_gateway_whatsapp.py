# -*- coding: utf-8 -*-
import logging

from markupsafe import Markup

from odoo import models

_logger = logging.getLogger(__name__)


class MailGatewayWhatsapp(models.AbstractModel):
    _inherit = "mail.gateway.whatsapp"

    def _extract_incoming_whatsapp_text(self, message):
        """Extrae texto tanto de mensajes normales como de botones interactivos Quick Reply / Listas de Meta."""
        if not message:
            return ""
        if message.get("text"):
            return (message["text"].get("body") or "").strip()
        if message.get("button"):
            return (
                message["button"].get("text")
                or message["button"].get("payload")
                or ""
            ).strip()
        if message.get("interactive"):
            interactive = message["interactive"]
            if interactive.get("button_reply"):
                return (
                    interactive["button_reply"].get("title")
                    or interactive["button_reply"].get("id")
                    or ""
                ).strip()
            if interactive.get("list_reply"):
                return (
                    interactive["list_reply"].get("title")
                    or interactive["list_reply"].get("description")
                    or ""
                ).strip()
        return ""

    def _process_update(self, chat, message, value):
        """Intercepta los mensajes entrantes de WhatsApp (texto y botones) para ejecutar el IVR de 4 pasos (Bot Silverio)."""
        extracted_text = self._extract_incoming_whatsapp_text(message)
        if extracted_text and not message.get("text"):
            message = dict(message, text={"body": extracted_text})

        res = super()._process_update(chat, message, value)
        chat.ensure_one()

        if not chat.gateway_id or chat.gateway_id.gateway_type != "whatsapp":
            return res
        if chat.bot_state == "4_assigned":
            return res

        if not extracted_text and chat.bot_state != "0_new":
            self._send_bot_reply(
                chat,
                "Por favor, envíame tu respuesta en texto para poder derivarte con el ingeniero de tu zona. 🙏",
            )
            return res

        # ---------------------------------------------------------------------
        # PASO 1: Canal nuevo -> Saludar como Silverio y pedir Nombre
        # ---------------------------------------------------------------------
        if chat.bot_state == "0_new":
            chat.sudo().write({"bot_state": "1_ask_name"})
            greeting_msg = (
                "¡Hola! 👋 Te saluda *Silverio*, el asistente virtual de *CONAGRA* 🚜🌱.\n\n"
                "Para comunicarte de inmediato con el ingeniero especialista de tu zona, "
                "por favor indícame:\n"
                "👉 *¿Cuál es tu nombre y apellido?*"
            )
            self._send_bot_reply(chat, greeting_msg)

        # ---------------------------------------------------------------------
        # PASO 2: Recibe Nombre -> Guardar y preguntar Zona
        # ---------------------------------------------------------------------
        elif chat.bot_state == "1_ask_name":
            clean_name = extracted_text[:120]
            chat.sudo().write({
                "wa_temp_name": clean_name,
                "bot_state": "2_ask_zone",
            })
            zonas_examples = ", ".join(
                self.env["conagra.master.zona"].sudo().search([], limit=7).mapped("name")
            ) or "Piura, Huaura, Casma, Cañete, Ica, Huancayo, Lima"
            ask_zone_msg = (
                f"¡Mucho gusto, *{clean_name}*! 🤝\n\n"
                "📍 *¿De qué zona, valle o provincia nos escribes?*\n"
                f"_(Ejemplo: {zonas_examples})_"
            )
            self._send_bot_reply(chat, ask_zone_msg)

        # ---------------------------------------------------------------------
        # PASO 3: Recibe Zona -> Guardar y preguntar Cultivo / Producto
        # ---------------------------------------------------------------------
        elif chat.bot_state == "2_ask_zone":
            clean_zone = extracted_text[:120]
            chat.sudo().write({
                "wa_temp_zone": clean_zone,
                "bot_state": "3_ask_crop",
            })
            cultivos_examples = ", ".join(
                self.env["conagra.master.cultivo"].sudo().search([], limit=6).mapped("name")
            ) or "Palto, Mango, Cítricos, Uva, Papa, Makita"
            ask_crop_msg = (
                f"Excelente, zona *{clean_zone}* registrada. ✅\n\n"
                f"🌾 *¿Qué cultivo trabajas (ej. {cultivos_examples}) "
                "o qué nutriente foliar / herramienta Makita necesitas?*"
            )
            self._send_bot_reply(chat, ask_crop_msg)

        # ---------------------------------------------------------------------
        # PASO 4: Recibe Cultivo -> Asignar comercial, crear Lead y notificar
        # ---------------------------------------------------------------------
        elif chat.bot_state == "3_ask_crop":
            clean_crop = extracted_text[:200]
            chat.sudo().write({
                "wa_temp_crop": clean_crop,
                "bot_state": "4_assigned",
            })
            self._complete_bot_onboarding(chat, value)

        return res

    def _send_bot_reply(self, chat, plain_text):
        """Envía un mensaje de respuesta desde CONAGRA hacia WhatsApp habilitando la notificación de pasarela."""
        chat.with_context(no_gateway_notification=False).sudo().message_post(
            body=Markup(plain_text.replace("\n", "<br/>")),
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

    def _match_master_zona(self, zone_text):
        """Busca en la Tabla Maestra conagra.master.zona por nombre o palabras clave."""
        Zona = self.env["conagra.master.zona"].sudo()
        zone_clean = (zone_text or "").strip()
        if not zone_clean:
            return Zona
        matched = Zona.search([("name", "ilike", zone_clean)], limit=1)
        if matched:
            return matched
        zone_lower = zone_clean.lower()
        for rec in Zona.search([]):
            kws = [k.strip().lower() for k in (rec.keywords or "").split(",") if k.strip()]
            if rec.name.lower() in zone_lower or any(k in zone_lower for k in kws):
                return rec
        return Zona

    def _match_master_cultivo(self, crop_text):
        """Busca en la Tabla Maestra conagra.master.cultivo por nombre o sinónimos."""
        Cultivo = self.env["conagra.master.cultivo"].sudo()
        crop_clean = (crop_text or "").strip()
        if not crop_clean:
            return Cultivo
        matched = Cultivo.search([("name", "ilike", crop_clean)], limit=1)
        if matched:
            return matched
        crop_lower = crop_clean.lower()
        for rec in Cultivo.search([]):
            kws = [k.strip().lower() for k in (rec.keywords or "").split(",") if k.strip()]
            if rec.name.lower() in crop_lower or any(k in crop_lower for k in kws):
                return rec
        return Cultivo

    def _find_salesperson_by_zone(self, zone_text, master_zona=None):
        """Obtiene el comercial desde la Tabla Maestra de Zonas, Equipo de Ventas o búsqueda en res.users."""
        if master_zona and master_zona.salesperson_id:
            return master_zona.salesperson_id
        if master_zona and master_zona.team_id and master_zona.team_id.user_id:
            return master_zona.team_id.user_id

        Users = self.env["res.users"].sudo()
        Teams = self.env["crm.team"].sudo()
        zone_clean = (zone_text or "").strip()

        if zone_clean:
            zone_lower = zone_clean.lower()
            for team in Teams.search([("conagra_zone_keywords", "!=", False)]):
                keywords = [
                    k.strip().lower()
                    for k in (team.conagra_zone_keywords or "").split(",")
                    if k.strip()
                ]
                if any(k in zone_lower for k in keywords):
                    if team.user_id and not team.user_id.share:
                        return team.user_id
                    if team.member_ids:
                        return team.member_ids[0]

            user = Users.search(
                [
                    ("share", "=", False),
                    ("active", "=", True),
                    "|",
                    ("name", "ilike", zone_clean),
                    ("login", "ilike", zone_clean),
                ],
                limit=1,
            )
            if user:
                return user

        fallback_user = (
            Users.search(
                [("share", "=", False), ("active", "=", True), ("name", "ilike", "Karina")],
                limit=1,
            )
            or self.env.ref("base.user_admin", raise_if_not_found=False)
            or self.env.user
        )
        return fallback_user

    def _ensure_partner_from_channel(self, chat, value, master_zona, master_cultivo):
        """Garantiza que el contacto quede guardado en res.partner con su Nombre, Teléfono, Zona y Cultivo."""
        phone_token = str(chat.gateway_channel_token or "").lstrip("+")
        formatted_phone = f"+{phone_token}" if phone_token else False
        captured_name = chat.wa_temp_name or chat.name or formatted_phone or "Cliente WhatsApp"

        gateway_link = self.env["res.partner.gateway.channel"].sudo().search(
            [
                ("gateway_id", "=", chat.gateway_id.id),
                ("gateway_token", "=", phone_token),
            ],
            limit=1,
        )
        partner = gateway_link.partner_id if gateway_link else self.env["res.partner"]

        if not partner and formatted_phone:
            partner = self.env["res.partner"].sudo().search(
                [
                    "|",
                    ("phone_sanitized", "=", formatted_phone),
                    ("mobile", "ilike", phone_token),
                ],
                limit=1,
            )

        if not partner:
            partner = self.env["res.partner"].sudo().create({
                "name": captured_name,
                "phone": formatted_phone,
                "mobile": formatted_phone,
                "city": master_zona.name if master_zona else (chat.wa_temp_zone or False),
                "conagra_zona_id": master_zona.id if master_zona else False,
                "conagra_cultivo_id": master_cultivo.id if master_cultivo else False,
                "conagra_zona": chat.wa_temp_zone or False,
                "conagra_cultivo": chat.wa_temp_crop or False,
                "comment": (
                    f"Capturado por Bot Silverio (WhatsApp)\n"
                    f"Zona: {chat.wa_temp_zone or '-'}\n"
                    f"Cultivo/Interés: {chat.wa_temp_crop or '-'}"
                ),
            })
        else:
            update_vals = {
                "conagra_zona": chat.wa_temp_zone or partner.conagra_zona,
                "conagra_cultivo": chat.wa_temp_crop or partner.conagra_cultivo,
            }
            if master_zona:
                update_vals["conagra_zona_id"] = master_zona.id
            if master_cultivo:
                update_vals["conagra_cultivo_id"] = master_cultivo.id
            if not partner.name or partner.name.startswith("+") or partner.name.isdigit():
                update_vals["name"] = captured_name
            if not partner.city and chat.wa_temp_zone:
                update_vals["city"] = master_zona.name if master_zona else chat.wa_temp_zone
            partner.sudo().write(update_vals)

        if not gateway_link and phone_token:
            self.env["res.partner.gateway.channel"].sudo().create({
                "name": chat.gateway_id.name,
                "partner_id": partner.id,
                "gateway_id": chat.gateway_id.id,
                "gateway_token": phone_token,
            })

        channel_title = f"{captured_name} ({master_zona.name if master_zona else (chat.wa_temp_zone or 'Sin Zona')})"
        chat.sudo().write({"name": channel_title})
        return partner

    def _complete_bot_onboarding(self, chat, value):
        """Crea el Lead en CRM, asigna comercial por zona y lo suscribe al canal notificándole."""
        master_zona = self._match_master_zona(chat.wa_temp_zone)
        master_cultivo = self._match_master_cultivo(chat.wa_temp_crop)
        partner = self._ensure_partner_from_channel(chat, value, master_zona, master_cultivo)
        salesperson = self._find_salesperson_by_zone(chat.wa_temp_zone, master_zona=master_zona)

        lead_name = (
            f"[WA] {chat.wa_temp_name or partner.name} - "
            f"{master_cultivo.name if master_cultivo else (chat.wa_temp_crop or 'Consulta')} "
            f"({master_zona.name if master_zona else (chat.wa_temp_zone or 'General')})"
        )
        lead_vals = {
            "name": lead_name,
            "type": "opportunity",
            "partner_id": partner.id,
            "contact_name": chat.wa_temp_name or partner.name,
            "phone": partner.phone or partner.mobile,
            "mobile": partner.mobile or partner.phone,
            "user_id": salesperson.id,
            "team_id": master_zona.team_id.id if master_zona and master_zona.team_id else False,
            "wa_zona_id": master_zona.id if master_zona else False,
            "wa_cultivo_id": master_cultivo.id if master_cultivo else False,
            "wa_zona": chat.wa_temp_zone,
            "wa_cultivo": chat.wa_temp_crop,
            "discuss_channel_id": chat.id,
            "description": (
                f"Lead calificado automáticamente por el Bot Silverio (WhatsApp):\n"
                f"- Nombre: {chat.wa_temp_name}\n"
                f"- Zona: {chat.wa_temp_zone}\n"
                f"- Cultivo / Herramienta: {chat.wa_temp_crop}\n"
                f"- Teléfono WhatsApp: +{chat.gateway_channel_token}"
            ),
        }
        lead = self.env["crm.lead"].sudo().create(lead_vals)
        chat.sudo().write({"crm_lead_id": lead.id})

        if salesperson.partner_id:
            chat.sudo().add_members(
                partner_ids=[salesperson.partner_id.id],
                post_joined_message=False,
            )
            chat.sudo().message_subscribe(partner_ids=[salesperson.partner_id.id])
            lead.sudo().message_subscribe(partner_ids=[salesperson.partner_id.id])

        internal_note = Markup(
            '<div style="border-left: 4px solid #28a745; background-color: #f0fff4; padding: 10px;">'
            "✅ <b>Lead Calificado por Bot Silverio</b><br/>"
            "• <b>Cliente:</b> %s<br/>"
            "• <b>Zona:</b> %s<br/>"
            "• <b>Cultivo / Interés:</b> %s<br/>"
            "• <b>Comercial Asignado:</b> %s<br/>"
            "• <b>Oportunidad CRM:</b> #%s (%s)<br/>"
            "<i>⏱️ SLA activo: Dispone de 2 horas para responder antes de la reasignación automática a Lima.</i>"
            "</div>"
        ) % (
            chat.wa_temp_name or partner.name,
            master_zona.name if master_zona else (chat.wa_temp_zone or "-"),
            master_cultivo.name if master_cultivo else (chat.wa_temp_crop or "-"),
            salesperson.name,
            lead.id,
            lead.name,
        )
        chat.with_context(no_gateway_notification=True).sudo().message_post(
            body=internal_note,
            message_type="notification",
            subtype_xmlid="mail.mt_note",
            partner_ids=[salesperson.partner_id.id] if salesperson.partner_id else [],
        )

        closing_msg = (
            f"¡Muchas gracias, *{chat.wa_temp_name}*! 🌱🚜\n\n"
            f"He registrado tu consulta sobre *{chat.wa_temp_crop}* para la zona de *{chat.wa_temp_zone}*.\n"
            f"En este momento te estoy transfiriendo con nuestro especialista *{salesperson.name}*, "
            "quien te atenderá por este mismo chat en breve."
        )
        self._send_bot_reply(chat, closing_msg)
