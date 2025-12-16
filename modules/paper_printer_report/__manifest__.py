{
    'name': 'Reportes de Impresión Personalizados',
    'version': '18.0.1.0.0',
    'category': 'Account',
    'summary': 'Añade una opción de impresión de factura en formato de ticket (72mm) con fuente grande.',
    'author': 'Tu Nombre',
    'depends': ['account'], # Dependencia obligatoria para acceder a las facturas
    'data': [
        'data/paper_format.xml',
        'data/report_ticket.xml', 
    ],
    'installable': True,
    'license': 'LGPL-3',
}