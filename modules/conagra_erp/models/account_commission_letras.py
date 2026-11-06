# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    # Punto 2: Gestión de Letras de Cambio y Conciliación BCP Telecrédito (Tabla Maestra)
    is_letra_cambio = fields.Boolean(
        string="Es Letra de Cambio",
        default=False,
        tracking=True,
    )
    letra_unique_number = fields.Char(
        string="Número Único de Letra (Banco)",
        tracking=True,
        help="Código único asignado por el banco (ej. BCP Telecrédito que inicia con 192/193/194).",
    )
    letra_status_id = fields.Many2one(
        comodel_name="conagra.master.letra.status",
        string="Estado de la Letra (Tabla Maestra)",
        tracking=True,
    )
    canje_source_invoice_ids = fields.Many2many(
        comodel_name="account.move",
        relation="account_move_conagra_letra_canje_rel",
        column1="letra_move_id",
        column2="invoice_move_id",
        string="Facturas Canjeadas por esta Letra",
    )

    # Punto 3: Resumen de Comisiones CONAGRA (Corte día 24 de cada mes)
    commission_cutoff_period = fields.Char(
        string="Período Corte Comisión (Día 24)",
        compute="_compute_conagra_commission_summary",
        store=True,
        help="Período de liquidación de comisiones (del 25 del mes anterior al 24 del mes actual).",
    )
    payment_delay_days = fields.Integer(
        string="Días de Mora al Cobro (ATD)",
        compute="_compute_conagra_commission_summary",
        store=True,
    )
    total_commission_base_pen = fields.Monetary(
        string="Base Comisionable Neta (Sin IGV)",
        compute="_compute_conagra_commission_summary",
        store=True,
        currency_field="currency_id",
    )
    total_commission_amount_pen = fields.Monetary(
        string="Comisión Total Vendedor (7 Reglas)",
        compute="_compute_conagra_commission_summary",
        store=True,
        currency_field="currency_id",
    )
    commission_settled = fields.Boolean(
        string="Comisión Liquidada (Pago día 7)",
        default=False,
        tracking=True,
    )

    @api.depends(
        "invoice_date",
        "invoice_date_due",
        "payment_state",
        "invoice_line_ids.conagra_commission_amount",
        "invoice_line_ids.conagra_commission_base",
    )
    def _compute_conagra_commission_summary(self):
        for move in self:
            if move.move_type not in ("out_invoice", "out_refund") or not move.invoice_date:
                move.commission_cutoff_period = False
                move.payment_delay_days = 0
                move.total_commission_base_pen = 0.0
                move.total_commission_amount_pen = 0.0
                continue

            inv_date = move.invoice_date
            if inv_date.day >= 25:
                year = inv_date.year + (1 if inv_date.month == 12 else 0)
                month = 1 if inv_date.month == 12 else inv_date.month + 1
            else:
                year = inv_date.year
                month = inv_date.month
            move.commission_cutoff_period = f"{year}-{month:02d} (Corte 24)"

            delay = 0
            if move.invoice_date_due:
                ref_date = fields.Date.context_today(move)
                delay = max((ref_date - move.invoice_date_due).days, 0)
            move.payment_delay_days = delay

            sign = -1.0 if move.move_type == "out_refund" else 1.0
            move.total_commission_base_pen = sign * sum(
                move.invoice_line_ids.mapped("conagra_commission_base")
            )
            move.total_commission_amount_pen = sign * sum(
                move.invoice_line_ids.mapped("conagra_commission_amount")
            )


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    is_igv_exonerated = fields.Boolean(
        string="Exonerado de IGV (Ley Peruana 40%)",
        compute="_compute_conagra_line_commission",
        store=True,
    )
    conagra_commission_base = fields.Monetary(
        string="Base Comisionable (Sin IGV)",
        compute="_compute_conagra_line_commission",
        store=True,
        currency_field="currency_id",
        help="En productos afectos a IGV se descuenta el 18% (price_subtotal); en productos exonerados toma el 100%.",
    )
    conagra_commission_rate_pct = fields.Float(
        string="% Comisión Aplicado (7 Reglas)",
        compute="_compute_conagra_line_commission",
        store=True,
        digits=(16, 2),
    )
    conagra_commission_amount = fields.Monetary(
        string="Monto Comisión Línea",
        compute="_compute_conagra_line_commission",
        store=True,
        currency_field="currency_id",
    )

    @api.depends(
        "price_subtotal",
        "price_total",
        "discount",
        "tax_ids",
        "product_id",
        "move_id.payment_state",
        "move_id.partner_id.reverted_to_lima_office",
        "move_id.partner_id.conagra_is_new_customer",
        "move_id.payment_delay_days",
    )
    def _compute_conagra_line_commission(self):
        Rule = self.env["conagra.master.commission.rule"].sudo()
        discount_rules = Rule.search(
            [("rule_type", "=", "discount_tier")], order="threshold_value desc"
        )
        delay_rules = Rule.search(
            [("rule_type", "=", "delay_tier")], order="threshold_value desc"
        )
        new_cust_rule = Rule.search(
            [("rule_type", "=", "new_customer_bonus")], limit=1
        )

        for line in self:
            if line.display_type != "product" or line.move_id.move_type not in (
                "out_invoice",
                "out_refund",
            ):
                line.is_igv_exonerated = False
                line.conagra_commission_base = 0.0
                line.conagra_commission_rate_pct = 0.0
                line.conagra_commission_amount = 0.0
                continue

            has_igv_18 = any(t.amount >= 18.0 for t in line.tax_ids)
            line.is_igv_exonerated = not has_igv_18
            if has_igv_18 and line.price_subtotal == line.price_total and line.price_total > 0:
                base_amount = line.price_total / 1.18
            else:
                base_amount = line.price_subtotal
            line.conagra_commission_base = base_amount

            partner = line.move_id.partner_id
            if partner.reverted_to_lima_office:
                line.conagra_commission_rate_pct = 0.0
                line.conagra_commission_amount = 0.0
                continue

            base_rate = line.product_id.base_commission_pct or 3.0

            # Aplicar tramos de descuento desde Tabla Maestra (o fallback estándar)
            if discount_rules:
                for d_rule in discount_rules:
                    if line.discount > d_rule.threshold_value:
                        base_rate *= d_rule.multiplier_or_bonus
                        break
            else:
                if line.discount > 15.0:
                    base_rate *= 0.5
                elif line.discount > 5.0:
                    base_rate *= 0.75

            # Bono cliente nuevo desde Tabla Maestra
            if partner.conagra_is_new_customer:
                base_rate += new_cust_rule.multiplier_or_bonus if new_cust_rule else 1.0

            # Aplicar castigo por días de mora (ATD) desde Tabla Maestra
            delay_days = line.move_id.payment_delay_days or 0
            if delay_rules:
                for m_rule in delay_rules:
                    if delay_days > m_rule.threshold_value:
                        base_rate *= m_rule.multiplier_or_bonus
                        break
            else:
                if delay_days > 60:
                    base_rate = 0.0
                elif delay_days > 15:
                    base_rate *= 0.7

            line.conagra_commission_rate_pct = round(base_rate, 2)
            line.conagra_commission_amount = round(
                base_amount * (line.conagra_commission_rate_pct / 100.0), 2
            )
