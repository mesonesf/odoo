from odoo import models, fields, api, _

class FinancialReportWizard(models.TransientModel):
    _name = 'financial.report.wizard'
    _description = 'Asistente de Reportes Financieros'

    date_from = fields.Date(string='Fecha Inicio', required=True)
    date_to = fields.Date(string='Fecha Fin', required=True, default=fields.Date.context_today)
    
    # 1. Agregamos las nuevas opciones al menú
    report_type = fields.Selection([
        ('balance', 'Estado de Situación Financiera (NIIF)'),
        ('pyl', 'Estado de Resultados (Naturaleza)'),
        ('patrimonio', 'Estado de Cambios en el Patrimonio'),
        ('flujo', 'Estado de Flujos de Efectivo'),      # <--- NUEVO
        ('notas', 'Notas a los Estados Financieros'),   # <--- NUEVO
        ('diario', 'Libro Diario'),                     # <--- NUEVO
        ('mayor', 'Libro Mayor')                        # <--- NUEVO
    ], string='Tipo de Reporte', required=True, default='balance')

    # 2. Creamos el campo para escribir las notas
    notas_text = fields.Html(string='Contenido de las Notas')

    def action_print_report(self):
        self.ensure_one()  # Seguridad: asegura que solo se procese un registro
        
        # Obtenemos los datos de forma serializable
        data = self.read(['date_from', 'date_to', 'report_type', 'notas_text'])[0]
        
        # Añadimos manualmente cualquier dato extra que necesitemos asegurar
        # En Odoo 18, es mejor pasar las fechas confirmadas como string
        data.update({
            'date_from': str(self.date_from),
            'date_to': str(self.date_to),
        })
        
        return self.env.ref('l10n_pe_financial_reports.action_report_financial').report_action(self, data=data)
