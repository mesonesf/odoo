# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    conagra_overhead_mode = fields.Selection(
        selection=[
            ("manual", "Porcentaje Manual Fijo (Colchón 35%)"),
            ("monthly", "Calculado Dinámico: Mensual (Último Mes)"),
            ("quarterly", "Calculado Dinámico: Trimestral (3 Meses)"),
            ("semiannual", "Calculado Dinámico: Semestral (6 Meses)"),
            ("annual", "Calculado Dinámico: Anual (12 Meses)"),
        ],
        string="Modo de Cálculo de Gastos Indirectos/Fijos",
        default="manual",
        required=True,
    )
    conagra_overhead_manual_pct = fields.Float(
        string="% Gastos Indirectos y Fijos (Manual)",
        default=35.0,
        help="Porcentaje base (ej. 35%) cuando se usa modo manual o no existen asientos contables en el período.",
    )
    conagra_indirect_account_prefix = fields.Char(
        string="Prefijos Cuentas Gastos Indirectos/Fijos/Admin",
        default="62,63,64,65,68,94,95",
        help="Prefijos de cuentas contables (separados por coma) donde se registran alquileres, sueldos administrativos, servicios y depreciación.",
    )
    conagra_direct_cost_account_prefix = fields.Char(
        string="Prefijos Cuentas Costo Directo (MP y Suministros)",
        default="60,69,92",
        help="Prefijos de cuentas contables (separados por coma) del costo directo de materia prima, envases y producción.",
    )
    conagra_period_indirect_expenses = fields.Monetary(
        string="Total G. Indirectos y Fijos del Período",
        compute="_compute_conagra_overhead_metrics",
        currency_field="currency_id",
    )
    conagra_period_direct_costs = fields.Monetary(
        string="Total Costos Directos del Período",
        compute="_compute_conagra_overhead_metrics",
        currency_field="currency_id",
    )
    conagra_effective_overhead_pct = fields.Float(
        string="% Efectivo Gastos Indirectos/Fijos Aplicado",
        compute="_compute_conagra_overhead_metrics",
        digits=(16, 2),
        help="Porcentaje real calculado ((G. Indirectos + G. Fijos + G. Admin) / Costo Directo * 100) o el % manual según configuración.",
    )
    conagra_monthly_breakeven_sales = fields.Monetary(
        string="Punto de Equilibrio Mensual Estimado",
        compute="_compute_conagra_overhead_metrics",
        currency_field="currency_id",
        help="Venta mensual mínima requerida para cubrir los gastos fijos/indirectos mensuales con un margen promedio del 35%.",
    )
    conagra_protected_exchange_rate = fields.Float(
        string="Tipo de Cambio Colchón Costeo (USD -> PEN)",
        default=4.12,
        digits=(12, 4),
        help="Tipo de cambio protector utilizado por CONAGRA para valorizar importaciones y matriz de costos.",
    )
    conagra_gps_api_url = fields.Char(
        string="URL API Proveedor GPS (Flota)",
        default="https://api.gpsprovider.pe/v1/vehicles/positions",
        help="Endpoint REST proporcionado por el proveedor de GPS (Pamela) para consultar ubicación y geocercas de vehículos.",
    )
    conagra_gps_api_token = fields.Char(
        string="Token API Proveedor GPS",
        help="Clave de autenticación Bearer/API Key del servicio GPS de CONAGRA.",
    )
    conagra_gps_agency_radius_meters = fields.Float(
        string="Radio Geocerca de Agencia (Metros)",
        default=250.0,
        help="Distancia máxima en metros para detectar automáticamente que una camioneta de reparto visitó una agencia (Shalom, Marvisur, Móvil Bus).",
    )

    def _get_overhead_months_window(self):
        self.ensure_one()
        mapping = {
            "monthly": 1,
            "quarterly": 3,
            "semiannual": 6,
            "annual": 12,
        }
        return mapping.get(self.conagra_overhead_mode, 1)

    @api.depends(
        "conagra_overhead_mode",
        "conagra_overhead_manual_pct",
        "conagra_indirect_account_prefix",
        "conagra_direct_cost_account_prefix",
    )
    def _compute_conagra_overhead_metrics(self):
        MoveLine = self.env["account.move.line"].sudo()
        today = fields.Date.context_today(self)
        for company in self:
            months = company._get_overhead_months_window()
            date_from = today - relativedelta(months=months)

            indirect_prefixes = [
                p.strip()
                for p in (company.conagra_indirect_account_prefix or "").split(",")
                if p.strip()
            ]
            direct_prefixes = [
                p.strip()
                for p in (company.conagra_direct_cost_account_prefix or "").split(",")
                if p.strip()
            ]

            indirect_total = 0.0
            direct_total = 0.0

            if indirect_prefixes:
                ind_domain = [
                    ("company_id", "=", company.id),
                    ("parent_state", "=", "posted"),
                    ("date", ">=", date_from),
                    ("date", "<=", today),
                ]
                prefix_domain = ["|"] * (len(indirect_prefixes) - 1)
                for pref in indirect_prefixes:
                    prefix_domain.append(("account_id.code", "=like", f"{pref}%"))
                lines = MoveLine.search(ind_domain + prefix_domain)
                indirect_total = sum(lines.mapped(lambda l: l.debit - l.credit))

            if direct_prefixes:
                dir_domain = [
                    ("company_id", "=", company.id),
                    ("parent_state", "=", "posted"),
                    ("date", ">=", date_from),
                    ("date", "<=", today),
                ]
                prefix_domain = ["|"] * (len(direct_prefixes) - 1)
                for pref in direct_prefixes:
                    prefix_domain.append(("account_id.code", "=like", f"{pref}%"))
                lines = MoveLine.search(dir_domain + prefix_domain)
                direct_total = sum(lines.mapped(lambda l: l.debit - l.credit))

            company.conagra_period_indirect_expenses = max(indirect_total, 0.0)
            company.conagra_period_direct_costs = max(direct_total, 0.0)

            if company.conagra_overhead_mode == "manual" or direct_total <= 0.0:
                effective_pct = company.conagra_overhead_manual_pct or 35.0
            else:
                effective_pct = round((max(indirect_total, 0.0) / direct_total) * 100.0, 2)

            company.conagra_effective_overhead_pct = effective_pct
            monthly_fixed = max(indirect_total, 0.0) / float(months or 1)
            # Punto de equilibrio mensual con margen de contribución objetivo (35%)
            company.conagra_monthly_breakeven_sales = (
                round(monthly_fixed / 0.35, 2) if monthly_fixed > 0 else 0.0
            )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    conagra_overhead_mode = fields.Selection(
        related="company_id.conagra_overhead_mode",
        readonly=False,
    )
    conagra_overhead_manual_pct = fields.Float(
        related="company_id.conagra_overhead_manual_pct",
        readonly=False,
    )
    conagra_indirect_account_prefix = fields.Char(
        related="company_id.conagra_indirect_account_prefix",
        readonly=False,
    )
    conagra_direct_cost_account_prefix = fields.Char(
        related="company_id.conagra_direct_cost_account_prefix",
        readonly=False,
    )
    conagra_period_indirect_expenses = fields.Monetary(
        related="company_id.conagra_period_indirect_expenses",
        readonly=True,
    )
    conagra_period_direct_costs = fields.Monetary(
        related="company_id.conagra_period_direct_costs",
        readonly=True,
    )
    conagra_effective_overhead_pct = fields.Float(
        related="company_id.conagra_effective_overhead_pct",
        readonly=True,
    )
    conagra_monthly_breakeven_sales = fields.Monetary(
        related="company_id.conagra_monthly_breakeven_sales",
        readonly=True,
    )
    conagra_protected_exchange_rate = fields.Float(
        related="company_id.conagra_protected_exchange_rate",
        readonly=False,
    )
    conagra_gps_api_url = fields.Char(
        related="company_id.conagra_gps_api_url",
        readonly=False,
    )
    conagra_gps_api_token = fields.Char(
        related="company_id.conagra_gps_api_token",
        readonly=False,
    )
    conagra_gps_agency_radius_meters = fields.Float(
        related="company_id.conagra_gps_agency_radius_meters",
        readonly=False,
    )
