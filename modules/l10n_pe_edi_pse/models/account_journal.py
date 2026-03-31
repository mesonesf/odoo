from odoo import models, fields

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    l10n_pe_serie = fields.Char(string='Serie Electrónica SUNAT', size=4, help='Ejemplo: F001, B001, FC01')