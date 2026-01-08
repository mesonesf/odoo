from odoo import models, fields, api, _

class FinancialReportWizard(models.TransientModel):
    _name = 'financial.report.wizard'
    _description = 'Asistente de Reportes Financieros'

    date_from = fields.Date(string='Fecha Inicio', required=True)
    date_to = fields.Date(string='Fecha Fin', required=True, default=fields.Date.context_today)
    report_type = fields.Selection([
        ('balance', 'Estado de Situación Financiera (NIIF)'),
        ('pyl', 'Estado de Resultados (Naturaleza)'),
        ('patrimonio', 'Estado de Cambios en el Patrimonio')  # <--- NUEVA OPCIÓN
    ], string='Tipo de Reporte', required=True, default='balance')

    def action_print_report(self):
        data = {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'report_type': self.report_type,
        }
        return self.env.ref('l10n_pe_financial_reports.action_report_financial').report_action(self, data=data)