{
    'name': 'Reportes Financieros Perú (Community)',
    'version': '1.0',
    'category': 'Accounting',
    'license': 'LGPL-3', 
    'summary': 'Balance, Ganancias y Pérdidas, y Patrimonio para Perú',
    'author': 'Mejores Horizontes',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/financial_report_wizard_view.xml',
        'report/financial_reports_definition.xml',
        'report/report_templates.xml',
    ],
    'installable': True,
    'application': False,
}