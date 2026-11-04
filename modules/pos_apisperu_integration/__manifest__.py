# -*- coding: utf-8 -*-
{
    "name": "POS APIsPerú Integración",
    "version": '18.0.1.0.0',
    "author": 'Mejores Horizontes: Manuel Fernando Mesones Sanchez',
    "category": "Accounting/Localizations/EDIApiPeru",
    "summary": "Integración nativa del POS con APIsPerú para facturación electrónica ",
    "depends": ["point_of_sale", "account", "queue_job"],
    "data": [
        "views/account_move_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}