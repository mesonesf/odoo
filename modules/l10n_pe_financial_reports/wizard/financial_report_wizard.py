from odoo import models, fields, api

class FinancialReportWizard(models.TransientModel):
    _name = 'financial.report.wizard'
    _description = 'Filtro de Reportes Financieros'

    date_from = fields.Date(string='Fecha Inicio', required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='Fecha Fin', required=True, default=fields.Date.context_today)
    report_type = fields.Selection([
        ('balance', 'Balance General'),
        ('pyl', 'Estado de Ganancias y Pérdidas'),
        ('patrimonio', 'Estado de Cambios en el Patrimonio')
    ], string='Tipo de Reporte', required=True, default='balance')

    def action_print(self):
        data = {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'report_type': self.report_type
        }
        if self.report_type == 'balance':
            return self.env.ref('l10n_pe_financial_reports.action_report_balance').report_action(self, data=data)
        elif self.report_type == 'pyl':
            return self.env.ref('l10n_pe_financial_reports.action_report_pyl').report_action(self, data=data)
        else:
            return self.env.ref('l10n_pe_financial_reports.action_report_patrimonio').report_action(self, data=data)