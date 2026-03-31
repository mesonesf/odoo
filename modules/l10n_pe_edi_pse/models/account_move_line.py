from odoo import models, fields

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # Campo vital para el SIRE y el XML
    l10n_pe_edi_affectation_reason = fields.Many2one(
        'sunat.catalog.07', 
        string="Afectación IGV",
        help="Indica si la línea es Gravada, Exonerada o Inafecta"
    )