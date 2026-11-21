# -*- coding: utf-8 -*-
import re
import unicodedata
from datetime import timedelta

from odoo import api, fields, models

_GENERIC_ROOT_NAMES = {"all", "todos", "saleable", "vendible", "expenses", "gastos", "pos"}
_STOP_WORDS = {
    "de", "del", "la", "las", "el", "los", "y", "e", "o", "u",
    "en", "para", "por", "con", "sin", "sola",
}


def _normalize_text_ascii(text):
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


class ProductCategory(models.Model):
    _inherit = "product.category"

    conagra_code_prefix = fields.Char(
        string="Prefijo de Código CONAGRA (Ej. JD, FFL, ACC)",
        help="Abreviatura para autogenerar el código interno de productos pertenecientes a esta categoría.",
    )

    @staticmethod
    def _extract_significant_words(text):
        clean = _normalize_text_ascii(text or "").lower()
        words = re.findall(r"[a-z0-9]+", clean)
        sig = [w for w in words if w not in _STOP_WORDS]
        return sig or words

    def _get_auto_hierarchy_prefix(self):
        """Genera un prefijo automático desde la ruta jerárquica ignorando raíces genéricas."""
        self.ensure_one()
        chain = []
        curr = self
        visited = set()
        while curr:
            key = curr._origin.id or id(curr)
            if key in visited:
                break
            visited.add(key)
            name_clean = _normalize_text_ascii(curr.name or "").strip().lower()
            if name_clean and name_clean not in _GENERIC_ROOT_NAMES:
                chain.append(curr)
            curr = curr.parent_id
        chain.reverse()

        if not chain:
            return False

        if len(chain) == 1:
            words = self._extract_significant_words(chain[0].name)
            if not words:
                return False
            if len(words) == 1:
                return words[0][:3].upper()
            return "".join(w[0] for w in words[:4]).upper()

        parts = []
        for idx, node in enumerate(chain):
            words = self._extract_significant_words(node.name)
            if not words:
                continue
            if idx < len(chain) - 1:
                parts.append(words[0][0])
            elif len(chain) == 2 and len(words) >= 2:
                parts.append("".join(w[0] for w in words[:2]))
            elif len(chain) == 2 and len(words) == 1:
                parts.append(words[0][:2])
            else:
                parts.append(words[0][0])

        prefix = "".join(parts).upper()
        return prefix[:6] if prefix else False

    @api.onchange("name", "parent_id")
    def _onchange_hierarchy_conagra_prefix(self):
        for cat in self:
            if not cat.name:
                continue
            is_new = not cat._origin or not cat._origin.id
            parent_changed = bool(cat._origin and cat.parent_id != cat._origin.parent_id)
            if is_new or parent_changed or not cat.conagra_code_prefix:
                auto_prefix = cat._get_auto_hierarchy_prefix()
                if auto_prefix:
                    cat.conagra_code_prefix = auto_prefix

    @api.model_create_multi
    def create(self, vals_list):
        categories = super().create(vals_list)
        for cat in categories:
            if not cat.conagra_code_prefix:
                auto_prefix = cat._get_auto_hierarchy_prefix()
                if auto_prefix:
                    cat.conagra_code_prefix = auto_prefix
        return categories


