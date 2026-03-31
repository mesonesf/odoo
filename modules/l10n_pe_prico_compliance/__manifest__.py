# -*- coding: utf-8 -*-
{
    'name': 'Compliance - PRICO (PLE y SIRE) Peru',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Generación de Libros Electrónicos (PLE) y SIRE para Principales Contribuyentes',
    'description': """
        Módulo orquestador para generar los archivos TXT y Excel exigidos por SUNAT para PRICOs.
        Integra y consolida datos de:
        - Planillas (payroll_peru)
        - Finanzas y Activos (l10n_pe_financial_reports)
        - Facturación Electrónica (l10n_pe_edi_pse)
    """,
    'author': 'Mejores Horizontes: Manuel Mesones',
    'depends': [
        'account',
        'payroll_peru',
        'l10n_pe_financial_reports',
        'l10n_pe_edi_pse',
    ],
    'data': [
        # Aquí iremos descomentando conforme agreguemos archivos
        'security/ir.model.access.csv',
        'data/sunat_catalog_07_data.xml',
        'views/account_tax_views.xml',
        'views/ple_diario_wizard_views.xml',
        'views/ple_activo_wizard_views.xml',
        'views/ple_caja_wizard_views.xml',
        'views/sire_wizard_views.xml',
        'views/sire_conciliation_wizard_views.xml',
        'views/menuitems.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}