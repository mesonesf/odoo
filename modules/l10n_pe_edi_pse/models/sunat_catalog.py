from odoo import models, fields

class L10nPeCatalog02(models.Model):
    _name = 'l10n_pe.catalog.02'
    _description = 'Catálogo SUNAT 02: Tipo de Documento de Identidad'
    
    code = fields.Char(string='Código', required=True)
    name = fields.Char(string='Descripción', required=True)
    active = fields.Boolean(default=True)

    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, f"{rec.code} - {rec.name}"))
        return result

class L10nPeCatalog10(models.Model):
    _name = 'l10n_pe.catalog.10'
    _description = 'Catálogo SUNAT 10: Tipo de Comprobante de Pago'
    
    code = fields.Char(string='Código', required=True)
    name = fields.Char(string='Descripción', required=True)
    active = fields.Boolean(default=True)

    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, f"{rec.code} - {rec.name}"))
        return result