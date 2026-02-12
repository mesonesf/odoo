from odoo import models, api

class FinancialReportParser(models.AbstractModel):
    _name = 'report.l10n_pe_financial_reports.report_template_view'
    _description = 'Parser Financiero Completo'

    @api.model
    def _get_report_values(self, docids, data=None):
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        report_type = data.get('report_type')

        # 1. Variables Base
        vals = {
            'data': data,
            'act_corriente': [], 'act_no_corriente': [], 
            'pas_corriente': [], 'pas_no_corriente': [], 'patrimonio': [],
            'total_act_c': 0.0, 'total_act_nc': 0.0, 'total_activo': 0.0,
            'total_pas_c': 0.0, 'total_pas_nc': 0.0, 'total_pat': 0.0, 'total_pas_pat': 0.0,
            'ventas': 0.0, 'otros_ingresos': 0.0, 
            'compras': 0.0, 'variacion_inv': 0.0, 
            'personal': 0.0, 'servicios': 0.0, 
            'tributos': 0.0, 'otros_gastos': 0.0, 
            'financieros': 0.0,
            'utilidad_operativa': 0.0, 'utilidad_neta': 0.0,
            # Nueva variable para el reporte de cambios
            'cambios_patrimonio': [] 
        }

        # 2. Lógica para BALANCE y PyL (Usa lógica de saldos acumulados al corte)
        if report_type in ['balance', 'pyl']:
            domain_balance = [('date', '<=', date_to), ('parent_state', '=', 'posted')]
            domain_pyl = [('date', '>=', date_from), ('date', '<=', date_to), ('parent_state', '=', 'posted')]
            
            domain = domain_balance if report_type == 'balance' else domain_pyl
            move_lines = self.env['account.move.line'].search(domain)

            accounts = {}
            for line in move_lines:
                acc = line.account_id
                if acc.id not in accounts:
                    accounts[acc.id] = {'code': acc.code, 'name': acc.name, 'balance': 0.0}
                accounts[acc.id]['balance'] += (line.debit - line.credit)
            
            res = list(accounts.values())

            if report_type == 'balance':
                #vals['act_corriente'] = [a for a in res if a['code'].startswith(('10','11','12','13','14','16','18','20','21'))]
                #vals['act_no_corriente'] = [a for a in res if a['code'].startswith(('3'))]
                #vals['pas_corriente'] = [a for a in res if a['code'].startswith(('40','41','42','43','44','45','46','48'))]
                #vals['pas_no_corriente'] = [a for a in res if a['code'].startswith(('47','49'))]
                #vals['patrimonio'] = [a for a in res if a['code'].startswith('5')]

                vals['act_corriente'] = [a for a in res if a['code'] and a['code'].startswith(('10','11','12','13','14','16','18','20','21'))]
                vals['act_no_corriente'] = [a for a in res if a['code'] and a['code'].startswith(('3'))]
                vals['pas_corriente'] = [a for a in res if a['code'] and a['code'].startswith(('40','41','42','43','44','45','46','48'))]
                vals['pas_no_corriente'] = [a for a in res if a['code'] and a['code'].startswith(('47','49'))]
                vals['patrimonio'] = [a for a in res if a['code'] and a['code'].startswith('5')]
                
                # Ajuste de Utilidad del ejercicio para cuadrar Balance
                #ing = sum(-a['balance'] for a in res if a['code'].startswith('7'))
                #gas = sum(a['balance'] for a in res if a['code'].startswith('6'))
                
                ing = sum(-a['balance'] for a in res if a['code'] and a['code'].startswith('7'))
                gas = sum(a['balance'] for a in res if a['code'] and a['code'].startswith('6'))
                util = ing - gas
                if util != 0:
                    vals['patrimonio'].append({'code': 'UTIL', 'name': 'RESULTADO DEL EJERCICIO', 'balance': -util})

                vals['total_act_c'] = sum(x['balance'] for x in vals['act_corriente'])
                vals['total_act_nc'] = sum(x['balance'] for x in vals['act_no_corriente'])
                vals['total_activo'] = vals['total_act_c'] + vals['total_act_nc']
                vals['total_pas_c'] = sum(-x['balance'] for x in vals['pas_corriente'])
                vals['total_pas_nc'] = sum(-x['balance'] for x in vals['pas_no_corriente'])
                vals['total_pat'] = sum(-x['balance'] for x in vals['patrimonio'])
                vals['total_pas_pat'] = vals['total_pas_c'] + vals['total_pas_nc'] + vals['total_pat']

            elif report_type == 'pyl':
                #vals['ventas'] = sum(-a['balance'] for a in res if a['code'].startswith('70'))
                #vals['otros_ingresos'] = sum(-a['balance'] for a in res if a['code'].startswith(('75','77')))
                #vals['compras'] = sum(a['balance'] for a in res if a['code'].startswith('60'))
                #vals['variacion_inv'] = sum(a['balance'] for a in res if a['code'].startswith('61'))
                #vals['personal'] = sum(a['balance'] for a in res if a['code'].startswith('62'))
                #vals['servicios'] = sum(a['balance'] for a in res if a['code'].startswith('63'))
                #vals['tributos'] = sum(a['balance'] for a in res if a['code'].startswith('64'))
                #vals['otros_gastos'] = sum(a['balance'] for a in res if a['code'].startswith('65'))
                #vals['financieros'] = sum(a['balance'] for a in res if a['code'].startswith('67'))


                vals['ventas'] = sum(-a['balance'] for a in res if a['code'] and a['code'].startswith('70'))
                vals['otros_ingresos'] = sum(-a['balance'] for a in res if a['code'] and a['code'].startswith(('75','77')))
                vals['compras'] = sum(a['balance'] for a in res if a['code'] and a['code'].startswith('60'))
                vals['variacion_inv'] = sum(a['balance'] for a in res if a['code'] and a['code'].startswith('61'))
                vals['personal'] = sum(a['balance'] for a in res if a['code'] and a['code'].startswith('62'))
                vals['servicios'] = sum(a['balance'] for a in res if a['code'] and a['code'].startswith('63'))
                vals['tributos'] = sum(a['balance'] for a in res if a['code'] and a['code'].startswith('64'))
                vals['otros_gastos'] = sum(a['balance'] for a in res if a['code'] and a['code'].startswith('65'))
                vals['financieros'] = sum(a['balance'] for a in res if a['code'] and a['code'].startswith('67'))
                vals['utilidad_operativa'] = (vals['ventas'] + vals['otros_ingresos']) - (vals['compras'] + vals['variacion_inv'] + vals['personal'] + vals['servicios'] + vals['tributos'] + vals['otros_gastos'])
                vals['utilidad_neta'] = vals['utilidad_operativa'] - vals['financieros']

        # 3. Lógica EXCLUSIVA para CAMBIOS EN EL PATRIMONIO
        elif report_type == 'patrimonio':
            # Buscamos cuentas de clase 5
            accounts_obj = self.env['account.account'].search([('code', 'like', '5%')])
            patrimonio_lines = []
            
            total_inicial = 0.0
            total_variacion = 0.0
            total_final = 0.0

            for acc in accounts_obj:
                # Saldo Inicial: Movimientos ANTES de date_from
                lines_init = self.env['account.move.line'].search([
                    ('account_id', '=', acc.id),
                    ('date', '<', date_from),
                    ('parent_state', '=', 'posted')
                ])
                # Saldo Periodo: Movimientos ENTRE fechas
                lines_period = self.env['account.move.line'].search([
                    ('account_id', '=', acc.id),
                    ('date', '>=', date_from),
                    ('date', '<=', date_to),
                    ('parent_state', '=', 'posted')
                ])

                # Nota: En patrimonio, SALDO ACREEDOR (Haber) es positivo para la presentación
                saldo_inicial = sum(l.credit - l.debit for l in lines_init)
                variacion = sum(l.credit - l.debit for l in lines_period)
                saldo_final = saldo_inicial + variacion

                if saldo_inicial != 0 or variacion != 0:
                    patrimonio_lines.append({
                        'code': acc.code,
                        'name': acc.name,
                        'inicial': saldo_inicial,
                        'variacion': variacion,
                        'final': saldo_final
                    })
                    total_inicial += saldo_inicial
                    total_variacion += variacion
                    total_final += saldo_final

            # Agregamos totales al final de la lista o los pasamos aparte
            vals['cambios_patrimonio'] = patrimonio_lines
            vals['total_pat_inicial'] = total_inicial
            vals['total_pat_variacion'] = total_variacion
            vals['total_pat_final'] = total_final

        return vals