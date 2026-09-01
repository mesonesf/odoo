import json
import logging
import requests
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.queue_job.exception import RetryableJobError
except ImportError:
    class RetryableJobError(Exception):
        pass

class SunatRucLine(models.Model):
    _name = 'sunat.ruc.line'
    _description = 'Línea de Resultado de SUNAT'

    batch_id = fields.Many2one('sunat.ruc.batch', string='Lote', ondelete='cascade', required=True)
    ruc = fields.Char(string='RUC', size=11, required=True)
    nombre_o_razon_social = fields.Char(string='Razón Social')
    estado = fields.Char(string='Estado')
    condicion = fields.Char(string='Condición')
    direccion_completa = fields.Char(string='Dirección Completa')
    tipo_contribuyente = fields.Char(string='Tipo de Contribuyente')
    fecha_inscripcion = fields.Date(string='Fecha de Inscripción')
    actividades_economicas = fields.Text(string='Actividades Económicas')
    
    status = fields.Selection([
        ('pending', 'Pendiente'),
        ('success', 'Exitoso'),
        ('failed', 'Fallido')
    ], string='Estado Consulta', default='pending', required=True)
    error_message = fields.Text(string='Mensaje de Error')

    def process_api(self):
        """Método principal para consumir la API. Este método debe ser ejecutado vía queue_job."""
        self.ensure_one()
        
        # En un escenario real, el token debería venir de res.config.settings o res.company
        # Aquí lo dejamos como placeholder o variable de entorno/configuración.
        # Para el propósito de este ejercicio, asumimos que se tiene el token.
        token = self.env['ir.config_parameter'].sudo().get_param('apiperu.dev.token', '49523193e61a980b7af0fa009d4e71cbf1b8e45b8ba58d481ba71d104bd1b6c1')
        
        url = "https://api.apiperu.dev/ruc-sunat"
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        payload = {
            "ruc": self.ruc
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
        except requests.exceptions.RequestException as e:
            self.error_message = f"Error de conexión: {str(e)}"
            raise RetryableJobError("Error de conexión, reintentando...", ignore_retry=False)

        if response.status_code == 200:
            res_json = response.json()
            if res_json.get('success'):
                data = res_json.get('data', {})
                self.write({
                    'status': 'success',
                    'nombre_o_razon_social': data.get('nombre_o_razon_social'),
                    'estado': data.get('estado'),
                    'condicion': data.get('condicion'),
                    'direccion_completa': data.get('direccion_completa') or data.get('direccion'),
                    'tipo_contribuyente': data.get('tipo_contribuyente'),
                    'fecha_inscripcion': data.get('fecha_inscripcion'),
                    'actividades_economicas': json.dumps(data.get('actividades_economicas', []), ensure_ascii=False),
                    'error_message': False
                })
            else:
                self.write({
                    'status': 'failed',
                    'error_message': res_json.get('message', 'Respuesta no exitosa')
                })
        elif response.status_code == 400:
            self.write({
                'status': 'failed',
                'error_message': 'El RUC es incorrecto'
            })
        elif response.status_code == 404:
            self.write({
                'status': 'failed',
                'error_message': 'El RUC no existe'
            })
        elif response.status_code == 503:
            self.error_message = 'Servicio no disponible, reintentando...'
            raise RetryableJobError("Servicio no disponible en apiperu.dev (503)", ignore_retry=False)
        else:
            self.write({
                'status': 'failed',
                'error_message': f'Error HTTP {response.status_code}: {response.text}'
            })
            
        # Verificar si el lote ya completó todas sus líneas
        self._check_batch_completion()

    def _check_batch_completion(self):
        batch = self.batch_id
        if not batch.line_ids.filtered(lambda l: l.status == 'pending'):
            if batch.line_ids.filtered(lambda l: l.status == 'failed'):
                batch.state = 'error'
            else:
                batch.state = 'completed'
