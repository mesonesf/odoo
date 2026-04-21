from odoo import models, fields

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    received_by_id = fields.Many2one('res.users', string="Recibido por (Recepción)", readonly=True, copy=False)
    reviewed_by_id = fields.Many2one('res.users', string="Revisado por (Calidad)", readonly=True, copy=False)

    # ==========================================
    # AUDITORÍA DE BOTONES PERSONALIZADOS
    # ==========================================
    def action_mark_received(self):
        for record in self:
            record.write({'received_by_id': self.env.user.id})
            record.message_post(body=f"📥 <b>Recepción Física</b><br/>Usuario: <i>{self.env.user.name}</i> marcó la recepción de los productos.")

    def action_mark_reviewed(self):
        for record in self:
            record.write({'reviewed_by_id': self.env.user.id})
            record.message_post(body=f"🔍 <b>Control de Calidad</b><br/>Usuario: <i>{self.env.user.name}</i> realizó la validación de calidad.")

    # ==========================================
    # AUDITORÍA DEL BOTÓN NATIVO "VALIDAR"
    # ==========================================
    def button_validate(self):
        # 1. Registramos el clic INMEDIATAMENTE, sin importar si Odoo abre ventanas emergentes después
        for picking in self:
            picking.message_post(body=f"✅ <b>Intento de Validación</b><br/>El usuario <i>{self.env.user.name}</i> presionó el botón Validar.")
            
        # 2. Ejecutamos el flujo normal de Odoo
        return super(StockPicking, self).button_validate()

    # ==========================================
    # AUDITORÍA DEL CIERRE REAL (ESTADO HECHO)
    # ==========================================
    def _action_done(self):
        # Esta es una función profunda de Odoo. Se ejecuta SOLO cuando el inventario realmente se mueve.
        res = super(StockPicking, self)._action_done()
        
        for picking in self:
            picking.message_post(body=f"📦 <b>Movimiento Completado</b><br/>El inventario fue procesado y cerrado definitivamente por <i>{self.env.user.name}</i>.")
            
        return res