class ProductTemplate(models.Model):
    _inherit = "product.template"

    list_price = fields.Float(string="Valor de Venta")
    conagra_extra_description = fields.Text(
        string="Descripción Adicional",
        help="Descripción comercial o técnica extendida para mostrar opcionalmente en cotizaciones.",
    )
    conagra_extra_detail = fields.Text(
        string="Detalle Adicional",
        help="Dosis de aplicación, ficha rápida o especificaciones técnicas para mostrar opcionalmente en cotizaciones.",
    )

    # Doble código: Código Interno CONAGRA (autogenerado con prefijo) y Código de Proveedor (Makita)
    conagra_internal_code = fields.Char(
        string="Código Interno CONAGRA",
        index=True,
        copy=False,
        help="Código autogenerado a partir de la abreviatura de la categoría (ej. FFL-0012) o asignado manualmente.",
    )
    supplier_product_code = fields.Char(
        string="Código del Proveedor (Ej. Makita 632... / BL1860B)",
        index=True,
        help="Código oficial asignado por el fabricante o proveedor extranjero.",
    )

    # Punto 1, 5 y 6: Clasificación y Presentaciones parametrizables desde Tablas Maestras CONAGRA
    ficha_tecnica_pdf = fields.Binary(
        string="Ficha Técnica PDF (WhatsApp)",
        attachment=True,
    )
    ficha_tecnica_filename = fields.Char(string="Nombre Archivo Ficha Técnica")
    conagra_business_line_id = fields.Many2one(
        comodel_name="conagra.master.business.line",
        string="Línea de Negocio CONAGRA (Tabla Maestra)",
    )
    presentation_id = fields.Many2one(
        comodel_name="conagra.master.presentation",
        string="Tipo de Presentación (Tabla Maestra)",
    )
    is_makita_combo = fields.Boolean(
        string="Es Combo Promocional Makita",
        default=False,
        help="Indica si este producto es un paquete promocional Makita (ej. Hoyadora + Batería + Cargador).",
    )
    is_bonus_free_item = fields.Boolean(
        string="Es Producto Bonificado Costo Cero (Ej. Batería Regalo)",
        default=False,
        help="Productos entregados por el proveedor sin costo para promociones o venta directa.",
    )
    max_discount_pct = fields.Float(
        string="Tope Máximo de Descuento (%)",
        default=10.0,
        help="Descuento máximo que un vendedor puede aplicar sin requerir aprobación de gerencia/créditos.",
    )
    base_commission_pct = fields.Float(
        string="% Comisión Base del Producto",
        default=3.0,
        help="Porcentaje base de comisión según rentabilidad del producto (antes de reglas de descuento y ATD).",
    )

    # Punto 5: Matriz de Costeo CONAGRA (01.LOG_COSTEO_GRAL_PRODUCTOS_SOLES.xlsx)
    pack_units_factor = fields.Integer(
        string="Factor de Unidades por Caja/Empaque",
        default=1,
        help="Cantidad de envases dentro de la presentación (ej. 12, 24, 36, 4 o 1).",
    )
    cost_supplies_pen = fields.Float(
        string="Costo Total Suministros (S/)",
        digits="Product Price",
        help="Suma de Etiqueta + Termoencogible + Envase + Tapa + Tapón/Laina + Caja.",
    )
    cost_raw_material_pen = fields.Float(
        string="Costo Materia Prima (S/)",
        digits="Product Price",
        help="Costo del líquido/polvo importado o pre-mezclado contenido en la presentación.",
    )
    total_production_cost_pen = fields.Float(
        string="Costo Directo Producción (S/)",
        compute="_compute_conagra_costing_matrix",
        store=True,
        digits="Product Price",
    )
    applied_overhead_pct = fields.Float(
        string="% G. Indirectos + G. Fijos Aplicado",
        compute="_compute_conagra_costing_matrix",
        store=True,
        digits=(16, 2),
        help="Toma dinámicamente el % de Gastos Indirectos/Fijos calculado en la compañía (o 35% manual).",
    )
    final_manufacturing_cost_pen = fields.Float(
        string="*Costo Final de Fabricación (S/)",
        compute="_compute_conagra_costing_matrix",
        store=True,
        digits="Product Price",
        help="Costo Directo Producción * (1 + % Gastos Indirectos y Fijos).",
    )
    min_margin_pct = fields.Float(
        string="% Margen Mínimo Objetivo",
        default=35.0,
    )
    equity_factor_t_equit = fields.Float(
        string="Factor Equidad Presentación (T-EQUIT)",
        default=1.0,
        digits=(12, 4),
    )
    suggested_distributor_price_pen = fields.Float(
        string="Precio Sugerido Distribuidor (S/)",
        compute="_compute_conagra_costing_matrix",
        store=True,
        digits="Product Price",
    )
    freight_surcharge_piura = fields.Float(string="Flete Tienda Piura (S/)", default=0.0)
    freight_surcharge_huaura = fields.Float(string="Flete Tienda Huaura (S/)", default=0.0)
    freight_surcharge_casma = fields.Float(string="Flete Tienda Casma (S/)", default=0.0)
    freight_surcharge_imperial = fields.Float(string="Flete Tienda Imperial/Cañete (S/)", default=0.0)

    @api.onchange("conagra_business_line_id")
    def _onchange_conagra_business_line_id(self):
        if self.conagra_business_line_id:
            self.base_commission_pct = self.conagra_business_line_id.default_commission_pct
            self.max_discount_pct = self.conagra_business_line_id.default_max_discount_pct

    @api.onchange("presentation_id")
    def _onchange_presentation_id(self):
        if self.presentation_id:
            self.pack_units_factor = self.presentation_id.pack_units_factor
            self.equity_factor_t_equit = self.presentation_id.equity_factor_t_equit

    @api.onchange("categ_id", "conagra_business_line_id")
    def _onchange_categ_id_conagra_code(self):
        for tmpl in self:
            prefix = tmpl._get_conagra_category_prefix(tmpl.categ_id)
            if prefix:
                current_code = (tmpl.conagra_internal_code or "").strip().upper()
                if not current_code.startswith(f"{prefix}-"):
                    tmpl.conagra_internal_code = tmpl._generate_conagra_code(prefix)
            else:
                tmpl.conagra_internal_code = False

    def _get_conagra_category_prefix(self, category):
        if category:
            if category.conagra_code_prefix:
                return category.conagra_code_prefix.strip().upper()
            auto_prefix = category._get_auto_hierarchy_prefix()
            if auto_prefix:
                return auto_prefix
        if len(self) == 1 and self.conagra_business_line_id and self.conagra_business_line_id.code:
            return self.conagra_business_line_id.code.strip().upper()
        return False

    def _generate_conagra_code(self, prefix):
        domain = [("conagra_internal_code", "=like", f"{prefix}-%")]
        rec_id = False
        if len(self) == 1:
            rec_id = (self._origin.id if self._origin else False) or (
                self.id if isinstance(self.id, int) else False
            )
        if rec_id:
            domain.append(("id", "!=", rec_id))
        existing_codes = (
            self.with_context(active_test=False)
            .search(domain)
            .mapped("conagra_internal_code")
        )
        max_num = 0
        prefix_dash = f"{prefix}-".upper()
        for code in existing_codes:
            if code and code.strip().upper().startswith(prefix_dash):
                suffix = code.strip()[len(prefix_dash):].strip()
                if suffix.isdigit():
                    max_num = max(max_num, int(suffix))
        return f"{prefix}-{(max_num + 1):04d}"

    def action_generate_conagra_code(self):
        """Genera o regenera el código interno en base a la categoría actual."""
        for tmpl in self:
            prefix = tmpl._get_conagra_category_prefix(tmpl.categ_id) or "CNG"
            tmpl.conagra_internal_code = tmpl._generate_conagra_code(prefix)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        templates = super().create(vals_list)
        for tmpl in templates:
            if not tmpl.conagra_internal_code:
                prefix = tmpl._get_conagra_category_prefix(tmpl.categ_id)
                if prefix:
                    tmpl.conagra_internal_code = tmpl._generate_conagra_code(prefix)
        return templates

    @api.depends(
        "cost_supplies_pen",
        "cost_raw_material_pen",
        "min_margin_pct",
        "equity_factor_t_equit",
        "is_bonus_free_item",
        "company_id.conagra_effective_overhead_pct",
    )
    def _compute_conagra_costing_matrix(self):
        default_company = self.env.company
        for tmpl in self:
            if tmpl.is_bonus_free_item:
                tmpl.total_production_cost_pen = 0.0
                tmpl.applied_overhead_pct = 0.0
                tmpl.final_manufacturing_cost_pen = 0.0
                tmpl.suggested_distributor_price_pen = 0.0
                continue

            company = tmpl.company_id or default_company
            overhead_pct = company.conagra_effective_overhead_pct or 35.0
            direct_cost = (tmpl.cost_supplies_pen or 0.0) + (tmpl.cost_raw_material_pen or 0.0)
            final_cost = direct_cost * (1.0 + (overhead_pct / 100.0))
            margin_factor = 1.0 + ((tmpl.min_margin_pct or 35.0) / 100.0)
            eq_factor = tmpl.equity_factor_t_equit or 1.0

            tmpl.total_production_cost_pen = round(direct_cost, 4)
            tmpl.applied_overhead_pct = overhead_pct
            tmpl.final_manufacturing_cost_pen = round(final_cost, 4)
            tmpl.suggested_distributor_price_pen = round(
                final_cost * margin_factor * eq_factor, 2
            )

    def action_recalculate_overhead_and_prices(self):
        """Recalcula el % de Gastos Indirectos/Fijos de la compañía y actualiza el costo final de los productos."""
        self.env.company._compute_conagra_overhead_metrics()
        self._compute_conagra_costing_matrix()
        return True


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    is_premix_dilution = fields.Boolean(
        string="Es Pre-Mezcla / Dilución (Ej. Cytex 100, Flow Bee, Dye Blue)",
        default=False,
        help="Indica si esta receta corresponde a una dilución con agua desionizada o mezcla previa antes del reenvasado.",
    )
    presentation_id = fields.Many2one(
        comodel_name="conagra.master.presentation",
        string="Presentación de Empaque (Tabla Maestra)",
    )
    pack_factor = fields.Integer(
        string="Factor de Empaque (Unidades por Caja)",
        default=12,
        help="Factor multiplicador de suministros (Etiqueta, Termoencogible, Frasco, Tapa, Laina/Tapón).",
    )

    @api.onchange("presentation_id")
    def _onchange_presentation_id_bom(self):
        if self.presentation_id:
            self.pack_factor = self.presentation_id.pack_units_factor


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    source_bulky_lot_id = fields.Many2one(
        comodel_name="stock.lot",
        string="Lote Madre (Bulky 1000L / DUA Importación)",
        help="Trazabilidad del contenedor o Bulky de 1000L del cual se está reenvasando o mezclando.",
    )
    merma_quantity = fields.Float(
        string="Merma Registrada en Proceso (L / Kg)",
        default=0.0,
        help="Control de merma real ocurrida durante el reenvasado o dilución en planta.",
    )
    applied_overhead_pct = fields.Float(
        string="% Gastos Indirectos/Fijos del Mes",
        default=lambda self: self.env.company.conagra_effective_overhead_pct or 35.0,
        readonly=True,
    )


