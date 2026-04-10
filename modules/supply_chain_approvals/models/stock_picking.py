from odoo import models, fields

class StockPicking(models.Model):
    # Ya no usamos _name, solo _inherit porque no estamos creando un modelo nuevo, solo ampliando el nativo
    _inherit = 'stock.picking'

    # Campos para guardar la auditoría visual
    received_by_id = fields.Many2one('res.users', string="Recibido por (Recepción)", readonly=True, copy=False)
    reviewed_by_id = fields.Many2one('res.users', string="Revisado por (Calidad)", readonly=True, copy=False)

    def action_mark_received(self):
        for record in self:
            record.write({'received_by_id': self.env.user.id})

    def action_mark_reviewed(self):
        for record in self:
            record.write({'reviewed_by_id': self.env.user.id})