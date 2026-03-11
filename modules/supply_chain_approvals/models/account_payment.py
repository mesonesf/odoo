from odoo import models,fields

class AccountPayment(models.Model):
    _name = 'account.payment'
    _inherit = ['account.payment', 'approval.mixin']

    approver_ids = fields.Many2many('res.users', 'payment_approver_rel', string="Firmas Requeridas")
    approved_user_ids = fields.Many2many('res.users', 'payment_signed_rel', string="Firmas Recibidas")

    def action_post(self):
        if self.approval_status != 'approved':
            self.action_request_approval()
            if self.approval_status != 'approved':
                return False
        return super(AccountPayment, self).action_post()