# -*- coding: utf-8 -*-
import logging
import math
from datetime import timedelta

import requests
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


def _haversine_meters(lat1, lon1, lat2, lon2):
    """Calcula la distancia en metros entre dos coordenadas GPS (Vehículo vs Agencia de Transporte)."""
    if not all([lat1, lon1, lat2, lon2]):
        return 999999.0
    radius_earth = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return radius_earth * c


class StockPicking(models.Model):
    _inherit = "stock.picking"

    transport_agency_id = fields.Many2one(
        comodel_name="res.partner",
        string="Agencia de Transporte (Shalom / Marvisur / Móvil Bus)",
        domain="[('is_transport_agency', '=', True)]",
        tracking=True,
    )
    vehicle_id = fields.Many2one(
        comodel_name="fleet.vehicle",
        string="Camioneta / Vehículo de Reparto",
        tracking=True,
    )
    driver_employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Chofer Asignado",
        tracking=True,
    )
    boxes_count = fields.Integer(
        string="Cantidad Total de Bultos / Cajas",
        default=1,
        tracking=True,
    )
    vehicle_capacity_warning = fields.Char(
        string="Alerta de Capacidad de Camioneta",
        compute="_compute_vehicle_capacity_warning",
    )
    agency_stamped_guide_photo = fields.Binary(
        string="Foto Guía Sellada por Agencia (Chofer)",
        attachment=True,
        help="Fotografía tomada por el chofer o ayudante con el sello de recepción de Shalom/Marvisur/Móvil Bus.",
    )
    agency_stamped_guide_filename = fields.Char(string="Nombre Archivo Foto Guía")
    gps_agency_visit_detected = fields.Boolean(
        string="Visita a Agencia Verificada por GPS",
        default=False,
        readonly=True,
        tracking=True,
    )
    gps_agency_visit_datetime = fields.Datetime(
        string="Fecha/Hora Detección GPS en Agencia",
        readonly=True,
    )
    salesperson_delivery_confirmed = fields.Boolean(
        string="Recepción Confirmada por Vendedor/Cliente",
        default=False,
        tracking=True,
        help="Confirmación obligatoria del vendedor de que el cliente recogió la mercadería conforme en la agencia destino.",
    )
    salesperson_confirmation_date = fields.Datetime(
        string="Fecha Confirmación Vendedor",
        readonly=True,
    )

    @api.depends("boxes_count", "vehicle_id", "vehicle_id.max_box_capacity")
    def _compute_vehicle_capacity_warning(self):
        for picking in self:
            if (
                picking.vehicle_id
                and picking.vehicle_id.max_box_capacity > 0
                and picking.boxes_count > picking.vehicle_id.max_box_capacity
            ):
                picking.vehicle_capacity_warning = (
                    f"⚠️ Exceso de Capacidad: Este despacho tiene {picking.boxes_count} cajas "
                    f"y la capacidad máxima de '{picking.vehicle_id.name}' es de "
                    f"{picking.vehicle_id.max_box_capacity} cajas."
                )
            else:
                picking.vehicle_capacity_warning = False

    def button_validate(self):
        for picking in self:
            if (
                picking.picking_type_code == "outgoing"
                and picking.driver_employee_id
                and picking.driver_employee_id.is_sctr_expired
            ):
                raise ValidationError(
                    f"Bloqueo de Seguridad SCTR (CONAGRA): El chofer/ingeniero "
                    f"'{picking.driver_employee_id.name}' tiene el seguro SCTR vencido "
                    f"({picking.driver_employee_id.sctr_due_date}). Renueve el SCTR antes de salir a despacho o fundo."
                )
        return super().button_validate()

    def action_driver_notify_stamped_guide(self):
        """Notifica al vendedor de la orden que la mercadería ya fue dejada en la agencia con foto de la guía sellada."""
        self.ensure_one()
        if not self.agency_stamped_guide_photo:
            raise ValidationError(
                "El chofer debe subir la foto de la Guía de Remisión sellada por la agencia antes de notificar."
            )
        salesperson = self.sale_id.user_id or self.user_id
        partner_ids = [salesperson.partner_id.id] if salesperson and salesperson.partner_id else []
        msg = Markup(
            '<div style="border-left: 4px solid #007bff; background-color: #eef6ff; padding: 10px;">'
            "📦 <b>Mercadería Entregada en Agencia de Transporte</b><br/>"
            "• <b>Agencia:</b> %s<br/>"
            "• <b>Bultos/Cajas:</b> %s<br/>"
            "• <b>Vehículo:</b> %s<br/>"
            "<i>Se adjuntó la foto de la guía sellada. Por favor, hacer seguimiento con el cliente y pulsar "
            "<b>Confirmar Recepción Cliente</b>.</i>"
            "</div>"
        ) % (
            self.transport_agency_id.name if self.transport_agency_id else "Directo",
            self.boxes_count,
            self.vehicle_id.name if self.vehicle_id else "-",
        )
        self.message_post(
            body=msg,
            partner_ids=partner_ids,
            subtype_xmlid="mail.mt_note",
        )
        return True

    def action_salesperson_confirm_delivery(self):
        """El vendedor confirma que vio la guía y que el cliente recibió conforme en destino."""
        for picking in self:
            picking.write({
                "salesperson_delivery_confirmed": True,
                "salesperson_confirmation_date": fields.Datetime.now(),
            })
            picking.message_post(
                body=Markup(
                    "✅ <b>Recepción Confirmada por el Vendedor:</b> El cliente recibió la mercadería conforme."
                ),
                subtype_xmlid="mail.mt_note",
            )
        return True


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    gps_device_imei = fields.Char(
        string="ID / IMEI Dispositivo GPS",
        index=True,
        help="Identificador único del equipo GPS instalado en el vehículo según la plataforma del proveedor.",
    )
    gps_assigned_zone_id = fields.Many2one(
        comodel_name="conagra.master.zona",
        string="Zona / Geocerca Autorizada (Tabla Maestra)",
        tracking=True,
    )
    gps_latitude = fields.Float(string="Última Latitud GPS", digits=(10, 7), readonly=True)
    gps_longitude = fields.Float(string="Última Longitud GPS", digits=(10, 7), readonly=True)
    gps_speed_kmh = fields.Float(string="Velocidad Actual (km/h)", readonly=True)
    gps_last_address = fields.Char(string="Dirección / Referencia GPS", readonly=True)
    gps_last_sync = fields.Datetime(string="Última Sincronización API GPS", readonly=True)
    gps_out_of_zone_alert = fields.Boolean(
        string="Alerta: Fuera de Geocerca / Zona Autorizada",
        default=False,
        tracking=True,
    )
    gps_google_maps_url = fields.Char(
        string="Ver en Mapa",
        compute="_compute_gps_google_maps_url",
    )

    max_box_capacity = fields.Integer(
        string="Capacidad Máxima de Cajas (Reparto)",
        default=80,
        help="Cantidad máxima de cajas que puede cargar esta unidad (ej. Toyota Hilux / Camión).",
    )
    soat_due_date = fields.Date(string="Vencimiento SOAT", tracking=True)
    technical_review_due_date = fields.Date(string="Vencimiento Revisión Técnica", tracking=True)
    insurance_policy_due_date = fields.Date(string="Vencimiento Póliza Vehicular", tracking=True)
    driver_license_number = fields.Char(string="N° Brevete Conductor")
    driver_license_due_date = fields.Date(string="Vencimiento Brevete Conductor", tracking=True)
    next_maintenance_odometer = fields.Float(
        string="Próximo Mantenimiento Preventivo (Km)",
        help="Kilometraje objetivo en el que debe saltar la alerta de mantenimiento preventivo.",
    )
    compliance_alert_status = fields.Selection(
        selection=[
            ("ok", "Al Día"),
            ("warning", "Por Vencer (< 15 días / Km cercano)"),
            ("expired", "Vencido / Alerta Crítica"),
        ],
        string="Estado Documentario y Mantenimiento",
        compute="_compute_compliance_alert_status",
        store=True,
    )

    @api.depends("gps_latitude", "gps_longitude")
    def _compute_gps_google_maps_url(self):
        for vehicle in self:
            if vehicle.gps_latitude and vehicle.gps_longitude:
                vehicle.gps_google_maps_url = (
                    f"https://www.google.com/maps/search/?api=1&query="
                    f"{vehicle.gps_latitude},{vehicle.gps_longitude}"
                )
            else:
                vehicle.gps_google_maps_url = False

    @api.depends(
        "soat_due_date",
        "technical_review_due_date",
        "insurance_policy_due_date",
        "driver_license_due_date",
        "odometer",
        "next_maintenance_odometer",
    )
    def _compute_compliance_alert_status(self):
        today = fields.Date.context_today(self)
        warning_limit = today + timedelta(days=15)
        for vehicle in self:
            dates = [
                d
                for d in (
                    vehicle.soat_due_date,
                    vehicle.technical_review_due_date,
                    vehicle.insurance_policy_due_date,
                    vehicle.driver_license_due_date,
                )
                if d
            ]
            odometer_due = (
                vehicle.next_maintenance_odometer > 0
                and vehicle.odometer >= vehicle.next_maintenance_odometer
            )
            if any(d < today for d in dates) or odometer_due:
                vehicle.compliance_alert_status = "expired"
            elif any(d <= warning_limit for d in dates) or (
                vehicle.next_maintenance_odometer > 0
                and vehicle.odometer >= (vehicle.next_maintenance_odometer - 500)
            ):
                vehicle.compliance_alert_status = "warning"
            else:
                vehicle.compliance_alert_status = "ok"

    def action_sync_gps_from_provider(self):
        """Consulta el API REST del proveedor GPS de CONAGRA (Pamela) y actualiza ubicación, geocerca y visitas a agencias."""
        company = self.env.company
        api_url = company.conagra_gps_api_url
        api_token = company.conagra_gps_api_token
        radius_m = company.conagra_gps_agency_radius_meters or 250.0

        if not api_url or not api_token:
            return False

        try:
            response = requests.get(
                api_url,
                headers={"Authorization": f"Bearer {api_token}", "Accept": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as err:
            _logger.warning("No se pudo conectar al API GPS de CONAGRA: %s", err)
            return False

        items = payload.get("data", payload) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            return False

        by_imei = {
            str(item.get("imei") or item.get("device_id") or item.get("plate", "")): item
            for item in items
            if isinstance(item, dict)
        }

        agencies = self.env["res.partner"].sudo().search([
            ("is_transport_agency", "=", True),
            ("partner_latitude", "!=", 0.0),
            ("partner_longitude", "!=", 0.0),
        ])

        now = fields.Datetime.now()
        for vehicle in self.filtered(lambda v: v.gps_device_imei or v.license_plate):
            gps_data = by_imei.get(vehicle.gps_device_imei) or by_imei.get(
                vehicle.license_plate
            )
            if not gps_data:
                continue

            lat = float(gps_data.get("latitude") or gps_data.get("lat") or 0.0)
            lon = float(gps_data.get("longitude") or gps_data.get("lng") or 0.0)
            speed = float(gps_data.get("speed") or 0.0)
            out_of_geofence = bool(gps_data.get("out_of_geofence", False))
            odometer_val = float(gps_data.get("odometer") or 0.0)

            vals = {
                "gps_latitude": lat,
                "gps_longitude": lon,
                "gps_speed_kmh": speed,
                "gps_last_address": gps_data.get("address") or vehicle.gps_last_address,
                "gps_out_of_zone_alert": out_of_geofence,
                "gps_last_sync": now,
            }
            if odometer_val > vehicle.odometer:
                vals["odometer"] = odometer_val
            vehicle.sudo().write(vals)

            if out_of_geofence:
                zone_name = (
                    vehicle.gps_assigned_zone_id.name
                    if vehicle.gps_assigned_zone_id
                    else "Sin geocerca asignada"
                )
                vehicle.sudo().message_post(
                    body=Markup(
                        f"🚨 <b>Alerta GPS Geocerca:</b> El vehículo <b>{vehicle.name}</b> "
                        f"salió de su zona autorizada ({zone_name}). "
                        f"Ubicación: ({lat}, {lon})."
                    ),
                    subtype_xmlid="mail.mt_note",
                )

            if lat and lon and agencies:
                pending_pickings = self.env["stock.picking"].sudo().search([
                    ("vehicle_id", "=", vehicle.id),
                    ("state", "in", ("assigned", "done")),
                    ("gps_agency_visit_detected", "=", False),
                    ("transport_agency_id", "in", agencies.ids),
                ])
                for picking in pending_pickings:
                    ag = picking.transport_agency_id
                    dist = _haversine_meters(
                        lat, lon, ag.partner_latitude, ag.partner_longitude
                    )
                    if dist <= radius_m:
                        picking.write({
                            "gps_agency_visit_detected": True,
                            "gps_agency_visit_datetime": now,
                        })
                        picking.message_post(
                            body=Markup(
                                f"📍 <b>Confirmación Automática por GPS:</b> El vehículo "
                                f"<b>{vehicle.name}</b> ingresó al radio de la agencia "
                                f"<b>{ag.name}</b> (distancia: {int(dist)} m)."
                            ),
                            subtype_xmlid="mail.mt_note",
                        )
        return True

    @api.model
    def _cron_sync_gps_and_check_fleet_alerts(self):
        """Cron que sincroniza el GPS de toda la flota y notifica vencimientos de SOAT, Revisión Técnica y Brevete."""
        vehicles = self.search([])
        vehicles.action_sync_gps_from_provider()
        vehicles._compute_compliance_alert_status()
        for vehicle in vehicles.filtered(lambda v: v.compliance_alert_status != "ok"):
            vehicle.message_post(
                body=Markup(
                    f"⚠️ <b>Alerta Preventiva de Flota CONAGRA:</b> El vehículo <b>{vehicle.name}</b> "
                    f"presenta documentos (SOAT / Revisión Técnica / Póliza / Brevete) o kilometraje "
                    f"próximos a vencer o vencidos."
                ),
                subtype_xmlid="mail.mt_note",
            )


class FleetVehicleLogServices(models.Model):
    _inherit = "fleet.vehicle.log.services"

    duplicate_repair_warning = fields.Char(
        string="Alerta de Reparación Repetida en Taller",
        compute="_compute_duplicate_repair_warning",
    )

    @api.depends("vehicle_id", "service_type_id", "description", "date")
    def _compute_duplicate_repair_warning(self):
        for log in self:
            if not log.vehicle_id or not log.service_type_id:
                log.duplicate_repair_warning = False
                continue
            ref_date = log.date or fields.Date.context_today(log)
            date_limit = ref_date - timedelta(days=180)
            domain = [
                ("vehicle_id", "=", log.vehicle_id.id),
                ("service_type_id", "=", log.service_type_id.id),
                ("date", ">=", date_limit),
                ("id", "!=", log._origin.id or 0),
            ]
            previous = self.search(domain, order="date desc", limit=1)
            if previous:
                log.duplicate_repair_warning = (
                    f"🚨 ALERTA DE TALLER (CONAGRA): El servicio '{log.service_type_id.name}' "
                    f"ya fue facturado/realizado en este mismo vehículo ('{log.vehicle_id.name}') "
                    f"el día {previous.date} por {previous.amount:.2f}. ¡Verificar garantía o cruce de placa!"
                )
            else:
                log.duplicate_repair_warning = False


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    requires_sctr = fields.Boolean(
        string="Requiere Seguro SCTR (Campo / Planta / Despacho)",
        default=True,
    )
    sctr_policy_number = fields.Char(string="N° Póliza SCTR")
    sctr_due_date = fields.Date(string="Fecha Vencimiento SCTR")
    is_sctr_expired = fields.Boolean(
        string="SCTR Vencido / Sin Cobertura",
        compute="_compute_is_sctr_expired",
        store=True,
    )
    biometric_store_id = fields.Many2one(
        comodel_name="conagra.master.store.location",
        string="Sede / Tienda Base (Tabla Maestra)",
    )
    biometric_device_pin = fields.Char(
        string="Código / PIN Reloj Biométrico (Tiendas y Planta)",
        index=True,
        help="Identificador del trabajador en el lector biométrico de huella de Lima, Piura, Huaura, Casma o Imperial.",
    )

    @api.depends("requires_sctr", "sctr_due_date")
    def _compute_is_sctr_expired(self):
        today = fields.Date.context_today(self)
        for emp in self:
            emp.is_sctr_expired = bool(
                emp.requires_sctr and (not emp.sctr_due_date or emp.sctr_due_date < today)
            )


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    biometric_store_id = fields.Many2one(
        comodel_name="conagra.master.store.location",
        string="Sede del Biométrico (Tabla Maestra)",
    )
    biometric_raw_log_id = fields.Char(
        string="ID Marcación Biométrica",
        index=True,
    )
