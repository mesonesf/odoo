{
    'name': 'Extensión CRM y Ventas Perú',
    'version': '18.0.2.0.0',
    'category': 'Sales/CRM',
    'summary': 'Campos SUNAT, Listas Dinámicas CRM, Jerarquía Productos',
    'author': 'Mejores Horizontes',
    'depends': ['base', 'crm', 'sale_management', 'account'],
    'data': [
        'security/ir.model.access.csv', # IMPORTANTE para las nuevas tablas
        'views/crm_config_views.xml',   # Menús de configuración
        'views/res_partner_view.xml',
        'views/crm_lead_view.xml',
        'views/sale_order_view.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}