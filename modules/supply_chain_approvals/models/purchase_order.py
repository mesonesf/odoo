from odoo import models,fields

class PurchaseOrder(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'approval.mixin']

    approver_ids = fields.Many2many('res.users', 'purchase_approver_rel', string="Firmas Requeridas")
    approved_user_ids = fields.Many2many('res.users', 'purchase_signed_rel', string="Firmas Recibidas")

    def button_confirm(self):
        # Interceptamos el botón confirmar
        if self.approval_status != 'approved':
            # Si no está aprobado, iniciamos el flujo
            self.action_request_approval()
            # Si tras la solicitud sigue sin estar aprobado (porque requiere firmas), paramos
            if self.approval_status != 'approved':
                return False
        return super(PurchaseOrder, self).button_confirm()