class StockLot(models.Model):
    _inherit = "stock.lot"

    dua_reference = fields.Char(
        string="Número de DUA / Importación",
        help="Número de Declaración Aduanera de Mercancías de origen.",
    )
    senasa_expiration_date = fields.Date(
        string="Vencimiento SENASA (1 Año)",
        compute="_compute_conagra_dual_expirations",
        store=True,
        readonly=False,
    )
    factory_expiration_date = fields.Date(
        string="Vencimiento Real Fábrica (5 Años)",
        compute="_compute_conagra_dual_expirations",
        store=True,
        readonly=False,
    )

    @api.depends("create_date")
    def _compute_conagra_dual_expirations(self):
        today = fields.Date.context_today(self)
        for lot in self:
            base_date = lot.create_date.date() if lot.create_date else today
            if not lot.senasa_expiration_date:
                lot.senasa_expiration_date = base_date + timedelta(days=365)
            if not lot.factory_expiration_date:
                lot.factory_expiration_date = base_date + timedelta(days=365 * 5)


class StockLandedCost(models.Model):
    _inherit = "stock.landed.cost"

    dua_number = fields.Char(
        string="Número de DUA Aduanas",
        tracking=True,
    )
    container_number = fields.Char(
        string="N° Contenedor / BL",
        tracking=True,
    )
    customs_agency_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Agencia de Aduana / Almacén (Ej. SGL, Alfosac, Villas Oquendo)",
    )
    fob_total_usd = fields.Float(
        string="Valor Total Factura FOB (USD)",
        digits=(16, 2),
    )
    nationalization_expenses_usd = fields.Float(
        string="Gastos Nacionalización / Liberación (USD)",
        digits=(16, 2),
        help="Flete marítimo, seguro, transporte interno, almacenaje, agencia de aduana, VoBo, sobrestadía, SENASA.",
    )
    proforma_advance_usd = fields.Float(
        string="Abono contra Proforma (USD)",
        digits=(16, 2),
    )
    letter_interest_usd = fields.Float(
        string="Intereses de Letras de Importación (USD)",
        digits=(16, 2),
    )
    liquidation_balance_usd = fields.Float(
        string="Saldo Liquidación vs Proforma (USD)",
        compute="_compute_conagra_import_metrics",
        store=True,
    )
    cost_increase_pct = fields.Float(
        string="% Incremento sobre Costo FOB",
        compute="_compute_conagra_import_metrics",
        store=True,
        digits=(16, 2),
    )
    protected_exchange_rate = fields.Float(
        string="TC Protegido CONAGRA (S/)",
        default=lambda self: self.env.company.conagra_protected_exchange_rate or 4.12,
        digits=(12, 4),
    )
    imported_gallons_qty = fields.Float(
        string="Cantidad Importada en Galones (USA)",
        default=0.0,
    )
    converted_liters_qty = fields.Float(
        string="Equivalente en Litros (x 3.785)",
        compute="_compute_conagra_import_metrics",
        store=True,
    )
    imported_pounds_qty = fields.Float(
        string="Cantidad Importada en Libras (Lbs)",
        default=0.0,
    )
    converted_kilos_qty = fields.Float(
        string="Equivalente en Kilos (x 0.454)",
        compute="_compute_conagra_import_metrics",
        store=True,
    )
    unit_cost_liter_or_kg_pen = fields.Float(
        string="Costo Puesto en Planta por Litro/Kg (S/ con TC Protegido)",
        compute="_compute_conagra_import_metrics",
        store=True,
        digits="Product Price",
    )

    @api.depends(
        "fob_total_usd",
        "nationalization_expenses_usd",
        "proforma_advance_usd",
        "letter_interest_usd",
        "protected_exchange_rate",
        "imported_gallons_qty",
        "imported_pounds_qty",
    )
    def _compute_conagra_import_metrics(self):
        for rec in self:
            total_expenses = (rec.nationalization_expenses_usd or 0.0) + (
                rec.letter_interest_usd or 0.0
            )
            rec.liquidation_balance_usd = (rec.proforma_advance_usd or 0.0) - total_expenses
            if rec.fob_total_usd > 0:
                rec.cost_increase_pct = round(
                    (total_expenses / rec.fob_total_usd) * 100.0, 2
                )
            else:
                rec.cost_increase_pct = 0.0

            liters = round((rec.imported_gallons_qty or 0.0) * 3.785, 3)
            kilos = round((rec.imported_pounds_qty or 0.0) * 0.454, 3)
            rec.converted_liters_qty = liters
            rec.converted_kilos_qty = kilos

            total_landed_usd = (rec.fob_total_usd or 0.0) + total_expenses
            tc = rec.protected_exchange_rate or 4.12
            total_units = liters or kilos or 0.0
            if total_units > 0:
                rec.unit_cost_liter_or_kg_pen = round(
                    (total_landed_usd / total_units) * tc, 4
                )
            else:
                rec.unit_cost_liter_or_kg_pen = 0.0
