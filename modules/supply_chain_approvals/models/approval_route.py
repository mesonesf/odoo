from odoo import models, fields

class ApprovalRoute(models.Model):
    _name = 'approval.route'
    _description = 'Ruta de Aprobación'

    name = fields.Char(string="Nombre de la Ruta", required=True)
    model_id = fields.Selection([
        ('purchase.requisition', '1. Requerimientos (Precios Referenciales)'),
        ('purchase.order', '2. Pedidos / Cotizaciones (Firma Final)')
    ], string="Documento a Aplicar", required=True)
    
    step_ids = fields.One2many('approval.step', 'route_id', string='Pasos de Aprobación')
    active = fields.Boolean(default=True)

class ApprovalStep(models.Model):
    _name = 'approval.step'
    _description = 'Paso de Aprobación'
    _order = 'sequence, id' # Respeta el orden secuencial

    route_id = fields.Many2one('approval.route', required=True, ondelete='cascade')
    sequence = fields.Integer(string="Secuencia", default=10)
    name = fields.Char(string="Nombre del Paso (Ej. 1era Aprobación)", required=True)
    approver_ids = fields.Many2many('res.users', string='Aprobadores en este Paso')