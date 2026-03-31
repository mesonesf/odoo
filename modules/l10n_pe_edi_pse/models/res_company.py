from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_pse_url = fields.Char(string='URL del PSE')
    l10n_pe_pse_token = fields.Char(string='Token del PSE')
    l10n_pe_service_code = fields.Char(string='Cód. Emisor (PSE)', default="1", help="Código de cliente asignado por su PSE")