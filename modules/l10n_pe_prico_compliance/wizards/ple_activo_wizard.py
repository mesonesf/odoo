# -*- coding: utf-8 -*-
import base64
from odoo import models, fields, api

class PleActivoWizard(models.TransientModel):
    _name = 'ple.activo.wizard'
    _description = 'Wizard para PLE 7.1 - Registro de Activos Fijos'

    date_from = fields.Date(string='Fecha Inicio (Ejercicio)', required=True)
    date_to = fields.Date(string='Fecha Fin (Ejercicio)', required=True)
    
    state = fields.Selection([('choose', 'Elegir'), ('get', 'Descargar')], default='choose')
    txt_filename = fields.Char(string='Nombre del Archivo')
    txt_binary = fields.Binary(string='Archivo TXT', readonly=True)

    def action_generate_ple_7_1(self):
        # Para el 7.1, se evalúan los activos que no estén en estado borrador
        assets = self.env['account.asset.peru.v3'].search([('state', '!=', 'draft')])
        
        ple_content = ""
        has_data = bool(assets)
        
        # El 7.1 suele reportarse al cierre (Ej: 20261200) o en el mes de la consulta
        periodo = self.date_to.strftime('%Y%m00')

        for idx, asset in enumerate(assets, 1):
            correlativo = f"M{str(idx).zfill(4)}"
            
            # CUO de alta: Si el activo viene de una factura, jalamos el CUO de tu facturación
            cuo_alta = f"ACTIVO-{asset.id}" # Fallback
            if asset.invoice_line_id and asset.invoice_line_id.move_id:
                cuo_alta = asset.invoice_line_id.move_id.l10n_pe_cuo or cuo_alta

            fecha_adq = asset.purchase_date.strftime('%d/%m/%Y') if asset.purchase_date else ''
            valor_adq = asset.purchase_value or 0.0

            # --- LA MATEMÁTICA QUE EXIGE SUNAT ---
            # 1. Depreciación Histórica (Antes de Date From)
            lineas_historicas = asset.depreciation_line_ids.filtered(
                lambda l: l.depreciation_date < self.date_from and l.is_posted
            )
            dep_acum_historica = sum(lineas_historicas.mapped('amount'))

            # 2. Depreciación del Ejercicio (Dentro del rango)
            lineas_ejercicio = asset.depreciation_line_ids.filtered(
                lambda l: self.date_from <= l.depreciation_date <= self.date_to and l.is_posted
            )
            dep_ejercicio = sum(lineas_ejercicio.mapped('amount'))

            # 3. Total Acumulado al cierre
            dep_total = dep_acum_historica + dep_ejercicio

            # Estructura oficial PLE 7.1 (29 columnas principales en la Versión 5.2)
            row = [
                periodo,                                        # 1: Periodo (YYYYMM00)
                cuo_alta,                                       # 2: CUO del alta del activo
                correlativo,                                    # 3: Correlativo
                '9',                                            # 4: Código de catálogo (9 = Otros)
                (asset.name or 'ACTIVO')[:40].replace('|', ''), # 5: Código propio del Activo
                '',                                             # 6: Cod. Catálogo SUNAT
                '',                                             # 7: Cod. Activo SUNAT
                fecha_adq,                                      # 8: Fecha de Adquisición
                fecha_adq,                                      # 9: Fecha de inicio de uso
                '1',                                            # 10: Método de Depreciación (1 = Línea Recta)
                '',                                             # 11: N° Documento autorización (vacío)
                '0.00',                                         # 12: Porcentaje de Depreciación (Se puede mapear luego)
                self.env['ple.report.base']._format_amount(dep_acum_historica), # 13: Depreciación acumulada anterior
                self.env['ple.report.base']._format_amount(valor_adq),          # 14: Valor de Adquisición / Histórico
                '0.00',                                         # 15: Ajuste por inflación
                '0.00',                                         # 16: Mejoras
                '0.00',                                         # 17: Retiros o Bajas
                '0.00',                                         # 18: Otros ajustes
                self.env['ple.report.base']._format_amount(valor_adq),          # 19: Valor del activo al cierre
                self.env['ple.report.base']._format_amount(dep_acum_historica), # 20: Dep. acumulada sin inflación
                '0.00',                                         # 21: Ajuste por inflación (Depreciación)
                self.env['ple.report.base']._format_amount(dep_ejercicio),      # 22: Depreciación del ejercicio
                '0.00',                                         # 23: Retiros (Depreciación)
                '0.00',                                         # 24: Otros ajustes (Depreciación)
                self.env['ple.report.base']._format_amount(dep_total),          # 25: Depreciación total al cierre
                '',                                             # 26: Dato estructurado (Vacío)
                '',                                             # 27: Cuenta Contable del Activo (Vacío)
                '',                                             # 28: Cuenta Contable de Depreciación (Vacío)
                '1'                                             # 29: Estado de Operación (1 = Registrado en el mes)
            ]
            
            ple_content += "|".join(row) + "|\r\n"

        # Nombre oficial del Libro 7.1: 070100
        period_str = self.date_to.strftime('%Y%m')
        filename = self.env['ple.report.base']._get_ple_filename(self.env.company, period_str, '070100', has_data)

        self.write({
            'txt_filename': filename,
            'txt_binary': base64.b64encode(ple_content.encode('utf-8')),
            'state': 'get'
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ple.activo.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }