# -*- coding: utf-8 -*-
import base64
from odoo import models, fields, api

class PleDiarioWizard(models.TransientModel):
    _name = 'ple.diario.wizard'
    _description = 'Wizard para Libro Diario 5.1 y Mayor 6.1'

    # --- NUEVO: Campo para elegir el libro ---
    book_type = fields.Selection([
        ('050100', 'Libro Diario (5.1)'),
        ('060100', 'Libro Mayor (6.1)')
    ], string='Tipo de Libro', required=True, default='050100')

    date_from = fields.Date(string='Fecha Inicio', required=True)
    date_to = fields.Date(string='Fecha Fin', required=True)
    
    state = fields.Selection([('choose', 'Elegir'), ('get', 'Descargar')], default='choose')
    txt_filename = fields.Char(string='Nombre del Archivo')
    txt_binary = fields.Binary(string='Archivo TXT', readonly=True)

    def action_generate_ple_5_1(self):
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('move_id.state', '=', 'posted'),
            ('display_type', 'not in', ('line_section', 'line_note'))
        ]
        
        # 1. Buscamos todas las líneas sin ordenarlas en la base de datos
        lines = self.env['account.move.line'].search(domain)

        # 2. PRE-CÁLCULO DEL CORRELATIVO M000X
        # Esto asegura que la línea 1 de un asiento tenga "M0001" tanto en el Diario como en el Mayor,
        # sin importar cómo se mezclen después.
        correlativos_map = {}
        for move in lines.mapped('move_id'):
            move_lines = move.line_ids.filtered(lambda l: l.id in lines.ids).sorted(key=lambda x: x.id)
            for idx, line in enumerate(move_lines, 1):
                correlativos_map[line.id] = f"M{str(idx).zfill(4)}"

        # 3. ORDENAMIENTO INFALIBLE EN PYTHON
        if self.book_type == '050100':
            # Diario: Orden cronológico
            lines = lines.sorted(key=lambda l: (l.date, l.move_id.name or '', l.id))
        else:
            # Mayor: Ordenado estrictamente por Código de Cuenta Contable
            lines = lines.sorted(key=lambda l: (l.account_id.code or '', l.date, l.move_id.name or '', l.id))

        ple_content = ""
        has_data = bool(lines)

        for line in lines:
            move = line.move_id
            
            # Llamamos al correlativo pre-calculado para esta línea exacta
            correlativo_asiento = correlativos_map.get(line.id, "M0001")

            periodo = self.date_from.strftime('%Y%m00')
            cuo = move.l10n_pe_cuo or f"{periodo}-ERROR-{move.id}"
            cuenta_pcge = line.account_id.code or '000000'
            
            moneda = line.currency_id.name or 'PEN'
            tipo_cambio = "1.000" if moneda == 'PEN' else "{:.3f}".format(move.invoice_currency_rate or 1.0)

            partner = line.partner_id
            tipo_doc_partner = getattr(partner.l10n_latam_identification_type_id, 'l10n_pe_vat_code', '6' if len(partner.vat or '') == 11 else '1') if partner else '0'
            num_doc_partner = partner.vat if partner and partner.vat else '0'

            tipo_comprobante = move.l10n_latam_document_type_id.code if move.l10n_latam_document_type_id else '00'
            
            serie = ""
            numero = ""
            if move.name and '-' in move.name:
                parts = move.name.split('-')
                serie = parts[0][-4:]
                numero = parts[1]
            else:
                serie = '0000'
                numero = move.name or '0'

            glosa = (line.name or move.name or 'Asiento Contable').replace('|', '')

            row = [
                periodo, cuo, correlativo_asiento, cuenta_pcge, '', '', moneda, 
                tipo_doc_partner, num_doc_partner, tipo_comprobante, serie, numero, 
                line.date.strftime('%d/%m/%Y'), 
                move.invoice_date.strftime('%d/%m/%Y') if move.invoice_date else line.date.strftime('%d/%m/%Y'), 
                line.date.strftime('%d/%m/%Y'), glosa[:200], '', 
                self.env['ple.report.base']._format_amount(line.debit), 
                self.env['ple.report.base']._format_amount(line.credit), 
                '', '1'
            ]
            
            ple_content += "|".join(row) + "|\r\n"

        period_str = self.date_from.strftime('%Y%m')
        filename = self.env['ple.report.base']._get_ple_filename(self.env.company, period_str, self.book_type, has_data)

        self.write({
            'txt_filename': filename,
            'txt_binary': base64.b64encode(ple_content.encode('utf-8')),
            'state': 'get'
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ple.diario.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }