from odoo import models, fields, api
from odoo.exceptions import UserError

class PurchaseOrder(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'approval.mixin']

    approver_ids = fields.Many2many('res.users', relation='po_approvers_rel')
    approved_user_ids = fields.Many2many('res.users', relation='po_approved_rel')

    # Vacuna Owl
    on_time_rate_perc = fields.Float(string="Tasa de entrega (Ghost)", compute="_compute_ghost_on_time")
    def _compute_ghost_on_time(self):
        for record in self:
            record.on_time_rate_perc = 0.0

    # ==========================================
    # FASE 2: PRE-FILTRO Y GRUPOS DE SEGURIDAD
    # ==========================================
    # ==========================================
    # FASE 2: PRE-FILTRO DE SELECCIÓN DE GANADORA
    # ==========================================
    is_winning_quote = fields.Boolean(string="Cotización Ganadora", copy=False, default=False)
    selector_id = fields.Many2one('res.users', string="Seleccionada por", copy=False)
    
    is_user_selector = fields.Boolean(compute='_compute_user_permissions')
    is_user_confirmer = fields.Boolean(compute='_compute_user_permissions')
    is_current_user_the_selector = fields.Boolean(compute='_compute_is_current_user_the_selector')
    
    # Quitamos el @api.depends para obligar a Odoo a recalcular esto más seguido
    requisition_has_winner = fields.Boolean(compute='_compute_requisition_has_winner')

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
            # EL BLINDAJE: Consulta en vivo a la BD, a prueba de cachés desactualizadas.
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

    # ==========================================
    # MOTOR DE APROBACIÓN
    # ==========================================
    def button_confirm(self):
        for record in self:
            if not record.is_winning_quote:
                raise UserError("Solo se puede confirmar la cotización declarada como ganadora.")

            # Si está 100% aprobada, verificamos si el usuario tiene el Check para Emitir la Orden
            if record.approval_status == 'approved':
                if not self.env.user.has_group('supply_chain_approvals.group_supply_chain_po_confirmers'):
                    raise UserError("No tienes el permiso de sistema para emitir Órdenes de Compra finales.")

            if record.approval_status == 'draft':
                record.action_request_approval()
                
            if record.approval_status != 'approved':
                return False
                
        return super(PurchaseOrder, self).button_confirm()