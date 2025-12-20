# -*- coding: utf-8 -*-
{
    'name': "Modulo de Facturacion Electronica",
    'version': '1.0',
    'summary': "Gestiona los Documentos Oficiales de la SUNAT",

    'description': """
    Permite emitir a través de un PSE Facturas, Boletas, Notas de Credito, Notas de Debito y Guias
    """,

    'author': "Mejores Horizontes eirl",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'EDI',
    'author': 'Mejores Horizontes: Manuel Fernando Mesones Sanchez',
    # any module necessary for this one to work correctly
    'depends': ['account','fleet','base'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/viewsNC.xml',
        'views/templates.xml',
        'views/payload_debug_views.xml',
        'views/stock_picking_views.xml',
        'views/viewsGuia.xml',
        'views/guia_debug_views.xml',
        'views/res_company_view.xml',
        'views/account_journal_view.xml'
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
