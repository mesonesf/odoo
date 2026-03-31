# -*- coding: utf-8 -*-
import base64
import io
try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

from odoo import models, fields, api
from odoo.exceptions import UserError

class SireWizard(models.TransientModel):
    _name = 'sire.wizard'
    _description = 'Wizard para SIRE (Ventas RVIE y Compras RCE)'

    book_type = fields.Selection([
        ('140400', 'RVIE - Registro de Ventas (14.04)'),
        ('080400', 'RCE - Registro de Compras (08.04)')
    ], string='Tipo de Registro (SIRE)', required=True, default='140400')

    date_from = fields.Date(string='Fecha Inicio', required=True)
    date_to = fields.Date(string='Fecha Fin', required=True)
    
    state = fields.Selection([('choose', 'Elegir'), ('get', 'Descargar')], default='choose')
    
    # Campos TXT
    txt_filename = fields.Char(string='Nombre TXT')
    txt_binary = fields.Binary(string='Archivo TXT', readonly=True)
    
    # NUEVOS: Campos Excel
    xls_filename = fields.Char(string='Nombre Excel')
    xls_binary = fields.Binary(string='Archivo Excel', readonly=True)

    def action_generate_sire(self):
        if not xlsxwriter:
            raise UserError("La librería xlsxwriter no está instalada en el servidor de Odoo.")

        domain = [
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
            ('state', '=', 'posted')
        ]
        
        if self.book_type == '140400':
            domain.append(('move_type', 'in', ('out_invoice', 'out_refund')))
        else:
            domain.append(('move_type', 'in', ('in_invoice', 'in_refund')))

        moves = self.env['account.move'].search(domain, order='invoice_date ASC, name ASC')

        sire_content = ""
        has_data = bool(moves)
        periodo = self.date_from.strftime('%Y%m00')
        ruc_empresa = self.env.company.vat or '00000000000'

        # --- PREPARAR EXCEL EN MEMORIA ---
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Reporte SIRE')
        
        # Formatos Excel
        head_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
        cell_format = workbook.add_format({'border': 1})
        
        # Cabeceras amigables para el contador
        headers_rvie = ['RUC', 'Razón Social', 'Periodo', 'CAR', 'Fecha Emisión', 'Fecha Venc.', 'Tipo Doc', 'Serie', 'Número', 'Nro Final', 'Tipo Doc Cli', 'RUC/DNI', 'Nombre Cliente', 'Val. Exp.', 'Base Imponible', 'Dscto Base', 'IGV', 'Dscto IGV', 'Exonerado', 'Inafecto', 'ISC', 'Base IVAP', 'IVAP', 'ICBPER', 'Otros Trib.', 'Total', 'Moneda', 'TC', 'Fecha Mod.', 'Tipo Mod.', 'Serie Mod.', 'Nro Mod.', 'Id Proyecto', 'Estado']
        headers_rce = ['RUC', 'Razón Social', 'Periodo', 'CAR', 'Fecha Emisión', 'Fecha Venc.', 'Tipo Doc', 'Serie', 'Año DUA', 'Número', 'Nro Final', 'Tipo Doc Prov', 'RUC/DNI', 'Nombre Proveedor', 'Base Gravada 1', 'IGV 1', 'Base 2', 'IGV 2', 'Base 3', 'IGV 3', 'No Gravadas', 'ISC', 'ICBPER', 'Otros Trib.', 'Total', 'Moneda', 'TC', 'Fecha Mod.', 'Tipo Mod.', 'Serie Mod.', 'Nro Mod.', 'Constancia', 'Fecha Const.', 'Retención', 'Clasif.', 'Id Contrato', 'Err 1', 'Err 2', 'Estado']
        
        active_headers = headers_rvie if self.book_type == '140400' else headers_rce
        
        # Escribir cabeceras en la Fila 0
        for col, head in enumerate(active_headers):
            sheet.write(0, col, head, head_format)
            sheet.set_column(col, col, 15) # Ancho de columna por defecto

        row_xls = 1

        for move in moves:
            # Construcción del CAR
            tipo_doc = move.l10n_latam_document_type_id.code if move.l10n_latam_document_type_id else '00'
            serie = '0000'
            numero = '0'
            if move.name and '-' in move.name:
                parts = move.name.split('-')
                serie = parts[0][-4:]
                numero = parts[1]
            
            numero_car = str(numero).zfill(10)
            car_sunat = f"{ruc_empresa}{tipo_doc}{serie}{numero_car}"

            # Fechas y Partner
            fecha_emision = move.invoice_date.strftime('%d/%m/%Y') if move.invoice_date else ''
            fecha_vencimiento = move.invoice_date_due.strftime('%d/%m/%Y') if move.invoice_date_due else ''
            
            partner = move.partner_id
            tipo_doc_partner = getattr(partner.l10n_latam_identification_type_id, 'l10n_pe_vat_code', '6' if len(partner.vat or '') == 11 else '1') if partner else '0'
            num_doc_partner = partner.vat or '0'
            nombre_partner = (partner.name or 'CLIENTE/PROVEEDOR')[:100].replace('|', '')

            # Montos
            moneda = move.currency_id.name or 'PEN'
            tipo_cambio = "{:.3f}".format(move.invoice_currency_rate or 1.0)
            base_imponible = self.env['ple.report.base']._format_amount(abs(move.amount_untaxed))
            igv = self.env['ple.report.base']._format_amount(abs(move.amount_tax))
            total = self.env['ple.report.base']._format_amount(abs(move.amount_total))

            # Lógica Notas de Crédito
            fecha_ref = tipo_doc_ref = serie_ref = numero_ref = ''
            if tipo_doc in ['07', '08']:
                factura_original = move.reversed_entry_id or move.debit_origin_id
                if not factura_original and move.ref and '-' in move.ref:
                    factura_original = self.env['account.move'].search([('name', '=', move.ref), ('company_id', '=', move.company_id.id)], limit=1)

                if factura_original:
                    fecha_ref = factura_original.invoice_date.strftime('%d/%m/%Y') if factura_original.invoice_date else ''
                    tipo_doc_ref = factura_original.l10n_latam_document_type_id.code if factura_original.l10n_latam_document_type_id else '01'
                    if factura_original.name and '-' in factura_original.name:
                        parts_ref = factura_original.name.split('-')
                        serie_ref = parts_ref[0][-4:]
                        numero_ref = parts_ref[1]

            # Estructura según el libro
            if self.book_type == '140400':
                row = [
                    ruc_empresa, self.env.company.name.replace('|', ''), periodo, car_sunat, 
                    fecha_emision, fecha_vencimiento, tipo_doc, serie, numero, '', 
                    tipo_doc_partner, num_doc_partner, nombre_partner, '', 
                    base_imponible, '', igv, '', '', '', '', '', '', '', '', 
                    total, moneda, tipo_cambio, 
                    fecha_ref, tipo_doc_ref, serie_ref, numero_ref, '', '1'
                ]
            else:
                row = [
                    ruc_empresa, self.env.company.name.replace('|', ''), periodo, car_sunat, 
                    fecha_emision, fecha_vencimiento, tipo_doc, serie, '', numero, '', 
                    tipo_doc_partner, num_doc_partner, nombre_partner, 
                    base_imponible, igv, '', '', '', '', '', '', '', '', '', '', 
                    total, moneda, tipo_cambio, 
                    fecha_ref, tipo_doc_ref, serie_ref, numero_ref, '', '', '', '', '', '', '', '1'
                ]
            
            # 1. Escribir en el TXT
            sire_content += "|".join(row) + "|\r\n"
            
            # 2. Escribir en el Excel
            for col, val in enumerate(row):
                # Intentar convertir montos a números en Excel para que el contador pueda sumar
                try:
                    num_val = float(val) if '.' in str(val) else val
                    sheet.write(row_xls, col, num_val, cell_format)
                except ValueError:
                    sheet.write(row_xls, col, val, cell_format)
            
            row_xls += 1

        # Cerrar y procesar Excel
        workbook.close()
        xls_data = base64.b64encode(output.getvalue())

        period_str = self.date_from.strftime('%Y%m')
        filename = self.env['ple.report.base']._get_ple_filename(self.env.company, period_str, self.book_type, has_data)

        self.write({
            'txt_filename': filename,
            'txt_binary': base64.b64encode(sire_content.encode('utf-8')),
            'xls_filename': filename.replace('.txt', '.xlsx'),
            'xls_binary': xls_data,
            'state': 'get'
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sire.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }