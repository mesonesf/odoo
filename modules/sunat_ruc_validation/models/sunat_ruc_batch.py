import io
import base64
import re
import xlsxwriter
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
        ruc_list = re.findall(r'\b\d{11}\b', file_content)
        rucs = set(ruc_list)
        
        if not rucs:
            raise UserError(_('El archivo no contiene RUCs válidos (11 dígitos numéricos).'))

        lines_to_create = [{'batch_id': self.id, 'ruc': ruc, 'status': 'pending'} for ruc in rucs]
            
        self.env['sunat.ruc.line'].create(lines_to_create)
        self.state = 'processing'
        self.action_process_queue()

    def action_process_queue(self):
        self.ensure_one()
        pending_lines = self.line_ids.filtered(lambda l: l.status == 'pending')
        
        from datetime import timedelta
        current_time = fields.Datetime.now()
        delay_seconds = 0.25
        
        for i, line in enumerate(pending_lines):
            eta = current_time + timedelta(seconds=i * delay_seconds)
            line.with_delay(eta=eta, channel='root.sunat_api').process_api()

    def action_force_complete(self):
        """Permite al usuario cerrar el lote manualmente si quedaron RUCs fallidos"""
        self.ensure_one()
        self.state = 'completed'

    def action_generate_excel(self):
        self.ensure_one()
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Resultados SUNAT')
        
        headers = ['RUC', 'Razón Social', 'Estado', 'Condición', 'Dirección', 'Tipo Contribuyente']
        bold = workbook.add_format({'bold': True})
        for col, text in enumerate(headers):
            sheet.write(0, col, text, bold)
            
        for row, line in enumerate(self.line_ids, start=1):
            sheet.write(row, 0, line.ruc or '')
            sheet.write(row, 1, line.nombre_o_razon_social or '')
            sheet.write(row, 2, line.estado or '')
            sheet.write(row, 3, line.condicion or '')
            sheet.write(row, 4, line.direccion_completa or '')
            sheet.write(row, 5, line.tipo_contribuyente or '')
            
        workbook.close()
        output.seek(0)
        
        attachment = self.env['ir.attachment'].create({
            'name': f'Consulta_RUC_{self.name}.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }