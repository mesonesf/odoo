# import requests
# import logging
# from odoo import models, fields, api

# _logger = logging.getLogger(__name__)


# class ResPartner(models.Model):
#     _inherit = 'res.partner'

#     # --- CAMPOS DE PERFILACIÓN EMPRESA ---
#     tamano_empresa = fields.Selection([
#         ('MICRO', 'Microempresa (1-10)'),
#         ('PEQUEÑA', 'Pequeña (11-50)'),
#         ('MEDIANA', 'Mediana (51-250)'),
#         ('GRANDE', 'Grande (250+)'),
#         ('CORPORATIVA', 'Corporación')
#     ], string='Tamaño de Empresa')
    
#     numero_trabajadores = fields.Integer(string='Nº Trabajadores')

#     # MOVIDO DESDE CRM (Punto 2)
#     tipo_cuenta = fields.Selection([
#         ('nueva', 'Nueva'),
#         ('mantenimiento', 'Mantenimiento')
#     ], string='Tipo de Cuenta', default='nueva')

#     # DATOS SUNAT
#     estado_contribuyente = fields.Selection([
#         ('ACTIVO', 'ACTIVO'),
#         ('BAJA_DEFINITIVA', 'BAJA DEFINITIVA'),
#         ('BAJA_PROVISIONAL', 'BAJA PROVISIONAL'),
#         ('SUSPENSION', 'SUSPENSION TEMPORAL'),
#         ('INHABILITADO', 'INHABILITADO'),
#         ('OTROS', 'OTROS')
#     ], string='Estado Contribuyente')

#     condicion_contribuyente = fields.Selection([
#         ('HABIDO', 'HABIDO'),
#         ('NO_HABIDO', 'NO HALLADO / NO HABIDO'),
#         ('OTROS', 'OTROS')
#     ], string='Condición Contribuyente')

#     riesgo_crediticio = fields.Selection([
#         ('bajo', 'Bajo'),
#         ('medio', 'Medio'),
#         ('alto', 'Alto')
#     ], string='Riesgo Crediticio')

#     # --- CAMPOS DE CONTACTO / PERSONA (Punto 1) ---
#     rol_decision = fields.Selection([
#         ('usuario', 'Usuario'),
#         ('influyente', 'Influyente'),
#         ('decisor', 'Decisor'),
#         ('pagos', 'Pagos')
#     ], string='Rol en la Decisión')

#     preferencia_contacto = fields.Boolean(string='Preferencia de Contacto')

#     # --- LOGICA DE CONEXION SUNAT (Punto 5: Empleados) ---
#     @api.onchange('vat')
#     def _onchange_vat_sunat(self):
#         if not self.vat or len(self.vat) != 11:
#             return

#         # # TOKEN DE APISPERU (Debes poner el tuyo real aquí)
#         # token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6Im1lc29uZXNmQGhvdG1haWwuY29tIn0.Gv-b0Qf34vhdP1vJhMxgJyuLRo_kPYu05cZfYlIAtcM" 
#         # url = f"https://api.apis.net.pe/v1/ruc?numero={self.vat}"

#         # try:
#         #     response = requests.get(url, headers={'Authorization': f'Bearer {token}'}, timeout=5)
            
#         #     if response.status_code == 200:
#         #         data = response.json()
                
#         #         self.name = data.get('nombre', '')

#         #         # Estado
#         #         estado_api = data.get('estado', '').upper()
#         #         if 'ACTIVO' in estado_api: self.estado_contribuyente = 'ACTIVO'
#         #         elif 'BAJA' in estado_api: self.estado_contribuyente = 'BAJA_DEFINITIVA'
#         #         elif 'SUSPENSION' in estado_api: self.estado_contribuyente = 'SUSPENSION'
#         #         else: self.estado_contribuyente = 'OTROS'

