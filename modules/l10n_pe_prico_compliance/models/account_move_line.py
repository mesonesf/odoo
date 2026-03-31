from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_pe_edi_affectation_reason = fields.Many2one(
        'l10n_pe.catalog.07',
        string="Afectación IGV",
        compute='_compute_l10n_pe_edi_affectation',
        store=True,
        readonly=False,
        help="Se calcula desde el impuesto, pero puede modificarse para excepciones (ej. Retiros por premio)."
    )

    @api.depends('tax_ids')
    def _compute_l10n_pe_edi_affectation(self):
        for line in self:
            # Si hay impuestos, tomamos el catálogo del primer impuesto aplicable
            if line.tax_ids:
                tax = line.tax_ids[0]
                if tax.l10n_pe_edi_affectation_reason:
                    line.l10n_pe_edi_affectation_reason = tax.l10n_pe_edi_affectation_reason
            else:
                # Si se quitan los impuestos, limpiamos el campo
                line.l10n_pe_edi_affectation_reason = False