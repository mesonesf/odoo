# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Segmentación agrícola WhatsApp / CRM (Tablas Maestras CONAGRA)
    conagra_zona_id = fields.Many2one(
        comodel_name="conagra.master.zona",
        string="Zona Agrícola (Tabla Maestra)",
        index=True,
    )
    conagra_cultivo_id = fields.Many2one(
        comodel_name="conagra.master.cultivo",
        string="Cultivo Principal (Tabla Maestra)",
        index=True,
    )
    conagra_zona = fields.Char(
        string="Texto Zona Agrícola",
        index=True,
    )
    conagra_cultivo = fields.Char(
        string="Texto Cultivo Principal",
        index=True,
    )
    conagra_is_new_customer = fields.Boolean(
        string="Es Cliente Nuevo (Bono Comisión)",
        default=True,
        help="Indica si aplica el bono de comisión por captación de cliente nuevo.",
    )
    partner_latitude = fields.Float(string="Geo Latitud", digits=(10, 7))
    partner_longitude = fields.Float(string="Geo Longitud", digits=(10, 7))

    # Punto 2: Grupo Económico / Familiar (Empresas Espejo hasta 3 RUCs vinculados)
    linked_credit_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="res_partner_conagra_credit_group_rel",
        column1="partner_id",
        column2="linked_partner_id",
        string="Empresas / Familiares Vinculados (Espejo)",
        help="Vincula las razones sociales o familiares (esposo/esposa/empresas espejo) para evaluar deuda vencida consolidada.",
    )
    group_overdue_amount = fields.Monetary(
        string="Deuda Vencida del Grupo Vinculado",
        compute="_compute_group_credit_status",
        currency_field="currency_id",
    )
    is_group_credit_blocked = fields.Boolean(
        string="Bloqueado por Morosidad de Grupo",
        compute="_compute_group_credit_status",
    )
    max_credit_term_id = fields.Many2one(
        comodel_name="conagra.master.credit.term",
        string="Plazo Máximo de Crédito Autorizado (Tabla Maestra)",
    )

    # Punto 2: Regla de Inactividad de 1 Año -> Reversión a Oficina Lima
    last_conagra_invoice_date = fields.Date(
        string="Fecha Última Factura",
        compute="_compute_last_conagra_invoice_date",
        store=True,
    )
    reverted_to_lima_office = fields.Boolean(
        string="Cartera Revertida a Oficina Lima (>1 Año Inactivo)",
        default=False,
        tracking=True,
        help="Si el cliente pasa 1 año sin facturación, pasa a Oficina Lima y no genera comisión de vendedor de zona.",
    )

    # Punto 7: Mapeo de Agencias de Transporte (Shalom, Marvisur, Móvil Bus)
    is_transport_agency = fields.Boolean(
        string="Es Agencia de Transporte (Despacho)",
        default=False,
    )
    agency_zone_id = fields.Many2one(
        comodel_name="conagra.master.agency.zone",
        string="Zona / Cercanía de Agencia (Tabla Maestra)",
    )
    preferred_nearby_agency_id = fields.Many2one(
        comodel_name="res.partner",
        string="Sucursal Alternativa Más Cercana (Ej. La Victoria)",
        domain="[('is_transport_agency', '=', True)]",
        help="Si el cliente pide una sucursal lejana (ej. Los Olivos o Lurín), sugiere esta sucursal cercana en La Victoria.",
    )

    @api.onchange("conagra_zona_id")
    def _onchange_conagra_zona_id(self):
        if self.conagra_zona_id:
            self.conagra_zona = self.conagra_zona_id.name

    @api.onchange("conagra_cultivo_id")
    def _onchange_conagra_cultivo_id(self):
        if self.conagra_cultivo_id:
            self.conagra_cultivo = self.conagra_cultivo_id.name

    @api.depends("invoice_ids.invoice_date", "invoice_ids.state", "invoice_ids.move_type")
    def _compute_last_conagra_invoice_date(self):
        for partner in self:
            invoices = partner.invoice_ids.filtered(
                lambda m: m.state == "posted" and m.move_type == "out_invoice"
            )
            partner.last_conagra_invoice_date = (
                max(invoices.mapped("invoice_date")) if invoices else False
            )

    def _compute_group_credit_status(self):
        today = fields.Date.context_today(self)
        Move = self.env["account.move"].sudo()
        for partner in self:
            all_partners = (
                partner
                | partner.commercial_partner_id
                | partner.linked_credit_partner_ids
                | partner.child_ids
            )
            overdue_moves = Move.search([
                ("partner_id", "in", all_partners.ids),
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "in", ("not_paid", "partial")),
                ("invoice_date_due", "<", today),
            ])
            overdue_total = sum(overdue_moves.mapped("amount_residual_signed"))
            partner.group_overdue_amount = max(overdue_total, 0.0)
            partner.is_group_credit_blocked = overdue_total > 0.0

    @api.model
    def _cron_revert_inactive_customers_to_lima(self):
        """Reasigna automáticamente a Oficina Lima (Karina) los clientes con más de 365 días sin compras."""
        cutoff_date = fields.Date.context_today(self) - timedelta(days=365)
        karina_user = self.env["res.users"].search(
            [("name", "ilike", "Karina"), ("share", "=", False)],
            limit=1,
        )
        inactive_partners = self.search([
            ("customer_rank", ">", 0),
            ("reverted_to_lima_office", "=", False),
            ("last_conagra_invoice_date", "!=", False),
            ("last_conagra_invoice_date", "<", cutoff_date),
        ])
        for partner in inactive_partners:
            vals = {"reverted_to_lima_office": True}
            if karina_user:
                vals["user_id"] = karina_user.id
            partner.write(vals)
            partner.message_post(
                body=(
                    "⚠️ <b>Regla de Inactividad de 1 Año (CONAGRA):</b> "
                    "El cliente supera los 365 días sin facturación. "
                    "La cuenta ha sido revertida automáticamente a <b>Oficina Lima</b>."
                ),
                subtype_xmlid="mail.mt_note",
            )


