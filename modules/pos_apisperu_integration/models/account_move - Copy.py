import requests
from odoo import models, fields, api
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    apiperu_enlace_pdf = fields.Char(string='Enlace PDF')
    apiperu_enlace_xml = fields.Char(string='Enlace XML')
    apiperu_hash_cpe = fields.Char(string='Hash CPE')
    apiperu_estado_sunat = fields.Selection([
        ('aceptado', 'Aceptado'),
        ('rechazado', 'Rechazado'),
        ('excepcion', 'Excepción')
    ], string='Estado SUNAT', readonly=True)

    # def action_post(self):
    #     res = super(AccountMove, self).action_post()
    #     for move in self.filtered(lambda m: m.country_code == 'PE' and m.move_type in ('out_invoice', 'out_refund')):
    #         # Enviar a la cola de trabajos (queue_job) para no bloquear el POS
    #         if hasattr(move, 'with_delay'):
    #             move.with_delay(channel='root')._enviar_factura_apisperu()
    #         else:
    #             move._enviar_factura_apisperu()
    #     return res

    def action_post(self):
        res = super(AccountMove, self).action_post()
        for move in self.filtered(lambda m: m.country_code == 'PE' and m.move_type in ('out_invoice', 'out_refund')):
            # Forzamos el envío síncrono para pruebas en local
            move._enviar_factura_apisperu()
        return res

    def _enviar_factura_apisperu(self):
        self.ensure_one()
        token = self.env['ir.config_parameter'].sudo().get_param('apiperu.dev.token')
        if not token:
            raise UserError("Falta configurar el token de APIsPerú (apiperu.dev.token).")

        vat_code = self.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code
        
        payload = {
            "cliente_tipo_de_documento": vat_code if vat_code else "1",
            "cliente_numero_de_documento": self.partner_id.vat or "00000000",
            "cliente_denominacion": self.partner_id.name,
            "cliente_direccion": self.partner_id.street or "",
            "cliente_email": self.partner_id.email or "",
            "tipo_de_comprobante": "01" if vat_code == '6' else "03", 
            "serie": self.name.split('-')[0] if '-' in self.name else "B001",
            "numero": int(self.name.split('-')[1]) if '-' in self.name else 1,
            "moneda": "1" if self.currency_id.name == 'PEN' else "2",
            "fecha_de_emision": self.invoice_date.strftime('%Y-%m-%d') if self.invoice_date else fields.Date.context_today(self).strftime('%Y-%m-%d'),
            "total_gravada": self.amount_untaxed,
            "total_igv": self.amount_tax,
            "total": self.amount_total,
            "enviar_automaticamente_a_la_sunat": True,
            "enviar_automaticamente_al_cliente": False,
            "items": []
        }

        for line in self.invoice_line_ids.filtered(lambda l: not l.display_type):
            qty = line.quantity or 1.0
            payload["items"].append({
                "unidad_de_medida": "NIU",
                "codigo": line.product_id.default_code or line.product_id.barcode or "S/C",
                "descripcion": line.name,
                "cantidad": qty,
                "valor_unitario": line.price_subtotal / qty,
                "precio_unitario": line.price_total / qty,
                "subtotal": line.price_subtotal,
                "tipo_de_igv": "1",
                "igv": line.price_total - line.price_subtotal,
                "total": line.price_total
            })

        url = "https://api.apiperu.dev/api/v1/cpe"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get('success'):
                data = response_data.get('data', {})
                self.write({
                    'apiperu_enlace_pdf': data.get('enlace_del_pdf'),
                    'apiperu_enlace_xml': data.get('enlace_del_xml'),
                    'apiperu_hash_cpe': data.get('hash_cpe'),
                    'apiperu_estado_sunat': 'aceptado' if data.get('aceptada_por_sunat') else 'excepcion'
                })
                self.message_post(body=f"✅ Comprobante enviado a SUNAT vía APIsPerú. <br/><a href='{data.get('enlace_del_pdf')}' target='_blank'>Ver PDF</a>")
            else:
                error_msg = response_data.get('message', 'Error desconocido al emitir en APIsPerú')
                self.write({'apiperu_estado_sunat': 'rechazado'})
                self.message_post(body=f"❌ Error SUNAT/APIsPerú: {error_msg}")
                
        except requests.exceptions.RequestException as e:
            self.message_post(body=f"⚠️ Error de conexión con APIsPerú: {str(e)}")
