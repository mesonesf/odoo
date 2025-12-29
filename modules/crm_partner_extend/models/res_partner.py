import requests
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # --- TUS CAMPOS PERSONALIZADOS ---
    tamano_empresa = fields.Selection([
        ('MICRO', 'Microempresa (1-10)'),
        ('PEQUEÑA', 'Pequeña (11-50)'),
        ('MEDIANA', 'Mediana (51-250)'),
        ('GRANDE', 'Grande (250+)'),
        ('CORPORATIVA', 'Corporación')
    ], string='Tamaño de Empresa')
    
    numero_trabajadores = fields.Integer(string='Nº Trabajadores')

    estado_contribuyente = fields.Selection([
        ('ACTIVO', 'ACTIVO'),
        ('BAJA_DEFINITIVA', 'BAJA DEFINITIVA'),
        ('BAJA_PROVISIONAL', 'BAJA PROVISIONAL'),
        ('SUSPENSION', 'SUSPENSION TEMPORAL'),
        ('INHABILITADO', 'INHABILITADO'),
        ('OTROS', 'OTROS')
    ], string='Estado Contribuyente')

    condicion_contribuyente = fields.Selection([
        ('HABIDO', 'HABIDO'),
        ('NO_HABIDO', 'NO HALLADO / NO HABIDO'),
        ('OTROS', 'OTROS')
    ], string='Condición Contribuyente')

    riesgo_crediticio = fields.Selection([
        ('bajo', 'Bajo'),
        ('medio', 'Medio'),
        ('alto', 'Alto')
    ], string='Riesgo Crediticio')

    rol_decision = fields.Selection([
        ('usuario', 'Usuario'),
        ('influyente', 'Influyente'),
        ('decisor', 'Decisor'),
        ('pagos', 'Pagos')
    ], string='Rol en la Decisión')

    preferencia_contacto = fields.Boolean(string='Preferencia de Contacto')

    # --- LOGICA DE CONEXION SUNAT ---
    
    @api.onchange('vat')
    def _onchange_vat_sunat(self):
        """
        Consulta automática a API externa cuando cambia el RUC (vat).
        """
        # 1. Validar que haya un RUC y sea de Perú (11 dígitos)
        if not self.vat or len(self.vat) != 11:
            return

        # ---------------- CONFIGURACIÓN API ----------------
        # REGÍSTRATE EN https://apisperu.com/ para obtener tu token gratis
        token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6Im1lc29uZXNmQGhvdG1haWwuY29tIn0.Gv-b0Qf34vhdP1vJhMxgJyuLRo_kPYu05cZfYlIAtcM" 
        url = f"https://api.apis.net.pe/v1/ruc?numero={self.vat}"
        # ---------------------------------------------------

        try:
            # Hacemos la petición
            response = requests.get(url, headers={'Authorization': f'Bearer {token}'}, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                # 2. Llenar Nombre / Razón Social
                self.name = data.get('nombre', '')

                # 3. Mapear ESTADO (La API devuelve texto, lo pasamos a tu Selection)
                estado_api = data.get('estado', '').upper()
                if 'ACTIVO' in estado_api:
                    self.estado_contribuyente = 'ACTIVO'
                elif 'BAJA' in estado_api:
                    self.estado_contribuyente = 'BAJA_DEFINITIVA'
                elif 'SUSPENSIÓN' in estado_api or 'SUSPENSION' in estado_api:
                    self.estado_contribuyente = 'SUSPENSION'
                else:
                    self.estado_contribuyente = 'OTROS'

                # 4. Mapear CONDICIÓN
                condicion_api = data.get('condicion', '').upper()
                if 'HABIDO' == condicion_api:
                    self.condicion_contribuyente = 'HABIDO'
                elif 'NO HABIDO' in condicion_api or 'NO HALLADO' in condicion_api:
                    self.condicion_contribuyente = 'NO_HABIDO'
                else:
                    self.condicion_contribuyente = 'OTROS'

                # 5. Dirección (Calle, Distrito, Departamento)
                direccion = data.get('direccion', '')
                departamento = data.get('departamento', '')
                provincia = data.get('provincia', '')
                distrito = data.get('distrito', '')
                
                # Concatenamos simple para la calle
                self.street = direccion
                self.city = provincia
                
                # Opcional: Podrías buscar el ID del estado (Departamento) si tienes l10n_pe instalado
                # self.state_id = ... (requiere lógica de búsqueda avanzada)

            else:
                _logger.warning("Error consultando RUC: %s", response.text)

        except Exception as e:
            _logger.error("Fallo en conexión SUNAT: %s", str(e))