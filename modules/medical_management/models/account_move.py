from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    payment_journal_names = fields.Char(
        string='Diario de Pago', 
        compute='_compute_payment_details'
    )

    @api.depends('payment_state', 'line_ids.matched_credit_ids', 'line_ids.matched_debit_ids')
    def _compute_payment_details(self):
        for move in self:
            # Buscamos las líneas de pago que se han conciliado con esta factura
            partials = move.line_ids.matched_credit_ids | move.line_ids.matched_debit_ids
            
            # Obtenemos los asientos de esos pagos
            payment_moves = (partials.credit_move_id.move_id | partials.debit_move_id.move_id) - move
            
            if payment_moves:
                # Extraemos los nombres de los diarios y usamos 'set' para evitar duplicados
                journals = list(set(payment_moves.mapped('journal_id.name')))
                move.payment_journal_names = ", ".join(journals)
            else:
                move.payment_journal_names = ""