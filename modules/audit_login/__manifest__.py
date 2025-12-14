# audit_login/__manifest__.py
{
    'name': 'Auditoría de Logins',
    'version': '18.0.1.0.0',
    'summary': 'Registra IPs y Sistemas Operativos de usuarios al loguearse',
    'category': 'Tools',
    'author': 'Mejores Horizontes EIRL',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/audit_view.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}