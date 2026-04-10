from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_pe_document_type_id = fields.Many2one('l10n_pe.catalog.02', string='Tipo Doc. SUNAT')