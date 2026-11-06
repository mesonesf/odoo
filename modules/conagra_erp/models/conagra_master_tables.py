# -*- coding: utf-8 -*-
from odoo import fields, models


class ConagraMasterZona(models.Model):
    _name = "conagra.master.zona"
    _description = "Tabla Maestra CONAGRA: Zona Agrícola y Geocerca"
    _order = "sequence, name"

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Nombre de Zona / Geocerca", required=True, translate=False)
    code = fields.Char(string="Código")
    keywords = fields.Char(
        string="Palabras Clave (Bot Silverio)",
        help="Provincias, valles o distritos separados por coma para que el Bot Silverio identifique esta zona automáticamente.",
    )
    salesperson_id = fields.Many2one(
        comodel_name="res.users",
        string="Ingeniero / Comercial Asignado",
        domain="[('share', '=', False)]",
    )
    team_id = fields.Many2one(
        comodel_name="crm.team",
        string="Equipo de Ventas",
    )
    default_freight_surcharge = fields.Float(
        string="Recargo de Flete Base Tienda (S/)",
        default=0.0,
    )
    active = fields.Boolean(default=True)


class ConagraMasterCultivo(models.Model):
    _name = "conagra.master.cultivo"
    _description = "Tabla Maestra CONAGRA: Cultivos e Intereses"
    _order = "sequence, name"

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Cultivo / Interés", required=True)
    code = fields.Char(string="Código")
    keywords = fields.Char(
        string="Sinónimos / Variedades (Bot WhatsApp)",
        help="Palabras clave para asociar automáticamente el cultivo escrito por el agricultor.",
    )
    active = fields.Boolean(default=True)


class ConagraMasterBusinessLine(models.Model):
    _name = "conagra.master.business.line"
    _description = "Tabla Maestra CONAGRA: Línea de Negocio"
    _order = "sequence, name"

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Línea de Negocio", required=True)
    code = fields.Char(string="Código")
    default_commission_pct = fields.Float(
        string="% Comisión Base Sugerido",
        default=3.0,
    )
    default_max_discount_pct = fields.Float(
        string="% Tope Descuento Sugerido",
        default=10.0,
    )
    active = fields.Boolean(default=True)


class ConagraMasterPresentation(models.Model):
    _name = "conagra.master.presentation"
    _description = "Tabla Maestra CONAGRA: Tipo de Presentación y Empaque"
    _order = "sequence, name"

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Nombre de la Presentación", required=True)
    code = fields.Char(string="Código")
    pack_units_factor = fields.Integer(
        string="Factor de Unidades por Caja/Empaque",
        default=12,
        required=True,
    )
    equity_factor_t_equit = fields.Float(
        string="Factor de Equidad por Defecto (T-EQUIT)",
        default=1.0,
        digits=(12, 4),
    )
    active = fields.Boolean(default=True)


class ConagraMasterAgencyZone(models.Model):
    _name = "conagra.master.agency.zone"
    _description = "Tabla Maestra CONAGRA: Zona / Cercanía de Agencia de Transporte"
    _order = "sequence, name"

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Zona / Distrito de Agencia", required=True)
    code = fields.Char(string="Código")
    is_distant_alert = fields.Boolean(
        string="Dispara Alerta de Lejanía (>24h)",
        default=False,
        help="Si está activo, cuando un vendedor elija una agencia en esta zona (ej. Los Olivos o Lurín), el pedido mostrará una alerta sugiriendo La Victoria.",
    )
    active = fields.Boolean(default=True)


class ConagraMasterCreditTerm(models.Model):
    _name = "conagra.master.credit.term"
    _description = "Tabla Maestra CONAGRA: Plazo Máximo de Crédito Autorizado"
    _order = "days asc, sequence"

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Descripción del Plazo", required=True)
    days = fields.Integer(string="Días de Crédito", required=True, default=30)
    allows_letras = fields.Boolean(string="Habilita Canje por Letras", default=False)
    active = fields.Boolean(default=True)


class ConagraMasterLetraStatus(models.Model):
    _name = "conagra.master.letra.status"
    _description = "Tabla Maestra CONAGRA: Estado de Letra de Cambio"
    _order = "sequence, name"

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Estado de la Letra", required=True)
    code = fields.Char(string="Código")
    is_overdue_alert = fields.Boolean(string="Es Estado de Protesto / Mora", default=False)
    active = fields.Boolean(default=True)


class ConagraMasterStoreLocation(models.Model):
    _name = "conagra.master.store.location"
    _description = "Tabla Maestra CONAGRA: Sedes, Tiendas y Reloj Biométrico"
    _order = "sequence, name"

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Nombre de Sede / Tienda", required=True)
    code = fields.Char(string="Código")
    zona_id = fields.Many2one(
        comodel_name="conagra.master.zona",
        string="Zona Agrícola Asociada",
    )
    freight_surcharge_pen = fields.Float(
        string="Recargo de Flete por Defecto en Tienda (S/)",
        default=0.0,
    )
    active = fields.Boolean(default=True)


class ConagraMasterCommissionRule(models.Model):
    _name = "conagra.master.commission.rule"
    _description = "Tabla Maestra CONAGRA: Reglas y Tramos de Comisión (Karina)"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Nombre del Tramo / Regla", required=True)
    rule_type = fields.Selection(
        selection=[
            ("discount_tier", "Tramo por % de Descuento Otorgado"),
            ("delay_tier", "Castigo por Días de Mora al Cobro (ATD)"),
            ("new_customer_bonus", "Bono por Cliente Nuevo"),
        ],
        string="Tipo de Regla",
        required=True,
        default="discount_tier",
    )
    threshold_value = fields.Float(
        string="Umbral (> % Descuento o > Días de Mora)",
        default=0.0,
        help="Si el descuento o los días de mora superan este valor, se aplica el factor multiplicador.",
    )
    multiplier_or_bonus = fields.Float(
        string="Factor Multiplicador (0.0 a 1.0) o Bono (+%)",
        default=1.0,
        help="Para tramos de descuento/mora: factor que multiplica la comisión (ej. 0.75 = 75%, 0.0 = pierde comisión). Para cliente nuevo: puntos porcentuales adicionales (ej. 1.0 = +1%).",
    )
    active = fields.Boolean(default=True)
