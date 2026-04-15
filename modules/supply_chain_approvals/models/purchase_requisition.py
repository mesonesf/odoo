from odoo import models, fields
from odoo.exceptions import UserError

class PurchaseRequisition(models.Model):
    _name = 'purchase.requisition'
    _inherit = ['purchase.requisition', 'approval.mixin']

    vendor_id = fields.Many2one('res.partner', string="Proveedor", required=False)

    approver_ids = fields.Many2many('res.users', relation='pr_approvers_rel')
    approved_user_ids = fields.Many2many('res.users', relation='pr_approved_rel')

    def action_request_approval(self):
        for record in self:
            if not record.line_ids:
                raise UserError("Debes agregar al menos un producto a la solicitud antes de enviarla a los jefes.")
            for line in record.line_ids:
                if line.price_unit <= 0.0:
                    raise UserError(f"Falta el precio referencial para el producto '{line.product_id.display_name}'. El equipo de Compras debe colocar un precio mayor a 0.00 antes de solicitar la primera firma.")
        return super(PurchaseRequisition, self).action_request_approval()

    def action_confirm(self):
        for record in self:
            if record.approval_status == 'draft':
                record.action_request_approval()
            if record.approval_status != 'approved':
                return False
        return super(PurchaseRequisition, self).action_confirm()

    # ==========================================
    # MANEJO DEL RECHAZO (Limpieza a Borrador)
    # ==========================================
    def action_reject(self, reason=False):
        if hasattr(super(PurchaseRequisition, self), 'action_reject'):
            res = super(PurchaseRequisition, self).action_reject(reason=reason)
        else:
            res = True
            
        for record in self:
            record.approval_status = 'draft'
            record.write({'state': 'draft'})
            record.message_post(body="❌ <b>Solicitud Rechazada por Jefatura</b><br/>El documento ha regresado a estado Borrador. Las celdas de precios y cantidades están desbloqueadas para corrección.")
            
        return res


class PurchaseRequisitionLine(models.Model):
    _inherit = 'purchase.requisition.line'

    is_user_quoter = fields.Boolean(compute='_compute_is_user_quoter')

    def _compute_is_user_quoter(self):
        for line in self:
            line.is_user_quoter = self.env.user.has_group('supply_chain_approvals.group_supply_chain_quoters')

    def write(self, vals):
        if 'price_unit' in vals or 'product_qty' in vals:
            for line in self:
                old_price = line.price_unit
                old_qty = line.product_qty
                
                new_price = vals.get('price_unit', old_price)
                new_qty = vals.get('product_qty', old_qty)
                
                cambios = []
                
                if 'price_unit' in vals and old_price != new_price:
                    cambios.append(f"<li><b>Precio:</b> {old_price} ➔ <b style='color: #d9534f;'>{new_price}</b></li>")
                    
                if 'product_qty' in vals and old_qty != new_qty:
                    cambios.append(f"<li><b>Cantidad:</b> {old_qty} ➔ <b style='color: #d9534f;'>{new_qty}</b></li>")
                
                if cambios:
                    mensaje = f"⚠️ <b>Auditoría de Modificación (Línea editada):</b><br/>" \
                              f"Producto: <i>{line.product_id.display_name}</i><br/>" \
                              f"<ul>{''.join(cambios)}</ul>"
                    
                    line.requisition_id.message_post(body=mensaje)
                    
        return super(PurchaseRequisitionLine, self).write(vals)