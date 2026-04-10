from odoo import models, fields
from odoo.exceptions import UserError  # <-- Importante: Importamos el motor de alertas de Odoo

class PurchaseRequisition(models.Model):
    _name = 'purchase.requisition'
    _inherit = ['purchase.requisition', 'approval.mixin']

    # MAGIA: Le decimos a Odoo que el proveedor es opcional en la Fase 1
    vendor_id = fields.Many2one('res.partner', string="Proveedor", required=False)

    approver_ids = fields.Many2many('res.users', relation='pr_approvers_rel')
    approved_user_ids = fields.Many2many('res.users', relation='pr_approved_rel')

    # ==========================================
    # EL GUARDIA: VALIDACIÓN ANTES DE INICIAR RUTA
    # ==========================================
    def action_request_approval(self):
        for record in self:
            # 1. Validar que la solicitud no esté vacía
            if not record.line_ids:
                raise UserError("Debes agregar al menos un producto a la solicitud antes de enviarla a los jefes.")
            
            # 2. Validar que todos los productos tengan precio referencial
            for line in record.line_ids:
                if line.price_unit <= 0.0:
                    raise UserError(f"Falta el precio referencial para el producto '{line.product_id.display_name}'. El equipo de Compras debe colocar un precio mayor a 0.00 antes de solicitar la primera firma.")

        # Si pasa las validaciones, permitimos que el Mixin inicie la ruta normal
        return super(PurchaseRequisition, self).action_request_approval()

    # ==========================================
    # MOTOR DE APROBACIÓN (Fase 1 Corregida)
    # ==========================================
    def action_confirm(self):
        for record in self:
            if record.approval_status == 'draft':
                record.action_request_approval()
            
            if record.approval_status != 'approved':
                return False
                
        return super(PurchaseRequisition, self).action_confirm()


class PurchaseRequisitionLine(models.Model):
    _inherit = 'purchase.requisition.line'

    # Campo invisible que detecta si el usuario logueado es del grupo "Cotizadores"
    is_user_quoter = fields.Boolean(compute='_compute_is_user_quoter')

    def _compute_is_user_quoter(self):
        for line in self:
            line.is_user_quoter = self.env.user.has_group('supply_chain_approvals.group_supply_chain_quoters')


    # ==========================================
    # AUDITORÍA DE PRECIOS Y CANTIDADES EN EL CHATTER
    # ==========================================
    def write(self, vals):
        # Si el diccionario de cambios contiene precio o cantidad
        if 'price_unit' in vals or 'product_qty' in vals:
            for line in self:
                old_price = line.price_unit
                old_qty = line.product_qty
                
                # Obtenemos los nuevos valores (si no vienen en 'vals', mantenemos los viejos)
                new_price = vals.get('price_unit', old_price)
                new_qty = vals.get('product_qty', old_qty)
                
                cambios = []
                
                # Registramos si cambió el precio
                if 'price_unit' in vals and old_price != new_price:
                    cambios.append(f"<li><b>Precio:</b> {old_price} ➔ <b style='color: #d9534f;'>{new_price}</b></li>")
                    
                # Registramos si cambió la cantidad
                if 'product_qty' in vals and old_qty != new_qty:
                    cambios.append(f"<li><b>Cantidad:</b> {old_qty} ➔ <b style='color: #d9534f;'>{new_qty}</b></li>")
                
                # Si hubo al menos un cambio real, disparamos el mensaje
                if cambios:
                    mensaje = f"⚠️ <b>Auditoría de Modificación (Línea editada):</b><br/>" \
                              f"Producto: <i>{line.product_id.display_name}</i><br/>" \
                              f"<ul>{''.join(cambios)}</ul>"
                    
                    line.requisition_id.message_post(body=mensaje)
                    
        return super(PurchaseRequisitionLine, self).write(vals)