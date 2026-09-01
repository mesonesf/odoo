{
    'name': 'Consulta SUNAT',
    'version': '18.0.1.0.0',
    'category': 'Tools',
    'summary': 'Validación masiva de RUCs ante la SUNAT',
    'description': """
Módulo para validar RUCs masivamente consumiendo la API de apiperu.dev.
    """,
    'depends': ['base', 'queue_job'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/queue_job_data.xml',
        'views/sunat_ruc_batch_views.xml',
        'views/sunat_ruc_menus.xml',
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
