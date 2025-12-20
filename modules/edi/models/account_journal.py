from odoo import models, fields

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    # Aquí es donde el usuario escribirá "F001", "B001", "FC01", etc.
    l10n_pe_serie = fields.Char(
        string="Serie Electrónica SUNAT", 
        size=4, 
        help="Ingrese la serie de 4 caracteres. Ej: F001, B001, FC01"
    )