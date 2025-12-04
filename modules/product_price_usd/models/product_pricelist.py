# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools import float_round

class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    # Agregamos "Precio Venta USD" a las opciones de "Basado en"
    base = fields.Selection(
        selection_add=[('price_usd', 'Precio Venta USD')], 
        ondelete={'price_usd': 'set default'}
    )

class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    # CORRECCIÓN ODOO 18: El primer argumento ahora es 'products' (recordset), no una lista de tuplas.
    def _compute_price_rule(self, products, *args, **kwargs):
        """ Sobrescribimos el cálculo para que entienda nuestro campo nuevo """
        
        # 1. Ejecutamos la lógica original de Odoo
        # Usamos *args y **kwargs para ser compatibles con cualquier cambio de firma de Odoo
        res = super(ProductPricelist, self)._compute_price_rule(products, *args, **kwargs)
        
        # 2. Iteramos sobre los productos recibidos (Odoo 18 pasa un recordset)
        for product in products:
            # Obtenemos el resultado que calculó Odoo (precio, regla_id)
            # res es un diccionario {product_id: (price, rule_id)}
            if product.id not in res:
                continue

            price, rule_id = res[product.id]
            
            if rule_id:
                # Buscamos la regla aplicada
                rule = self.env['product.pricelist.item'].browse(rule_id)
                
                # Si la regla es la nuestra ("Precio Venta USD")
                if rule.base == 'price_usd':
                    # Obtenemos el valor de TU campo
                    target_price = getattr(product, 'price_usd', 0.0)
                    
                    # Aplicamos descuentos/fórmulas si la lista de precios tiene alguna configuración extra
                    if rule.compute_price == 'formula':
                        price_limit = target_price
                        target_price -= (target_price * (rule.price_discount / 100))
                        if rule.price_round:
                            target_price = float_round(target_price, precision_rounding=rule.price_round)
                        target_price += rule.price_surcharge
                        if rule.price_min_margin:
                            target_price = max(target_price, price_limit + rule.price_min_margin)
                        if rule.price_max_margin:
                            target_price = min(target_price, price_limit + rule.price_max_margin)
                    
                    # Sobrescribimos el precio en el resultado final
                    res[product.id] = (target_price, rule_id)
        
        return res
