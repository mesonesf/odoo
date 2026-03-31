from odoo import models, fields

class AccountTax(models.Model):
    _inherit = 'account.tax'

    l10n_pe_edi_affectation_reason = fields.Many2one(
        'l10n_pe.catalog.07',
        string="Afectación IGV (Cat. 07)",
        help="Este código se heredará automáticamente a las líneas de la factura para el XML y el SIRE."
    )