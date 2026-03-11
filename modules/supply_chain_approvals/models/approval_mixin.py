from odoo import models, fields, api, exceptions
from markupsafe import Markup

class ApprovalMixin(models.AbstractModel):
    _name = 'approval.mixin'
    _description = 'Mixin de Aprobación Supply Chain'

    approval_status = fields.Selection([
        ('draft', 'Borrador'),
        ('to_approve', 'Esperando Aprobación'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado')
    ], default='draft', string="Estado Aprobación", tracking=True, copy=False)

    # --- SOLUCIÓN: Nombres "Dummy" para evitar el conflicto interno del Mixin ---
    approver_ids = fields.Many2many(
        'res.users', 
        'approval_mixin_dummy_approvers_rel',  # <--- Nombre ficticio 1
        string="Firmas Requeridas", 
        copy=False
    )
    
    approved_user_ids = fields.Many2many(
        'res.users', 
        'approval_mixin_dummy_signed_rel',     # <--- Nombre ficticio 2
        string="Firmas Recibidas", 
        copy=False
    )
    
    is_current_user_approver = fields.Boolean(compute='_compute_is_approver')

    @api.depends('approver_ids', 'approved_user_ids')
    def _compute_is_approver(self):
        for record in self:
            current = self.env.user
            # Es aprobador si: Está en la lista requerida Y NO ha firmado aún
            is_req = current in record.approver_ids
            has_signed = current in record.approved_user_ids
            # Superuser o aprobador pendiente
            record.is_current_user_approver = (is_req and not has_signed) or self.env.is_superuser()

    def _get_approvers_from_config(self, user):
        """Mapea el modelo con el campo en res.users"""
        if self._name == 'purchase.order':
            return user.purchase_approver_ids
        elif self._name == 'stock.picking':
            return user.stock_approver_ids
        elif self._name == 'account.move':
            return user.account_approver_ids
        elif self._name == 'account.payment':
            return user.payment_approver_ids
        return False

    def action_request_approval(self):
        for record in self:
            # 1. Obtener aprobadores del Creador del documento
            creator = record.create_uid
            configured_approvers = record._get_approvers_from_config(creator)

            # 2. Lógica: Si no hay nadie configurado, aprobar directo
            if not configured_approvers:
                record.write({
                    'approval_status': 'approved',
                    'approver_ids': [(5, 0, 0)],
                    'approved_user_ids': [(5, 0, 0)]
                })
                # ACTUALIZADO: Markup y tipo de mensaje para renderizado HTML seguro
                record.message_post(
                    body=Markup("<i>Sistema: Aprobación automática (Sin aprobadores configurados).</i>"),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note'
                )
            else:
                record.write({
                    'approver_ids': [(6, 0, configured_approvers.ids)],
                    'approved_user_ids': [(5, 0, 0)],
                    'approval_status': 'to_approve'
                })

    # --- WIZARD ---
    def open_approval_wizard(self, action_type):
        self.ensure_one()
        return {
            'name': 'Firma de Aprobación',
            'type': 'ir.actions.act_window',
            'res_model': 'approval.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
                'default_action_type': action_type,
            }
        }

    def button_approve_wizard(self):
        return self.open_approval_wizard('approve')

    def button_reject_wizard(self):
        return self.open_approval_wizard('reject')

    def action_approve_process(self):
        """Firma un usuario. Si todos firman, se aprueba."""
        self.ensure_one()
        current = self.env.user
        self.write({'approved_user_ids': [(4, current.id)]})

        # Verificar si faltan firmas
        required = set(self.approver_ids.ids)
        signed = set(self.approved_user_ids.ids)
        
        if required.issubset(signed):
            self.write({'approval_status': 'approved'})
            # ACTUALIZADO: Markup y tipo de mensaje para renderizado HTML seguro
            self.message_post(
                body=Markup("<strong style='color:green'>¡Aprobación Completada! Todos han firmado.</strong>"),
                message_type='comment',
                subtype_xmlid='mail.mt_note'
            )
        else:
            missing = self.approver_ids.filtered(lambda u: u.id not in signed).mapped('name')
            self.message_post(body=f"Faltan las firmas de: {', '.join(missing)}")

    def action_reject_process(self):
        """Rechazo total"""
        self.write({'approval_status': 'rejected', 'approved_user_ids': [(5, 0, 0)]})