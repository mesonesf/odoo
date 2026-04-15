from odoo import models, fields

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    received_by_id = fields.Many2one('res.users', string="Recibido por (Recepción)", readonly=True, copy=False)
    reviewed_by_id = fields.Many2one('res.users', string="Revisado por (Calidad)", readonly=True, copy=False)

    def action_mark_received(self):
        for record in self:
            record.write({'received_by_id': self.env.user.id})

    def action_mark_reviewed(self):
        for record in self:
            record.write({'reviewed_by_id': self.env.user.id})

    # ==========================================
    # AUDITORÍA EN EL CHATTER AL VALIDAR
    # ==========================================
    def button_validate(self):
        res = super(StockPicking, self).button_validate()
        for picking in self:
            if picking.state == 'done':
                mensaje = f"📦 <b>Operación de Almacén Registrada</b><br/>" \
                          f"Usuario responsable: <i>{self.env.user.name}</i><br/>" \
                          f"Acción: Recepción/Entrega Validada en Sistema."
                picking.message_post(body=mensaje)
        return res