class SaleOrder(models.Model):
    _inherit = "sale.order"

    transport_agency_id = fields.Many2one(
        comodel_name="res.partner",
        string="Agencia de Transporte Solicitada",
        domain="[('is_transport_agency', '=', True)]",
    )
    agency_distance_warning = fields.Char(
        string="Alerta de Ubicación de Agencia",
        compute="_compute_agency_distance_warning",
    )
    requires_credit_approval = fields.Boolean(
        string="Requiere Aprobación de Créditos (Karina)",
        compute="_compute_credit_and_discount_alerts",
    )

    @api.depends(
        "transport_agency_id",
        "transport_agency_id.agency_zone_id",
        "transport_agency_id.agency_zone_id.is_distant_alert",
    )
    def _compute_agency_distance_warning(self):
        for order in self:
            agency = order.transport_agency_id
            if agency and agency.agency_zone_id and agency.agency_zone_id.is_distant_alert:
                alt = (
                    f" Sugerencia más cercana: {agency.preferred_nearby_agency_id.name}."
                    if agency.preferred_nearby_agency_id
                    else " Verifica si existe sucursal en La Victoria para ahorrar tiempo y combustible."
                )
                order.agency_distance_warning = (
                    f"⚠️ La agencia '{agency.name}' queda en zona alejada ({agency.agency_zone_id.name}). "
                    f"El despacho puede demorar más de 24h.{alt}"
                )
            else:
                order.agency_distance_warning = False

    @api.depends(
        "partner_id",
        "partner_id.is_group_credit_blocked",
        "order_line.discount",
        "order_line.product_id",
    )
    def _compute_credit_and_discount_alerts(self):
        for order in self:
            exceeded_discount = any(
                line.product_id.max_discount_pct > 0
                and line.discount > line.product_id.max_discount_pct
                for line in order.order_line
            )
            order.requires_credit_approval = (
                bool(order.partner_id.is_group_credit_blocked) or exceeded_discount
            )

    def action_confirm(self):
        for order in self:
            if order.partner_id.is_group_credit_blocked and not self.env.user.has_group(
                "account.group_account_manager"
            ):
                raise ValidationError(
                    f"Bloqueo Crediticio CONAGRA: El cliente '{order.partner_id.name}' o una de sus "
                    f"empresas vinculadas (espejo) presenta una deuda vencida consolidada de "
                    f"{order.partner_id.group_overdue_amount:.2f}. Solicite autorización a Créditos y Cobranzas (Karina)."
                )
            for line in order.order_line:
                max_disc = line.product_id.max_discount_pct
                if (
                    max_disc > 0.0
                    and line.discount > max_disc
                    and not self.env.user.has_group("sales_team.group_sale_manager")
                ):
                    raise ValidationError(
                        f"Tope de Descuento Excedido: El producto '{line.product_id.display_name}' "
                        f"tiene un descuento máximo permitido de {max_disc:.1f}% (solicitado: {line.discount:.1f}%)."
                    )
        res = super().action_confirm()
        for order in self:
            if order.transport_agency_id and order.picking_ids:
                order.picking_ids.filtered(lambda p: p.state != "cancel").write({
                    "transport_agency_id": order.transport_agency_id.id,
                })
        return res
