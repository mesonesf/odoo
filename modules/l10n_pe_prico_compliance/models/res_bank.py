# -*- coding: utf-8 -*-
from odoo import models, fields

class ResBank(models.Model):
    _inherit = 'res.bank'

    l10n_pe_edi_bank_code = fields.Char(
        string='Código SUNAT (Cat. 03)',
        help='Código de 2 dígitos asignado por SUNAT. Ej: 02 (BCP), 11 (BBVA), 03 (Interbank), 09 (Scotiabank).'
    )