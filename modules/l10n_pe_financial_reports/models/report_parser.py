from odoo import models, api

class FinancialReportParser(models.AbstractModel):
    _name = 'report.l10n_pe_financial_reports.report_template_view'
    _description = 'Parser Financiero bajo NIIF'

    @api.model
    def _get_report_values(self, docids, data=None):
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        report_type = data.get('report_type')

        move_lines = self.env['account.move.line'].search([
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('parent_state', '=', 'posted')
        ])

        # Consolidación de saldos
        accounts = {}
        for line in move_lines:
            acc = line.account_id
            if acc.id not in accounts:
                accounts[acc.id] = {'code': acc.code, 'name': acc.name, 'balance': 0.0}
            accounts[acc.id]['balance'] += (line.debit - line.credit)

        res = list(accounts.values())
        vals = {'data': data}

        if report_type == 'balance':
            # Clasificación NIIF (Activo Corriente/No Corriente, etc.)
            vals.update({
                'act_corriente': [a for a in res if a['code'][:2] in ['10','11','12','13','14','16','18','20','21']],
                'act_no_corriente': [a for a in res if a['code'][:2] in ['30','31','32','33','34','35','39']],
                'pas_corriente': [a for a in res if a['code'][:2] in ['40','41','42','43','44','45','46','48']],
                'pas_no_corriente': [a for a in res if a['code'][:2] in ['47','49']],
                'patrimonio': [a for a in res if a['code'].startswith('5')],
            })
            # Cálculos de Totales
            vals['total_act_c'] = sum(x['balance'] for x in vals['act_corriente'])
            vals['total_act_nc'] = sum(x['balance'] for x in vals['act_no_corriente'])
            vals['total_activo'] = vals['total_act_c'] + vals['total_act_nc']
            
            # Invertir signo para pasivos/patrimonio
            vals['total_pas_c'] = sum(-x['balance'] for x in vals['pas_corriente'])
            vals['total_pas_nc'] = sum(-x['balance'] for x in vals['pas_no_corriente'])
            vals['total_pat'] = sum(-x['balance'] for x in vals['patrimonio'])
            vals['total_pas_pat'] = vals['total_pas_c'] + vals['total_pas_nc'] + vals['total_pat']

        elif report_type == 'pyl':
            # Estado de Resultados por Función (NIIF)
            vals.update({
                'ventas': sum(-a['balance'] for a in res if a['code'].startswith('70')),
                'costo_ventas': sum(a['balance'] for a in res if a['code'].startswith('69')),
                'gastos_adm': sum(a['balance'] for a in res if a['code'].startswith('94')),
                'gastos_ventas': sum(a['balance'] for a in res if a['code'].startswith('95')),
                'otros_ingresos': sum(-a['balance'] for a in res if a['code'].startswith(('75','77'))),
                'otros_gastos': sum(a['balance'] for a in res if a['code'].startswith(('65','67'))),
            })
            vals['utilidad_bruta'] = vals['ventas'] - vals['costo_ventas']
            vals['utilidad_operativa'] = vals['utilidad_bruta'] - vals['gastos_adm'] - vals['gastos_ventas']
            vals['utilidad_neta'] = vals['utilidad_operativa'] + vals['otros_ingresos'] - vals['otros_gastos']

        return vals