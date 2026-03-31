# -*- coding: utf-8 -*-
{
    'name': 'Localización Perú: Facturación Electrónica PSE',
    'version': '1.0',
    'category': 'Accounting/Localizations/EDI',
    'author': 'Mejores Horizontes: Manuel Fernando Mesones Sanchez',
    'summary': 'Módulo base para facturación electrónica y libros electrónicos (SIRE/PLE)',
    'depends': [
        'account',
        'fleet',
        'base',
        'l10n_pe', # Dependencia nativa de Perú recomendada
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_journal_views.xml',
        'views/account_move_views.xml',
        'views/payload_debug_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}