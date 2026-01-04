from odoo import models, fields, api

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # 2.1 Origen Típico
    origen_tipico_id = fields.Many2one('crm.origen', string='Origen Típico')

    # (ELIMINADO) tipo_cuenta -> Ahora está en res.partner

    # 2.3 Jerarquía de Producto
    linea_producto_id = fields.Many2one('crm.linea.producto', string='Línea de Producto')
    tipo_producto_id = fields.Many2one('crm.tipo.producto', string='Tipo de Producto', 
                                       domain="[('linea_id', '=', linea_producto_id)]")

    # 2.4 Volumen
    volumen_negocio = fields.Integer(string='Volumen Estimado')

    # 2.5 Normativa
    normativa_id = fields.Many2one('crm.normativa', string='Normativa')

    # 2.6 Dolor
    dolor_id = fields.Many2one('crm.dolor', string='Dolor Principal')

    @api.onchange('linea_producto_id')
    def _onchange_linea_producto(self):
        self.tipo_producto_id = False