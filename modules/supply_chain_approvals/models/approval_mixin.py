from odoo import models, fields, api
from markupsafe import Markup

class ApprovalMixin(models.AbstractModel):
    _name = 'approval.mixin'
    _description = 'Mixin Secuencial de Aprobación'

    approval_status = fields.Selection([
        ('draft', 'Borrador'),
        ('to_approve', 'Esperando Aprobación'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado')
    ], default='draft', string="Estado Aprobación", tracking=True, copy=False)

    # El motor secuencial
    route_id = fields.Many2one('approval.route', string="Ruta Asignada", copy=False)
    current_step_id = fields.Many2one('approval.step', string="Paso Actual", copy=False)
    

    # Usamos nombres "dummy" (ficticios) distintos para que el validador de Odoo no se queje.
    # Los modelos reales (purchase.requisition y purchase.order) sobreescribirán esto.
    approver_ids = fields.Many2many('res.users', relation='mixin_approver_dummy_rel', string="Firmas Requeridas (Paso Actual)", copy=False)
    approved_user_ids = fields.Many2many('res.users', relation='mixin_approved_dummy_rel', string="Firmas Recibidas (Paso Actual)", copy=False)
    
    is_current_user_approver = fields.Boolean(compute='_compute_is_approver')

    @api.depends('approver_ids', 'approved_user_ids')
    def _compute_is_approver(self):
        for record in self:
            current = self.env.user
            is_req = current in record.approver_ids
            has_signed = current in record.approved_user_ids
            record.is_current_user_approver = (is_req and not has_signed) or self.env.is_superuser()

    def action_request_approval(self):
        for record in self:
            # 1. Buscar si hay una ruta configurada para este modelo
            route = self.env['approval.route'].search([('model_id', '=', self._name)], limit=1)
            
            if not route or not route.step_ids:
                # Si no hay rutas, se aprueba solo
                record.write({'approval_status': 'approved'})
                record.message_post(body=Markup("<i>Sistema: Aprobado (Sin ruta configurada).</i>"))
                continue

            # 2. Iniciar en el primer paso
            first_step = route.step_ids[0]
            record.write({
                'route_id': route.id,
                'current_step_id': first_step.id,
                'approver_ids': [(6, 0, first_step.approver_ids.ids)],
                'approved_user_ids': [(5, 0, 0)],
                'approval_status': 'to_approve'
            })
            record.message_post(body=Markup(f"<strong>Inicia Aprobación:</strong> Pasó a etapa <em>{first_step.name}</em>."))

    def action_approve_process(self):
        self.ensure_one()
        current = self.env.user
        self.write({'approved_user_ids': [(4, current.id)]})

        required = set(self.approver_ids.ids)
        signed = set(self.approved_user_ids.ids)
        
        # Si TODOS los del paso actual ya firmaron
        if required.issubset(signed):
            # Buscar el siguiente paso
            current_seq = self.current_step_id.sequence
            next_step = self.env['approval.step'].search([
                ('route_id', '=', self.route_id.id),
                ('sequence', '>', current_seq)
            ], order='sequence asc', limit=1)

            if next_step:
                # Avanzar al siguiente paso
                self.write({
                    'current_step_id': next_step.id,
                    'approver_ids': [(6, 0, next_step.approver_ids.ids)],
                    'approved_user_ids': [(5, 0, 0)] # Limpiar firmas para el nuevo paso
                })
                self.message_post(body=Markup(f"<strong style='color:blue'>Paso Completado.</strong> Avanza a: <em>{next_step.name}</em>."))
            else:
                # Ya no hay más pasos, APROBACIÓN TOTAL
                self.write({'approval_status': 'approved'})
                self.message_post(body=Markup("<strong style='color:green'>¡Aprobación Total Completada!</strong>"))

    def action_reject_process(self):
        self.write({'approval_status': 'rejected', 'approved_user_ids': [(5, 0, 0)]})

    # (Conserva los métodos open_approval_wizard, button_approve_wizard, etc. que ya tenías)
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