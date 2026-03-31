# -*- coding: utf-8 -*-
import base64
from odoo import models, fields, api

class PleCajaWizard(models.TransientModel):
    _name = 'ple.caja.wizard'
    _description = 'Wizard para PLE 1.1 (Caja) y 1.2 (Bancos)'

    book_type = fields.Selection([
        ('010100', 'Libro 1.1 - Detalle de Caja (Efectivo)'),
        ('010200', 'Libro 1.2 - Detalle de Bancos (Cta. Corriente)')
    ], string='Tipo de Libro', required=True, default='010100')

    date_from = fields.Date(string='Fecha Inicio', required=True)
    date_to = fields.Date(string='Fecha Fin', required=True)
    
    state = fields.Selection([('choose', 'Elegir'), ('get', 'Descargar')], default='choose')
    txt_filename = fields.Char(string='Nombre del Archivo')
    txt_binary = fields.Binary(string='Archivo TXT', readonly=True)

    def action_generate_ple_1(self):
        # Filtramos por tipo de diario según el libro seleccionado
        journal_type = 'cash' if self.book_type == '010100' else 'bank'
        
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('move_id.state', '=', 'posted'),
            ('journal_id.type', '=', journal_type),
            ('display_type', 'not in', ('line_section', 'line_note'))
        ]
        
        # Orden cronológico
        lines = self.env['account.move.line'].search(domain, order='date ASC, move_id ASC, id ASC')

        ple_content = ""
        has_data = bool(lines)
        line_correlatives = {}

        for line in lines:
            move = line.move_id
            
            if move.id not in line_correlatives:
                line_correlatives[move.id] = 1
            else:
                line_correlatives[move.id] += 1
                
            correlativo_asiento = f"M{str(line_correlatives[move.id]).zfill(4)}"

            periodo = self.date_from.strftime('%Y%m00')
            cuo = move.l10n_pe_cuo or f"{periodo}-ERROR-{move.id}"
            cuenta_pcge = line.account_id.code or '000000'
            moneda = line.currency_id.name or 'PEN'
            glosa = (line.name or move.name or 'Movimiento').replace('|', '')
            fecha_op = line.date.strftime('%d/%m/%Y')
            debe = self.env['ple.report.base']._format_amount(line.debit)
            haber = self.env['ple.report.base']._format_amount(line.credit)

            partner = line.partner_id
            tipo_doc_partner = getattr(partner.l10n_latam_identification_type_id, 'l10n_pe_vat_code', '6' if len(partner.vat or '') == 11 else '1') if partner else '0'
            num_doc_partner = partner.vat if partner and partner.vat else '0'
            nombre_partner = (partner.name or 'Varios')[:100].replace('|', '')

            # --- ESTRUCTURA 1.1 (CAJA - 19 Columnas) ---
            if self.book_type == '010100':
                row = [
                    periodo, cuo, correlativo_asiento, cuenta_pcge, 
                    '', '', moneda, 
                    '00',   # Tipo Comprobante (00=Otros para caja interna)
                    '0000', # Serie
                    move.name or '0', # Número
                    fecha_op, fecha_op, fecha_op, glosa[:200], '', 
                    debe, haber, '', '1'
                ]
            
            # --- ESTRUCTURA 1.2 (BANCOS - 18 Columnas) ---
            else:
                # Catálogos por defecto para evitar errores si no se llenaron en Odoo
                entidad_financiera = '99' # Fallback por si acaso
                if line.journal_id.bank_account_id and line.journal_id.bank_account_id.bank_id:
                    entidad_financiera = getattr(line.journal_id.bank_account_id.bank_id, 'l10n_pe_edi_code', '99') or '99'

                cta_bancaria = line.journal_id.bank_account_id.acc_number if line.journal_id.bank_account_id else 'S/N'
                medio_pago = '009' # 009 = Transferencia / Efectivo (Catálogo 1)

                row = [
                    periodo, cuo, correlativo_asiento, 
                    entidad_financiera, cta_bancaria, fecha_op, medio_pago, 
                    glosa[:200], tipo_doc_partner, num_doc_partner, nombre_partner, 
                    move.name or '0', # Nro Transacción bancaria
                    cuenta_pcge, '1', debe, haber, '', '1'
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
            'res_model': 'ple.caja.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }