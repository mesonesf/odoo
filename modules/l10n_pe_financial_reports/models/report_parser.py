from odoo import models, api, _

class FinancialReportParser(models.AbstractModel):
    _name = 'report.l10n_pe_financial_reports.report_template_view'
    _description = 'Parser de Reportes Financieros con Cuadre NIIF'

    @api.model
    def _get_report_values(self, docids, data=None):
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        report_type = data.get('report_type')
        
        vals = {
            'data': data,
            'ventas': 0.0, 'otros_ingresos': 0.0, 'compras': 0.0, 
            'variacion_inv': 0.0, 'personal': 0.0, 'servicios': 0.0, 
            'tributos': 0.0, 'otros_gastos': 0.0, 'financieros': 0.0,
            'utilidad_neta': 0.0,
            'propiedad_planta_equipo': 0.0,
            'depreciacion_acumulada': 0.0,
            'act_no_corriente': [],
            'act_corriente': [],
            'pas_corriente': [],
            'pas_no_corriente': [],
            'patrimonio': [],
            'total_act_c': 0.0,
            'total_act_nc': 0.0,
            'total_activo': 0.0,
            'total_pas_c': 0.0,
            'total_pas_nc': 0.0,
            'total_pat': 0.0,
            'total_pas_pat': 0.0
        }

        # --- 1. CÁLCULO DE UTILIDAD (Para el balance y PyL) ---
        dominio_resultados = [
            ('date', '>=', date_from), 
            ('date', '<=', date_to), 
            ('parent_state', '=', 'posted')
        ]
        lineas_res = self.env['account.move.line'].search(dominio_resultados)
        
        ingresos = sum(-l.balance for l in lineas_res if l.account_id.code and l.account_id.code.startswith('7'))
        gastos = sum(l.balance for l in lineas_res if l.account_id.code and l.account_id.code.startswith('6'))
        utilidad_del_periodo = ingresos - gastos
        vals['utilidad_neta'] = utilidad_del_periodo

        # --- 2. SALDOS DE CUENTAS (Para Balance) ---
        accounts = self.env['account.account'].search([], order="code asc")
        res = []
        for acc in accounts:
            domain_b = [
                ('account_id', '=', acc.id), 
                ('date', '<=', date_to), 
                ('parent_state', '=', 'posted')
            ]
            # Usar search_read para mayor eficiencia en saldos
            lines_b = self.env['account.move.line'].search(domain_b)
            balance = sum(l.debit - l.credit for l in lines_b)
            if balance != 0:
                res.append({
                    'code': acc.code or '', 
                    'name': acc.name, 
                    'balance': balance
                })

        if report_type == 'balance':
            # Activo Corriente
            vals['act_corriente'] = [a for a in res if a['code'].startswith(('10','11','12','13','14','16','18','19','2'))]
            
            # Activo No Corriente (Lógica NIIF: Agrupar 33 y 39)
            ppe_list = [a for a in res if a['code'].startswith('33')]
            dep_list = [a for a in res if a['code'].startswith('39')]
            vals['propiedad_planta_equipo'] = sum(a['balance'] for a in ppe_list)
            vals['depreciacion_acumulada'] = sum(a['balance'] for a in dep_list)
            vals['act_no_corriente'] = [a for a in res if a['code'].startswith('3') and not a['code'].startswith(('33', '39'))]

            # Pasivo y Patrimonio
            vals['pas_corriente'] = [a for a in res if a['code'].startswith(('40','41','42','43','44','45','46','48'))]
            vals['pas_no_corriente'] = [a for a in res if a['code'].startswith(('47','49'))]
            vals['patrimonio'] = [a for a in res if a['code'].startswith('5')]

            # Totales
            vals['total_act_c'] = sum(a['balance'] for a in vals['act_corriente'])
            vals['total_act_nc'] = vals['propiedad_planta_equipo'] + vals['depreciacion_acumulada'] + sum(a['balance'] for a in vals['act_no_corriente'])
            vals['total_activo'] = vals['total_act_c'] + vals['total_act_nc']
            vals['total_pas_c'] = sum(-a['balance'] for a in vals['pas_corriente'])
            vals['total_pas_nc'] = sum(-a['balance'] for a in vals['pas_no_corriente'])
            vals['total_pat'] = sum(-a['balance'] for a in vals['patrimonio']) + utilidad_del_periodo
            vals['total_pas_pat'] = vals['total_pas_c'] + vals['total_pas_nc'] + vals['total_pat']

        elif report_type == 'pyl':
            vals['ventas'] = sum(-l.balance for l in lineas_res if l.account_id.code and l.account_id.code.startswith('70'))
            vals['otros_ingresos'] = sum(-l.balance for l in lineas_res if l.account_id.code and l.account_id.code.startswith(('75', '77')))
            vals['compras'] = sum(l.balance for l in lineas_res if l.account_id.code and l.account_id.code.startswith('60'))
            vals['variacion_inv'] = sum(l.balance for l in lineas_res if l.account_id.code and l.account_id.code.startswith('61'))
            vals['personal'] = sum(l.balance for l in lineas_res if l.account_id.code and l.account_id.code.startswith('62'))
            vals['servicios'] = sum(l.balance for l in lineas_res if l.account_id.code and l.account_id.code.startswith('63'))
            vals['tributos'] = sum(l.balance for l in lineas_res if l.account_id.code and l.account_id.code.startswith('64'))
            vals['otros_gastos'] = sum(l.balance for l in lineas_res if l.account_id.code and l.account_id.code.startswith('65'))
            vals['financieros'] = sum(l.balance for l in lineas_res if l.account_id.code and l.account_id.code.startswith('67'))
            
            vals['utilidad_operativa'] = (vals['ventas'] + vals['otros_ingresos']) - \
                                         (vals['compras'] + vals['variacion_inv'] + vals['personal'] + \
                                          vals['servicios'] + vals['tributos'] + vals['otros_gastos'])

        elif report_type == 'mayor':
            cuentas_mayor = []
            for acc in accounts:
                init_lines = self.env['account.move.line'].search([('account_id', '=', acc.id), ('date', '<', date_from), ('parent_state', '=', 'posted')])
                saldo_inicial = sum(l.debit - l.credit for l in init_lines)
                movs = self.env['account.move.line'].search([
                    ('account_id', '=', acc.id), ('date', '>=', date_from), ('date', '<=', date_to), ('parent_state', '=', 'posted')
                ], order='date asc')
                if movs or saldo_inicial != 0:
                    cuentas_mayor.append({
                        'code': acc.code or '', 
                        'name': acc.name, 
                        'inicial': saldo_inicial, 
                        'movimientos': movs, 
                        'final': saldo_inicial + sum(l.debit - l.credit for l in movs)
                    })
            vals['cuentas_mayor'] = cuentas_mayor

        elif report_type == 'flujo':
            lines_f = self.env['account.move.line'].search([
                ('account_id.code', '=like', '10%'), ('date', '>=', date_from), ('date', '<=', date_to), ('parent_state', '=', 'posted')
            ])
            vals['entradas'] = sum(l.debit for l in lines_f)
            vals['salidas'] = sum(l.credit for l in lines_f)
            vals['flujo_neto'] = vals['entradas'] - vals['salidas']

        elif report_type == 'diario':
            vals['asientos'] = self.env['account.move.line'].search([
                ('date', '>=', date_from), ('date', '<=', date_to), ('parent_state', '=', 'posted')
            ], order='date asc, move_id asc')

        elif report_type == 'notas':
            vals['notas_html'] = data.get('notas_text', 'Sin notas.')

        return vals