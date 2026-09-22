# -*- coding: utf-8 -*-
{
    'name': 'Medical WhatsApp Gateway Marketing',
    'version': '18.0.1.0.0',
    'category': 'Marketing',
    'summary': 'Campañas de marketing masivo integradas con la pasarela WhatsApp y plantillas oficiales',
    'author': 'Tu Nombre / Empresa',
    'license': 'AGPL-3',
    'depends': ['mail_gateway_whatsapp', 'medical_management'],
    'data': [
        'security/ir.model.access.csv',
        'views/whatsapp_campaign_views.xml',
    ],
    'installable': True,
    'application': False,
}