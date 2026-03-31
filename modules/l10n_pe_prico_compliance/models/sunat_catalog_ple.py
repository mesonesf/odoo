# -*- coding: utf-8 -*-
from odoo import models, fields, api

class L10nPeCatalog07(models.Model):
    _name = 'l10n_pe.catalog.07'
    _description = 'Catálogo 07: Afectación del IGV'
    
    code = fields.Char(string='Código', required=True)
    name = fields.Char(string='Descripción', required=True)
    active = fields.Boolean(default=True)

    # --- SINTAXIS ODOO 18 PARA MOSTRAR "CÓDIGO - NOMBRE" ---
    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            if rec.code and rec.name:
                rec.display_name = f"{rec.code} - {rec.name}"
            else:
                rec.display_name = rec.name or rec.code or 'Sin nombre'
    
class SunatCatalogPle(models.Model):
    _name = 'sunat.catalog.ple'
    _description = 'Catálogos exclusivos para PLE (Ej: Catálogo 8, Estados PLE)'
    
    code = fields.Char(string='Código', required=True)
    name = fields.Char(string='Descripción', required=True)
    catalog_type = fields.Selection([
        ('ple_state', 'Estado de Operación PLE'),
        ('book_code', 'Código de Libro (Catálogo 8)')
    ], string='Tipo de Catálogo')