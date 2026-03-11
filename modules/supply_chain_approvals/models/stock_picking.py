from odoo import models,fields

class StockPicking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'approval.mixin']
    
    approver_ids = fields.Many2many('res.users', 'stock_approver_rel', string="Firmas Requeridas")
    approved_user_ids = fields.Many2many('res.users', 'stock_signed_rel', string="Firmas Recibidas")

    def button_validate(self):
        if self.approval_status != 'approved':
            self.action_request_approval()
            if self.approval_status != 'approved':
                return False
        return super(StockPicking, self).button_validate()