#         #         # Condición
#         #         condicion_api = data.get('condicion', '').upper()
#         #         if 'HABIDO' == condicion_api: self.condicion_contribuyente = 'HABIDO'
#         #         elif 'NO HABIDO' in condicion_api: self.condicion_contribuyente = 'NO_HABIDO'
#         #         else: self.condicion_contribuyente = 'OTROS'

#         #         # Dirección
#         #         self.street = data.get('direccion', '')
#         #         self.city = data.get('provincia', '')
                
#         #         # PUNTO 5: Intentar obtener número de trabajadores
#         #         # La API devuelve a veces 'trabajadores' o 'empleados' dependiendo la versión
#         #         if data.get('trabajadores'):
#         #             try:
#         #                 self.numero_trabajadores = int(data.get('trabajadores'))
#         #             except:
#         #                 pass

#         # --- CONFIGURACIÓN PARA APIPERU.DEV ---
#         token = "49523193e61a980b7af0fa009d4e71cbf1b8e45b8ba58d481ba71d104bd1b6c1" 
#         headers = {
#             'Authorization': f'Bearer {token}',
#             'Content-Type': 'application/json',
#             'Accept': 'application/json'
#         }
#         params = {'ruc': self.vat}

#         try:
#             # 1. DATOS GENERALES (Endpoint /api/ruc)
#             res_ruc = requests.post("https://apiperu.dev/api/ruc", json=params, headers=headers, timeout=10, verify=False)
#             if res_ruc.status_code == 200:
#                 data = res_ruc.json().get('data', {})
#                 if data:
#                     self.name = data.get('nombre_o_razon_social', self.name)
#                     self.street = data.get('direccion', self.street)
#                     self.city = data.get('provincia', self.city)
                    
#                     estado = data.get('estado', '').upper()
#                     self.estado_contribuyente = 'ACTIVO' if 'ACTIVO' in estado else 'OTROS'
                    
#                     condicion = data.get('condicion', '').upper()
#                     self.condicion_contribuyente = 'HABIDO' if 'HABIDO' in condicion else 'NO_HABIDO'

#             # 2. TRABAJADORES (Endpoint /api/ruc_trabajadores - Tu código PHP)
#             _logger.info(">>> Consultando trabajadores para RUC: %s", self.vat)
#             res_trab = requests.post("https://apiperu.dev/api/ruc_trabajadores", json=params, headers=headers, timeout=15, verify=False)
            
#             if res_trab.status_code == 200:
#                 trab_json = res_trab.json()
#                 _logger.info(">>> Respuesta Trabajadores: %s", trab_json)

#                 if trab_json.get('success'):
#                     periodos = trab_json.get('data', [])
#                     if periodos:
#                         # Obtenemos el registro más reciente (el de arriba)
#                         ultimo = periodos[0] 
#                         # Extraemos el número (ej. los 85 que viste en la web)
#                         cantidad = ultimo.get('numero_trabajadores', 0)
#                         self.numero_trabajadores = int(cantidad)

#                         # Auto-segmentación según ley Mype Perú
#                         if self.numero_trabajadores <= 10: self.tamano_empresa = 'MICRO'
#                         elif self.numero_trabajadores <= 50: self.tamano_empresa = 'PEQUEÑA'
#                         elif self.numero_trabajadores <= 250: self.tamano_empresa = 'MEDIANA'
#                         else: self.tamano_empresa = 'GRANDE'
#                 else:
#                     _logger.warning(">>> API success=False en trabajadores: %s", trab_json.get('message'))

#         except Exception as e:
#             # Ahora el logger ya no dará error porque está definido arriba
#             _logger.error(">>> Error crítico en consulta SUNAT: %s", str(e))

#Aqui se completa la mayoria de cambios en campos incluyendo el WS para saber el estado Activo y habido
import logging
import requests
import urllib3
from odoo import models, fields, api

