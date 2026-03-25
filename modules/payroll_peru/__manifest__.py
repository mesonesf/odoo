# -*- coding: utf-8 -*-
{
    'name': 'Localización de Planillas Perú',
    'version': '18.0.1.0.0',
    'author': 'Mejores Horizontes',
    'category': 'Human Resources/Payroll',
    'summary': 'Adaptación de nómina para Perú (SUNAT/MTPE) sobre Odoo 18 Community.',
    'depends': [
        'hr',
        'hr_contract',
        'payroll',
        'payroll_account',
        'account'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/hr_pension_data.xml',
        'data/hr_quinta_escala_data.xml',
        'data/l10n_pe_payroll_data.xml',
        'data/salary_rules_ingresos.xml',
        'data/salary_rules_descuentos.xml',
        'views/hr_contract_views.xml',
        'views/hr_pension_views.xml',
        'views/res_config_settings_views.xml', # Nueva vista
        'views/report_payslip_templates.xml',
        'views/report_payslip_action.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}