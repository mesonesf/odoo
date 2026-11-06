# -*- coding: utf-8 -*-
{
    "name": "CONAGRA ERP - Suite Integral Agroindustrial",
    "version": "18.0.2.1.0",
    "category": "Industries/Agriculture",
    "summary": "Solución integral para CONAGRA con Tablas Maestras Parametrizables",
    "description": """
CONAGRA ERP - Suite Integral Agroindustrial
===========================================
Módulo unificado que implementa los 8 pilares funcionales de CONAGRA con **Tablas Maestras Parametrizables**
integrado nativamente con los módulos base del sistema CONAGRA y `mail_gateway` / `mail_gateway_whatsapp`.
    """,
    "author": "CONAGRA / Mejores Horizontes",
    "website": "https://www.conagra.com.pe",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "crm",
        "sale_management",
        "account",
        "purchase",
        "stock",
        "stock_landed_costs",
        "mrp",
        "product_expiry",
        "fleet",
        "hr",
        "hr_attendance",
        "mail_gateway",
        "mail_gateway_whatsapp",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/conagra_master_data.xml",
        "data/ir_cron_conagra.xml",
        "report/stock_picking_box_sticker_report.xml",
        "views/conagra_master_tables_views.xml",
        "views/res_config_settings_views.xml",
        "views/crm_whatsapp_views.xml",
        "views/partner_credit_commission_views.xml",
        "views/mrp_landed_cost_product_views.xml",
        "views/stock_fleet_gps_hr_views.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
