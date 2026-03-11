from odoo import models,fields

class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'approval.mixin']

    approver_ids = fields.Many2many('res.users', 'account_approver_rel', string="Firmas Requeridas")
    approved_user_ids = fields.Many2many('res.users', 'account_signed_rel', string="Firmas Recibidas")

    def action_post(self):
        # Solo aplicamos lógica a Facturas de Proveedor (in_invoice) o Cliente (out_invoice)
        if self.move_type in ('in_invoice', 'out_invoice', 'in_refund', 'out_refund'):
            if self.approval_status != 'approved':
                self.action_request_approval()
                if self.approval_status != 'approved':
                    return False
        return super(AccountMove, self).action_post()