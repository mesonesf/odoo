import logging
import requests
import urllib3
from odoo import models, fields, api

_logger = logging.getLogger(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # --- CAMPOS (Sin cambios) ---
    tamano_empresa = fields.Selection([
        ('MICRO', 'Microempresa (1-10)'),
        ('PEQUEÑA', 'Pequeña (11-50)'),
        ('MEDIANA', 'Mediana (51-250)'),
        ('GRANDE', 'Grande (250+)'),
        ('CORPORATIVA', 'Corporación')
    ], string='Tamaño de Empresa')
    
    numero_trabajadores = fields.Integer(string='Nº Trabajadores')
    tipo_cuenta = fields.Selection([
        ('nueva', 'Nueva'),
        ('mantenimiento', 'Mantenimiento')
    ], string='Tipo de Cuenta', default='nueva')

    estado_contribuyente = fields.Selection([
        ('ACTIVO', 'ACTIVO'),
        ('BAJA_DEFINITIVA', 'BAJA DEFINITIVA'),
        ('BAJA_OFICIO', 'BAJA DE OFICIO'),
        ('SUSPENSION', 'SUSPENSION TEMPORAL'),
        ('OTROS', 'OTROS')
    ], string='Estado del Contribuyente')

    condicion_contribuyente = fields.Selection([
        ('HABIDO', 'HABIDO'),
        ('NO_HABIDO', 'NO HABIDO'),
        ('OTROS', 'OTROS')
    ], string='Condición del Contribuyente')

    riesgo_crediticio = fields.Selection([
        ('bajo', 'Bajo'), ('medio', 'Medio'), ('alto', 'Alto')
    ], string='Riesgo Crediticio')

    rol_decision = fields.Selection([
        ('usuario', 'Usuario'), ('influyente', 'Influyente'),
        ('decisor', 'Decisor'), ('pagos', 'Pagos')
    ], string='Rol en la Decisión')

    preferencia_contacto = fields.Boolean(string='Preferencia de Contacto')

    # --- LÓGICA DE BÚSQUEDA UNIFICADA ---
    def action_buscar_ruc(self):
        """Función que realiza la búsqueda real en el Web Service"""
        for record in self:
            if not record.vat or len(record.vat) != 11:
                continue

            token = "49523193e61a980b7af0fa009d4e71cbf1b8e45b8ba58d481ba71d104bd1b6c1" 
            headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', 'Accept': 'application/json'}
            params = {'ruc': record.vat}

            try:
                # Opcional: Limpiamos campos antes de buscar para ver el efecto visual
                record.estado_contribuyente = False
                record.condicion_contribuyente = False

                res = requests.post("https://apiperu.dev/api/ruc", json=params, headers=headers, timeout=10, verify=False)
                if res.status_code == 200:
                    res_json = res.json()
                    if res_json.get('success'):
                        data = res_json.get('data', {})
                        record.name = data.get('nombre_o_razon_social', record.name)
                        record.street = data.get('direccion', record.street)
                        record.city = data.get('provincia', record.city)
                        
                        # Mapeo de Estado
                        estado_api = data.get('estado', '').upper()
                        if estado_api == 'ACTIVO': record.estado_contribuyente = 'ACTIVO'
                        elif 'BAJA DE OFICIO' in estado_api: record.estado_contribuyente = 'BAJA_OFICIO'
                        elif 'BAJA' in estado_api: record.estado_contribuyente = 'BAJA_DEFINITIVA'
                        elif 'SUSPENSION' in estado_api: record.estado_contribuyente = 'SUSPENSION'
                        else: record.estado_contribuyente = 'OTROS'
                        
                        # Mapeo de Condición
                        condicion_api = data.get('condicion', '').upper()
                        if condicion_api == 'HABIDO': record.condicion_contribuyente = 'HABIDO'
                        elif 'NO' in condicion_api: record.condicion_contribuyente = 'NO_HABIDO'
                        else: record.condicion_contribuyente = 'OTROS'
                        
            except Exception as e:
                _logger.error("Error SUNAT: %s", str(e))

    # --- EVENTO AL CAMBIAR EL RUC ---
    @api.onchange('vat')
    def _onchange_vat_sunat(self):
        # Cuando el usuario escribe un RUC nuevo, se dispara la búsqueda automáticamente
        if self.vat and len(self.vat) == 11:
            self.action_buscar_ruc()

    @api.onchange('numero_trabajadores')
    def _onchange_numero_trabajadores_manual(self):
        if self.numero_trabajadores:
            if self.numero_trabajadores <= 10: self.tamano_empresa = 'MICRO'
            elif self.numero_trabajadores <= 50: self.tamano_empresa = 'PEQUEÑA'
            elif self.numero_trabajadores <= 250: self.tamano_empresa = 'MEDIANA'
            else: self.tamano_empresa = 'GRANDE'