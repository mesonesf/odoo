import json
import logging
import requests
import base64
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

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
    #         # En local, forzamos el envío síncrono para ver errores en tiempo real
    #         move._enviar_factura_apisperu()
    #     return res
    def action_post(self):
        res = super(AccountMove, self).action_post()
        for move in self.filtered(lambda m: m.country_code == 'PE' and m.move_type in ('out_invoice', 'out_refund')):
            # En producción, usamos queue_job para no congelar la interfaz
            if hasattr(move, 'with_delay'):
                move.with_delay(channel='root')._enviar_factura_apisperu()
            else:
                move._enviar_factura_apisperu()
        return res

    def _enviar_factura_apisperu(self):
        self.ensure_one()
        token = self.env['ir.config_parameter'].sudo().get_param('apiperu.dev.token')
        if not token:
            raise UserError("Falta configurar el token de APIsPerú (apiperu.dev.token).")

        vat_code = self.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code or "1"
        moneda_str = "PEN" if self.currency_id.name == 'PEN' else "USD"
        
        # 1. Identificar si es Venta normal o Nota de Crédito
        is_refund = self.move_type == 'out_refund'
        
        if is_refund:
            tipo_doc = "07" # 07 = Nota de Crédito
            endpoint_url = "https://facturacion.apisperu.com/api/v1/note/send"
        else:
            tipo_doc = "01" if vat_code == '6' else "03"
            endpoint_url = "https://facturacion.apisperu.com/api/v1/invoice/send"

        # Manejo de serie y correlativo
        serie_split = self.name.split('-')
        if len(serie_split) > 1:
            serie = serie_split[0]
            correlativo = serie_split[1]
        else:
            # Fallback si Odoo no generó la secuencia aún
            if is_refund:
                serie = "FC01" if vat_code == '6' else "BC01"
            else:
                serie = "F001" if tipo_doc == "01" else "B001"
            correlativo = "1"

        mto_gravadas = round(self.amount_untaxed, 2)
        mto_igv = round(self.amount_tax, 2)
        mto_total = round(self.amount_total, 2)

        # 2. Estructura Base compartida por Facturas y Notas
        payload = {
            "ublVersion": "2.1",
            "tipoDoc": tipo_doc,
            "serie": serie,
            "correlativo": correlativo,
            "fechaEmision": (self.invoice_date or fields.Date.context_today(self)).strftime('%Y-%m-%dT00:00:00-05:00'),
            "tipoMoneda": moneda_str,
            "client": {
                "tipoDoc": vat_code,
                "numDoc": self.partner_id.vat or "00000000",
                "rznSocial": self.partner_id.name,
                "address": {
                    "direccion": self.partner_id.street or "-"
                }
            },
            "company": {
                "ruc": self.company_id.vat or "20000000000",
                "razonSocial": self.company_id.name or "Mi Empresa",
                "address": {
                    "direccion": self.company_id.street or "-"
                }
            },
            "mtoOperGravadas": mto_gravadas,
            "mtoIGV": mto_igv,
            "totalImpuestos": mto_igv,
            "valorVenta": mto_gravadas,
            "subTotal": mto_total,
            "mtoImpVenta": mto_total,
            "details": []
        }

        # 3. Campos condicionales dependiendo del tipo de documento
        if is_refund:
            orig_move = self.reversed_entry_id
            if not orig_move:
                raise UserError("La nota de crédito debe estar vinculada a una factura original.")
            
            orig_tipo_doc = "01" if vat_code == '6' else "03"
            orig_serie = orig_move.name if '-' in orig_move.name else f"{'F001' if orig_tipo_doc == '01' else 'B001'}-1"

            # Campos obligatorios para notas
            payload["codMotivo"] = "01" # 01 = Anulación de la operación
            payload["desMotivo"] = self.ref or "Anulacion de la operacion"
            payload["tipDocAfectado"] = orig_tipo_doc
            payload["numDocAfectado"] = orig_serie
        else:
            # Campos obligatorios para facturas
            payload["tipoOperacion"] = "0101"
            
            is_credit = False
            cuotas = []
            receivable_lines = self.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable' and l.debit > 0)
            
            if receivable_lines:
                for line in receivable_lines:
                    fecha_vencimiento = line.date_maturity or self.invoice_date or fields.Date.context_today(self)
                    fecha_emision = self.invoice_date or fields.Date.context_today(self)
                    if fecha_vencimiento > fecha_emision:
                        is_credit = True
                    monto_cuota = line.amount_currency if self.currency_id != self.company_id.currency_id else line.debit
                    cuotas.append({
                        "moneda": moneda_str,
                        "monto": round(monto_cuota, 2),
                        "fechaPago": fecha_vencimiento.strftime('%Y-%m-%d')
                    })
            
            payload["formaPago"] = {
                "moneda": moneda_str,
                "tipo": "Credito" if is_credit else "Contado"
            }
            if is_credit:
                payload["cuotas"] = cuotas

        # 4. Construcción del Detalle (Items)
        for line in self.invoice_line_ids.filtered(lambda l: l.display_type not in ('line_section', 'line_note')):
            qty = float(line.quantity or 1.0)
            mto_valor_unitario = round(line.price_subtotal / qty, 5) if qty else 0.0
            mto_valor_venta = round(line.price_subtotal, 2)
            igv_linea = round(line.price_total - line.price_subtotal, 2)
            precio_con_igv = round(line.price_total / qty, 2) if qty else 0.0
            
            payload["details"].append({
                "codProducto": line.product_id.default_code or line.product_id.barcode or "S/C",
                "unidad": "NIU",
                "descripcion": line.name or "Servicio",
                "cantidad": qty,
                "mtoValorUnitario": mto_valor_unitario,
                "mtoValorVenta": mto_valor_venta,
                "mtoBaseIgv": mto_valor_venta,
                "porcentajeIgv": 18,
                "igv": igv_linea,
                "tipAfeIgv": "10" if igv_linea > 0 else "20",
                "totalImpuestos": igv_linea,
                "mtoPrecioUnitario": precio_con_igv
            })

        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        _logger.info(f"====== PAYLOAD ENVIADO A {endpoint_url} ======")
        _logger.info(json.dumps(payload, indent=4))
        
        try:
            # Petición principal (SEND)
            response = requests.post(endpoint_url, json=payload, headers=headers, timeout=15)
            response_data = response.json()
            
            _logger.info("====== RESPUESTA DE APIPERU (SEND) ======")
            _logger.info(json.dumps(response_data, indent=4))
            
            if response.status_code == 200 and response_data.get('hash'):
                update_vals = {
                    'apiperu_hash_cpe': response_data.get('hash'),
                    'apiperu_estado_sunat': 'aceptado'
                }

                safe_name = self.name.replace('/', '-')
                attachment_xml_id = False
                attachment_pdf_id = False

                # 1. Generar y adjuntar el XML
                xml_content = response_data.get('xml')
                if xml_content:
                    xml_base64 = base64.b64encode(xml_content.encode('utf-8')).decode('utf-8')
                    attachment_xml = self.env['ir.attachment'].create({
                        'name': f"{safe_name}.xml",
                        'type': 'binary',
                        'datas': xml_base64,
                        'res_model': 'account.move',
                        'res_id': self.id,
                        'mimetype': 'application/xml'
                    })
                    attachment_xml_id = attachment_xml.id
                    update_vals['apiperu_enlace_xml'] = f"/web/content/{attachment_xml_id}?download=true"

                # 2. Solicitar y adjuntar el PDF a APIsPerú
                pdf_endpoint = "https://facturacion.apisperu.com/api/v1/note/pdf" if is_refund else "https://facturacion.apisperu.com/api/v1/invoice/pdf"
                try:
                    pdf_resp = requests.post(pdf_endpoint, json=payload, headers=headers, timeout=15)
                    if pdf_resp.status_code == 200:
                        content_type = pdf_resp.headers.get('Content-Type', '')
                        pdf_base64 = None
                        
                        # APIsPerú puede devolver un JSON con base64 o el archivo binario directo
                        if 'application/json' in content_type:
                            pdf_json = pdf_resp.json()
                            pdf_base64 = pdf_json.get('pdf') or pdf_json.get('base64') or (pdf_json.get('data', {}) if isinstance(pdf_json.get('data'), str) else None)
                        else:
                            pdf_base64 = base64.b64encode(pdf_resp.content).decode('utf-8')
                        
                        if pdf_base64:
                            attachment_pdf = self.env['ir.attachment'].create({
                                'name': f"{safe_name}.pdf",
                                'type': 'binary',
                                'datas': pdf_base64,
                                'res_model': 'account.move',
                                'res_id': self.id,
                                'mimetype': 'application/pdf'
                            })
                            attachment_pdf_id = attachment_pdf.id
                            update_vals['apiperu_enlace_pdf'] = f"/web/content/{attachment_pdf_id}?download=true"
                except Exception as e:
                    _logger.error(f"Error al generar PDF con APIsPerú: {e}")

                self.write(update_vals)
                
                # Armar el mensaje para el historial (Chatter)
                tipo_msg = "Nota de Crédito" if is_refund else "Comprobante"
                msg_body = f"✅ {tipo_msg} aceptado por SUNAT."
                
                adjuntos = []
                if attachment_pdf_id:
                    msg_body += f"<br/>📄 <a href='/web/content/{attachment_pdf_id}?download=true' target='_blank'><b>Descargar PDF</b></a>"
                    adjuntos.append(attachment_pdf_id)
                if attachment_xml_id:
                    msg_body += f"<br/>📄 <a href='/web/content/{attachment_xml_id}?download=true' target='_blank'><b>Descargar XML</b></a>"
                    adjuntos.append(attachment_xml_id)
                
                self.message_post(body=msg_body, attachment_ids=adjuntos)
            else:
                sunat_resp = response_data.get('sunatResponse', {})
                error_obj = sunat_resp.get('error', {})
                error_msg = error_obj.get('message') or response_data.get('message', 'Error desconocido al emitir')
                
                self.write({'apiperu_estado_sunat': 'rechazado'})
                self.message_post(body=f"❌ Error SUNAT: {error_msg}")
                _logger.error(f"Error al enviar a APIsPerú: {error_msg}")
                
        except requests.exceptions.RequestException as e:
            self.message_post(body=f"⚠️ Error de conexión con APIsPerú: {str(e)}")
            _logger.error(f"Excepción HTTP: {str(e)}")