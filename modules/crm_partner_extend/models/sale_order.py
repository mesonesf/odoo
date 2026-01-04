# from odoo import models, fields

# class SaleOrder(models.Model):
#     _inherit = 'sale.order'

#     enlace_externo = fields.Char(string='Link Documentación / Carpeta')

#     # --- PUNTO 4: Actualizar Tipo de Cuenta al Confirmar ---
#     def action_confirm(self):
#         # 1. Ejecutar la lógica original de Odoo (confirmar orden)
#         res = super(SaleOrder, self).action_confirm()
        
#         # 2. Nuestra lógica personalizada
#         for order in self:
#             if order.partner_id:
#                 # Cambiamos el estado del cliente a Mantenimiento
#                 order.partner_id.tipo_cuenta = 'mantenimiento'
        
#         return res
from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    es_cotizacion_crm = fields.Boolean(string='Es Cotización CRM', default=False, help="Marca si es una cotización aproximada sin variantes")
    enlace_externo = fields.Char(string='Link Carpeta/Doc')

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            if order.partner_id:
                order.partner_id.tipo_cuenta = 'mantenimiento'
        return res

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.onchange('product_template_id')
    def _onchange_product_template_id_crm_clean(self):
        # Si es modo CRM, autoseleccionamos la primera variante disponible
        if self.env.context.get('disable_product_configurator') or self.order_id.es_cotizacion_crm:
            if self.product_template_id:
                variant = self.product_template_id.product_variant_id
                if variant:
                    self.product_id = variant
                    self.name = self.product_template_id.name # Nombre limpio sin variantes