from odoo import models, fields, api

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # 2.1 Origen Típico (Dinámico)
    origen_tipico_id = fields.Many2one('crm.origen', string='Origen Típico')

    # 2.2 Tipo Cuenta
    tipo_cuenta = fields.Selection([
        ('nueva', 'Nueva'),
        ('mantenimiento', 'Mantenimiento')
    ], string='Tipo de Cuenta')

    # 2.3 Jerarquía de Producto
    linea_producto_id = fields.Many2one('crm.linea.producto', string='Línea de Producto')
    # El domain hace que solo se vean los Tipos que pertenecen a la Línea seleccionada
    tipo_producto_id = fields.Many2one('crm.tipo.producto', string='Tipo de Producto', 
                                       domain="[('linea_id', '=', linea_producto_id)]")

    # 2.4 Volumen
    volumen_negocio = fields.Integer(string='Volumen Estimado')

    # 2.5 Normativa (Dinámico)
    normativa_id = fields.Many2one('crm.normativa', string='Normativa')

    # 2.6 Dolor (Dinámico)
    dolor_id = fields.Many2one('crm.dolor', string='Dolor Principal')

    # --- Onchange para limpiar el hijo si cambia el padre ---
    @api.onchange('linea_producto_id')
    def _onchange_linea_producto(self):
        self.tipo_producto_id = False