from odoo import models, fields, api
from odoo.exceptions import ValidationError

class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def procesar_pedido_custom(self, payload):
        partner_id = payload.get('usuario_id')
        if not partner_id:
            raise ValidationError("Debes seleccionar un cliente válido para finalizar el pago.")

        session = self.env['pos.session'].search([('state', '=', 'opened')], limit=1)
        if not session:
            raise ValidationError("La caja (POS Session) se encuentra cerrada.")

        order_lines = []
        for item in payload.get('items', []):
            product_id = item.get('producto_id') or item.get('id')
            if not product_id:
                continue
            
            product = self.env['product.product'].browse(product_id)
            if not product.exists():
                continue

            order_lines.append((0, 0, {
                'product_id': product.id,
                'qty': item.get('qty', 1),
                'price_unit': item.get('precio', 0.0),
                'discount': item.get('descuento_porcentaje', 0.0),
                'tax_ids': [(6, 0, product.taxes_id.ids)],
                'full_product_name': product.name,
            }))

        order_vals = {
            'session_id': session.id,
            'partner_id': partner_id,
            'lines': order_lines,
            'amount_paid': payload.get('total_cobrado', 0.0),
        }

        # 1. Crear el pedido POS
        order = self.create(order_vals)

        # 2. Registrar el pago (Mapeando 'EFECTIVO' o 'TARJETA' con los métodos de Odoo)
        payment_method_name = payload.get('metodo_pago', 'EFECTIVO').upper()
        payment_method = session.config_id.payment_method_ids.filtered(
            lambda pm: pm.name.upper() == payment_method_name
        )
        if payment_method:
            self.env['pos.payment'].create({
                'pos_order_id': order.id,
                'payment_method_id': payment_method[0].id,
                'amount': order.amount_total,
            })

        # 3. Confirmar pedido (esto baja stock por FEFO si está configurado en las rutas)
        order.action_pos_order_paid()

        # 4. Generar factura si el frontend lo solicita
        if payload.get('emitir_comprobante'):
            order.action_pos_order_invoice()
            # Al ejecutarse esto, el account.move se publica y dispara nuestra asincronía en account_move.py

        return {
            'ok': True,
            'pedido_id': order.id,
            'codigo': order.pos_reference,
            'factura_id': order.account_move.id if order.account_move else False,
        }
