#Aqui se completa la mayoria de cambios en campos incluyendo el WS para saber el estado Activo y habido
import logging
import requests
import urllib3
from odoo import models, fields, api

_logger = logging.getLogger(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # --- CAMPOS DE PERFILACIÓN ---
    tamano_empresa = fields.Selection([
        ('MICRO', 'Microempresa (1-10)'),
        ('PEQUEÑA', 'Pequeña (11-50)'),
        ('MEDIANA', 'Mediana (51-250)'),
        ('GRANDE', 'Grande (250+)'),
        ('CORPORATIVA', 'Corporación')
    ], string='Tamaño de Empresa')
    
    # Campo editable manualmente como pediste
    numero_trabajadores = fields.Integer(string='Nº Trabajadores')
    
    tipo_cuenta = fields.Selection([
        ('nueva', 'Nueva'),
        ('mantenimiento', 'Mantenimiento')
    ], string='Tipo de Cuenta', default='nueva')

    # --- CAMPOS SUNAT ---
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

    # ESTE ES EL CAMPO QUE DABA EL ERROR
    riesgo_crediticio = fields.Selection([
        ('bajo', 'Bajo'),
        ('medio', 'Medio'),
        ('alto', 'Alto')
    ], string='Riesgo Crediticio')

    # --- CAMPOS DE CONTACTO ---
    rol_decision = fields.Selection([
        ('usuario', 'Usuario'),
        ('influyente', 'Influyente'),
        ('decisor', 'Decisor'),
        ('pagos', 'Pagos')
    ], string='Rol en la Decisión')

    preferencia_contacto = fields.Boolean(string='Preferencia de Contacto')

    # --- LÓGICA DE SEGMENTACIÓN MANUAL ---
    @api.onchange('numero_trabajadores')
    def _onchange_numero_trabajadores_manual(self):
        if self.numero_trabajadores:
            if self.numero_trabajadores <= 10: self.tamano_empresa = 'MICRO'
            elif self.numero_trabajadores <= 50: self.tamano_empresa = 'PEQUEÑA'
            elif self.numero_trabajadores <= 250: self.tamano_empresa = 'MEDIANA'
            else: self.tamano_empresa = 'GRANDE'

    # --- LÓGICA DE CONSULTA RUC ---
    @api.onchange('vat')
    def _onchange_vat_sunat(self):
        if not self.vat or len(self.vat) != 11:
            return

        token = "49523193e61a980b7af0fa009d4e71cbf1b8e45b8ba58d481ba71d104bd1b6c1" 
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', 'Accept': 'application/json'}
        params = {'ruc': self.vat}

        try:
            res = requests.post("https://apiperu.dev/api/ruc", json=params, headers=headers, timeout=10, verify=False)
            if res.status_code == 200:
                res_json = res.json()
                if res_json.get('success'):
                    data = res_json.get('data', {})
                    self.name = data.get('nombre_o_razon_social', self.name)
                    self.street = data.get('direccion', self.street)
                    self.city = data.get('provincia', self.city)
                    
                    estado_api = data.get('estado', '').upper()
                    if estado_api == 'ACTIVO': self.estado_contribuyente = 'ACTIVO'
                    elif 'BAJA DE OFICIO' in estado_api: self.estado_contribuyente = 'BAJA_OFICIO'
                    elif 'BAJA' in estado_api: self.estado_contribuyente = 'BAJA_DEFINITIVA'
                    elif 'SUSPENSION' in estado_api: self.estado_contribuyente = 'SUSPENSION'
                    else: self.estado_contribuyente = 'OTROS'
                    
                    condicion_api = data.get('condicion', '').upper()
                    if condicion_api == 'HABIDO': self.condicion_contribuyente = 'HABIDO'
                    elif 'NO' in condicion_api: self.condicion_contribuyente = 'NO_HABIDO'
                    else: self.condicion_contribuyente = 'OTROS'
                    
        except Exception as e:
            _logger.error("Error SUNAT: %s", str(e))