import base64
import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SunatRucBatch(models.Model):
    _name = 'sunat.ruc.batch'
    _description = 'Lote de Consulta SUNAT'
    _order = 'id desc'

    name = fields.Char(string='Secuencia', required=True, copy=False, readonly=True, default=lambda self: _('Nuevo'))
    txt_file = fields.Binary(string='Archivo TXT', required=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('processing', 'Procesando'),
        ('completed', 'Completado'),
        ('error', 'Error')
    ], string='Estado', default='draft', readonly=True, tracking=True)
    line_ids = fields.One2many('sunat.ruc.line', 'batch_id', string='Líneas de Resultado')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sunat.ruc.batch') or _('Nuevo')
        return super().create(vals_list)

    def action_confirm(self):
        self.ensure_one()
        if not self.txt_file:
            raise UserError(_('Debe cargar un archivo TXT.'))
        
        file_content = base64.b64decode(self.txt_file).decode('utf-8')
        rucs = set()
        
        for line in file_content.splitlines():
            ruc = line.strip()
            if re.fullmatch(r'\d{11}', ruc):
                rucs.add(ruc)
        
        if not rucs:
            raise UserError(_('El archivo no contiene RUCs válidos (11 dígitos numéricos).'))

        lines_to_create = []
        for ruc in rucs:
            lines_to_create.append({
                'batch_id': self.id,
                'ruc': ruc,
                'status': 'pending'
            })
            
        self.env['sunat.ruc.line'].create(lines_to_create)
        self.state = 'processing'
        self.action_process_queue()

    def action_process_queue(self):
        """Agrupa las líneas pendientes y las encola respetando 240 por minuto."""
        self.ensure_one()
        pending_lines = self.line_ids.filtered(lambda l: l.status == 'pending')
        
        # El límite de la API es 240 consultas por minuto -> 4 por segundo -> 1 cada 0.25s.
        # Para ser seguros, lo espaciaremos con datetime y timedelta
        from datetime import datetime, timedelta
        
        current_time = fields.Datetime.now()
        delay_seconds = 0.25  # 60s / 240 = 0.25s per request
        
        for i, line in enumerate(pending_lines):
            eta = current_time + timedelta(seconds=i * delay_seconds)
            line.with_delay(eta=eta, channel='root.sunat_api').process_api()

    def action_generate_excel(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/export/xlsx?model=sunat.ruc.line&domain=[("batch_id", "=", %s)]' % self.id,
            'target': 'new',
        }
