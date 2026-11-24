# -*- coding: utf-8 -*-
{
    "name": "CONAGRA Backend Theme - Interfaz Moderna ERP",
    "version": "18.0.1.1.0",
    "category": "Themes/Backend",
    "summary": "Tema corporativo CONAGRA: Sidebar lateral colapsable, paleta verde agroindustrial y diseño moderno SaaS para Odoo 18 CE",
    "description": """
CONAGRA Backend Theme - Interfaz Moderna ERP
============================================
Rediseño visual integral y desacoplado para Odoo 18 Community:
- Sidebar lateral fijo colapsable con buscador rápido de módulos.
- Paleta verde agroindustrial + superficies claras blanco/gris moderno.
- Barra superior limpia, tarjetas de formulario, tablas y kanban estilizados.
- Pantalla de inicio de sesión modernizada compatible con Website / eCommerce.
    """,
    "author": "CONAGRA / Mejores Horizontes",
    "website": "https://www.conagra.com.pe",
    "license": "LGPL-3",
    "depends": ["web"],
    "assets": {
        "web._assets_primary_variables": [
            ("prepend", "conagra_backend_theme/static/src/scss/primary_variables.scss"),
        ],
        "web.assets_backend": [
            "conagra_backend_theme/static/src/scss/sidebar.scss",
            "conagra_backend_theme/static/src/scss/backend_theme.scss",
            "conagra_backend_theme/static/src/views/form_status_indicator_patch.xml",
            "conagra_backend_theme/static/src/webclient/sidebar/conagra_sidebar.xml",
            "conagra_backend_theme/static/src/webclient/sidebar/conagra_sidebar.js",
            "conagra_backend_theme/static/src/webclient/webclient_patch.xml",
            "conagra_backend_theme/static/src/webclient/webclient_patch.js",
        ],
        "web.assets_frontend": [
            "conagra_backend_theme/static/src/scss/login.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