_logger = logging.getLogger(__name__)
# Esto evita que el log se llene de advertencias de seguridad de la API
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # --- CAMPOS DE PERFILACIÓN (NECESARIOS PARA EL XML) ---
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
        ('SUSPENSION', 'SUSPENSION TEMPORAL'),
        ('OTROS', 'OTROS')
    ], string='Estado del Contribuyente')

    condicion_contribuyente = fields.Selection([
        ('HABIDO', 'HABIDO'),
        ('NO_HABIDO', 'NO HALLADO / NO HABIDO'),
        ('OTROS', 'OTROS')
    ], string='Condición del Contribuyente')

    riesgo_crediticio = fields.Selection([
        ('bajo', 'Bajo'),
        ('medio', 'Medio'),
        ('alto', 'Alto')
    ], string='Riesgo Crediticio')

    # CAMPOS DE CONTACTO HIJO (Para evitar el ParseError en el XML)
    rol_decision = fields.Selection([
        ('usuario', 'Usuario'),
        ('influyente', 'Influyente'),
        ('decisor', 'Decisor'),
        ('pagos', 'Pagos')
    ], string='Rol en la Decisión')

    preferencia_contacto = fields.Boolean(string='Preferencia de Contacto')

    @api.onchange('vat')
    def _onchange_vat_sunat(self):
        if not self.vat or len(self.vat) != 11:
            return

        # --- CONFIGURACIÓN PARA APIPERU.DEV ---
        token = "49523193e61a980b7af0fa009d4e71cbf1b8e45b8ba58d481ba71d104bd1b6c1" 
        headers = {
            'Authorization': f'Bearer {token}', 
            'Content-Type': 'application/json', 
            'Accept': 'application/json'
        }
        params = {'ruc': self.vat}

        try:
            # 1. CONSULTA DATOS GENERALES
            res = requests.post("https://apiperu.dev/api/ruc", json=params, headers=headers, timeout=10, verify=False)
            if res.status_code == 200:
                res_json = res.json()
                if res_json.get('success'):
                    data = res_json.get('data', {})
                    self.name = data.get('nombre_o_razon_social', self.name)
                    self.street = data.get('direccion', self.street)
                    self.city = data.get('provincia', self.city)
                    
                    estado = data.get('estado', '').upper()
                    self.estado_contribuyente = 'ACTIVO' if 'ACTIVO' in estado else 'OTROS'
                    
                    condicion = data.get('condicion', '').upper()
                    self.condicion_contribuyente = 'HABIDO' if 'HABIDO' in condicion else 'NO_HABIDO'

            # 2. CONSULTA TRABAJADORES
            # Nota: Si el log sigue dando Status 403, es porque se necesita plan de pago en la API
            _logger.info(">>> Consultando trabajadores para RUC: %s", self.vat)
            res_trab = requests.post("https://apiperu.dev/api/ruc_trabajadores", json=params, headers=headers, timeout=10, verify=False)
            
            if res_trab.status_code == 200:
                trab_json = res_trab.json()
                if trab_json.get('success'):
                    periodos = trab_json.get('data', [])
                    if periodos and len(periodos) > 0:
                        ultimo_periodo = periodos[0]
                        cantidad = ultimo_periodo.get('numero_trabajadores') or ultimo_periodo.get('total') or 0
                        self.numero_trabajadores = int(cantidad)
                        
                        # Auto-segmentación
                        if self.numero_trabajadores <= 10: self.tamano_empresa = 'MICRO'
                        elif self.numero_trabajadores <= 50: self.tamano_empresa = 'PEQUEÑA'
                        elif self.numero_trabajadores <= 250: self.tamano_empresa = 'MEDIANA'
                        else: self.tamano_empresa = 'GRANDE'
            else:
                _logger.error(">>> Fallo en API Trabajadores: Status %s. Esto suele ser por falta de suscripción en ApiPeru.dev", res_trab.status_code)

        except Exception as e:
            _logger.error("Error SUNAT: %s", str(e))