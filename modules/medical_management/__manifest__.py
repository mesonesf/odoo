{
     'name': 'Medical Management',
     'version': '1.0.1',
     'category': 'Medical',
     'summary': 'Sistema de Gestión Médica Integral',
      'description': """
          Módulo completo para gestión de pacientes, fichas clínicas, evaluaciones, 
          tratamientos y programación de sesiones médicas.
      """,
     'author': 'Mejores Horizontes: Manuel Fernando Mesones Sanchez',
     'depends': ['base','hr','product','mail', 'account','calendar'],
     'data': [
         'data/sequences.xml',
         'security/ir.model.access.csv',
         'views/medical_specialty_views.xml',
         'views/medical_template_views.xml',
         'views/patient_views.xml',
         'views/clinical_record_views.xml',  
         'views/evaluation_views.xml',       
         'views/treatment_views.xml',
         'views/medical_menus.xml',
     ],
     'installable': True,
     'application': True,
     'auto_install': False,
     'license': 'LGPL-3',
 }
