# -*- coding: utf-8 -*-
{
    'name': 'Medical WhatsApp Marketing',
    'version': '1.0.0',
    'category': 'Marketing',
    'summary': 'Módulo de Marketing para envío de WhatsApp (Texto e Imágenes) usando Meta Cloud API',
    'description': """
        Permite la selección manual de contactos/pacientes para enviar campañas 
        de mensajes de texto e imágenes a través de la API Oficial de Meta Cloud.
    """,
    'author': 'Mejores Horizontes: Manuel Fernando Mesones Sanchez',
    'depends': ['base', 'mail', 'medical_management'],
    'data': [
        'security/ir.model.access.csv',
        'views/whatsapp_message_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}