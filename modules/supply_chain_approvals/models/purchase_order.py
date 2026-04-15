from odoo import models, fields, api
from odoo.exceptions import UserError

class PurchaseOrder(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'approval.mixin']

    approver_ids = fields.Many2many('res.users', relation='po_approvers_rel')
    approved_user_ids = fields.Many2many('res.users', relation='po_approved_rel')

    on_time_rate_perc = fields.Float(string="Tasa de entrega (Ghost)", compute="_compute_ghost_on_time")
    def _compute_ghost_on_time(self):
        for record in self:
            record.on_time_rate_perc = 0.0

    is_winning_quote = fields.Boolean(string="Cotización Ganadora", copy=False, default=False)
    selector_id = fields.Many2one('res.users', string="Seleccionada por", copy=False)
    
    is_user_selector = fields.Boolean(compute='_compute_user_permissions')
    is_user_confirmer = fields.Boolean(compute='_compute_user_permissions')
    is_current_user_the_selector = fields.Boolean(compute='_compute_is_current_user_the_selector')
    requisition_has_winner = fields.Boolean(compute='_compute_requisition_has_winner')

    # ==========================================
    # ESTADOS DE GANADORA / PERDIDA
    # ==========================================
    quote_result_status = fields.Char(string="Resultado", compute="_compute_quote_result_status")
    
    @api.depends('is_winning_quote', 'requisition_has_winner')
    def _compute_quote_result_status(self):
        for record in self:
            if record.is_winning_quote:
                record.quote_result_status = '🏆 Ganadora'
            elif record.requisition_has_winner:
                record.quote_result_status = '❌ Perdida'
            else:
                record.quote_result_status = '⏳ En Evaluación'

    def _compute_user_permissions(self):
        for record in self:
            record.is_user_selector = self.env.user.has_group('supply_chain_approvals.group_supply_chain_selectors')
            record.is_user_confirmer = self.env.user.has_group('supply_chain_approvals.group_supply_chain_po_confirmers')

    def _compute_is_current_user_the_selector(self):
        for record in self:
            record.is_current_user_the_selector = (record.selector_id == self.env.user)

    def _compute_requisition_has_winner(self):
        for record in self:
            if record.requisition_id:
                winner = self.env['purchase.order'].search([
                    ('requisition_id', '=', record.requisition_id.id),
                    ('is_winning_quote', '=', True),
                    ('id', '!=', record.id)
                ], limit=1)
                record.requisition_has_winner = bool(winner)
            else:
                record.requisition_has_winner = False

    def action_select_winner(self):
        for record in self:
            if record.requisition_id:
                live_winner = self.env['purchase.order'].search([
                    ('requisition_id', '=', record.requisition_id.id),
                    ('is_winning_quote', '=', True),
                    ('id', '!=', record.id)
                ], limit=1)
                
                if live_winner:
                    raise UserError(f"¡Alto! La cotización {live_winner.name} ya tiene la medalla de ganadora para este requerimiento. Si deseas elegir esta, primero debes quitarle la medalla a la otra.")
                    
            record.is_winning_quote = True
            record.selector_id = self.env.user.id

    def action_undo_winner(self):
        for record in self:
            if record.selector_id != self.env.user:
                raise UserError("Solo quien marcó esta cotización puede quitarle la medalla.")
            record.is_winning_quote = False
            record.selector_id = False

    def button_confirm(self):
        for record in self:
            if not record.is_winning_quote:
                raise UserError("Solo se puede confirmar la cotización declarada como ganadora.")
            if record.approval_status == 'approved':
                if not self.env.user.has_group('supply_chain_approvals.group_supply_chain_po_confirmers'):
                    raise UserError("No tienes el permiso de sistema para emitir Órdenes de Compra finales.")
            if record.approval_status == 'draft':
                record.action_request_approval()
            if record.approval_status != 'approved':
                return False
        return super(PurchaseOrder, self).button_confirm()

    # ==========================================
    # MANEJO DEL RECHAZO FASE 2
    # ==========================================
    def action_reject(self, reason=False):
        if hasattr(super(PurchaseOrder, self), 'action_reject'):
            res = super(PurchaseOrder, self).action_reject(reason=reason)
        else:
            res = True
            
        for record in self:
            record.approval_status = 'draft'
            record.write({'state': 'draft'})
            # Si la rechazan, le quitamos la medalla
            record.is_winning_quote = False 
            record.selector_id = False
            record.message_post(body="❌ <b>Cotización Rechazada</b><br/>Regresada a Borrador y medalla retirada.")
        return res