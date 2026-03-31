import json
import requests
import logging
import re
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    # --- CAMPOS DE RESPUESTA ---
    l10n_pe_edi_response = fields.Text(string='Respuesta PSE', readonly=True, copy=False)
    l10n_pe_edi_ticket = fields.Char(string='Ticket / CDR', readonly=True, copy=False)
    l10n_pe_edi_status = fields.Selection([
        ('no_sent', 'No Enviado'),
        ('accepted', 'Aceptado'),
        ('rejected', 'Rechazado'),
        ('error', 'Error de Conexión')
    ], string='Estado SUNAT', default='no_sent', copy=False)

    l10n_pe_cuo = fields.Char(string='CUO', copy=False)

    # --- CAMPOS SUNAT (Catálogos 09, 10 y Detracciones) ---
    l10n_pe_credit_note_type = fields.Selection([
        ('01', '01 - Anulación de la operación'), ('02', '02 - Anulación por error en el RUC'),
        ('03', '03 - Corrección por error en la descripción'), ('04', '04 - Descuento global'),
        ('05', '05 - Descuento por ítem'), ('06', '06 - Devolución total'), ('07', '07 - Devolución por ítem'),
        ('08', '08 - Bonificación'), ('09', '09 - Disminución en el valor'), ('10', '10 - Otros Conceptos')
    ], string="Motivo Nota de Crédito", default="01", copy=False)

    l10n_pe_debit_note_type = fields.Selection([
        ('01', '01 - Intereses por mora'), ('02', '02 - Aumento en el valor'), ('03', '03 - Penalidades/otros conceptos')
    ], string="Motivo Nota de Débito", default="01", copy=False)

    l10n_pe_detraction_code = fields.Char(string="Cód. Bien/Servicio (Detracción)", help="Catálogo 54")
    l10n_pe_detraction_amount = fields.Float(string="Monto Detracción")

    def _post(self, soft=True):
        for move in self:
            if not move.l10n_pe_cuo and move.date:
                periodo = move.date.strftime('%Y%m00')
                move.l10n_pe_cuo = f"{periodo}-{move.id}"
        return super(AccountMove, self)._post(soft=soft)

    def _get_correlativo_sunat(self):
        self.ensure_one()
        if self.name and '-' in self.name:
            return self.name.split('-')[-1]
        numbers = re.findall(r'\d+', self.name or '')
        return numbers[-1].zfill(8) if numbers else "00000000"

    def _prepare_pse_payload(self):
        """Genera el JSON consolidado UBL 2.1"""
        self.ensure_one()

        # AQUÍ ESTÁ LA CORRECCIÓN CLAVE: Usamos l10n_latam_document_type_id
        doc_code = self.l10n_latam_document_type_id.code if self.l10n_latam_document_type_id else '01'
        if self.move_type == 'out_refund': doc_code = '07'
        
        identificadores_pse = {'01': 'FC', '03': 'BC', '07': 'CC', '08': 'DC'}
        identificador = identificadores_pse.get(doc_code, 'FC')

        if not self.journal_id.l10n_pe_serie:
            raise UserError("Debe configurar la Serie Electrónica en el Diario contable.")

        txt_serie = self.journal_id.l10n_pe_serie
        txt_correlativo = self._get_correlativo_sunat()

        # Acumuladores
        mnt_tot_gravadas = mnt_tot_inafectas = mnt_tot_exoneradas = mnt_tot_gratuitas = 0.0

        detalles = []
        for i, line in enumerate(self.invoice_line_ids.filtered(lambda l: l.display_type == 'product')):
            tax_obj = line.tax_ids[:1]
            tip_tax = tax_obj.tax_group_id.name.upper() if tax_obj else "IGV"
            
            if "EXO" in tip_tax:
                cod_tip_afect = "20"
                mnt_tot_exoneradas += line.price_subtotal
            elif "INA" in tip_tax:
                cod_tip_afect = "30"
                mnt_tot_inafectas += line.price_subtotal
            elif "GRA" in tip_tax: 
                cod_tip_afect = "21"
                mnt_tot_gratuitas += line.price_subtotal
            else:
                cod_tip_afect = "10"
                mnt_tot_gravadas += line.price_subtotal

            # Cálculos de línea
            precio_unit_base = line.price_unit
            mnt_dscto_item = (precio_unit_base * line.quantity) * ((line.discount or 0.0) / 100.0)
            mnt_igv_item = line.price_total - line.price_subtotal
            prc_vta_unit_item = (line.price_total / line.quantity) if line.quantity else 0.0

            # UoM
            uom_code = getattr(line.product_uom_id, 'l10n_pe_edi_measure_unit_code', line.product_uom_id.name[:3].upper())
            if not uom_code or len(uom_code) > 3: uom_code = "NIU"

            detalles.append({
                "num_lin_item": i + 1,
                "cod_unid_item": uom_code,
                "cant_unid_item": line.quantity,
                "val_vta_item": round(line.price_subtotal, 2),
                "cod_tip_afect_igv_item": cod_tip_afect,
                "prc_vta_unit_item": round(prc_vta_unit_item, 5),
                "mnt_dscto_item": round(mnt_dscto_item, 2),
                "mnt_igv_item": round(mnt_igv_item, 2),
                "txt_descr_item": line.name[:250],
                "cod_prod_sunat": "31201501", 
                "cod_item": line.product_id.default_code or str(line.product_id.id),
                "val_unit_item": round(precio_unit_base, 2),
                "importe_total_item": round(line.price_total, 2),
            })

        # Mapeo de Identidad del Cliente
        tipo_doc_cliente = getattr(self.partner_id.l10n_latam_identification_type_id, 'l10n_pe_vat_code', '6' if len(self.partner_id.vat or '') == 11 else '1')

        # Estructura Principal
        payload = {
            "identificador": identificador,
            "fec_emis": (self.invoice_date or fields.Date.context_today(self)).strftime("%Y-%m-%d"),
            "hora_emis": "00:00:00",
            "txt_serie": txt_serie,
            "txt_correlativo": txt_correlativo,
            "cod_tip_cpe": doc_code,
            "cod_mnd": self.currency_id.name,
            "cod_tip_escenario": "01",
            "cod_cliente_emis": self.company_id.l10n_pe_service_code or "1",
            "num_ruc_emis": self.company_id.vat or "",
            "nom_rzn_soc_emis": self.company_id.name or "",
            "cod_tip_nif_emis": 6,
            "cod_loc_emis": 1,
            "cod_ubi_emis": self.company_id.zip or "150101",
            "txt_dmcl_fisc_emis": self.company_id.street or "",
            "txt_prov_emis": self.company_id.state_id.name or "",
            "txt_dpto_emis": self.company_id.state_id.name or "",
            "txt_distr_emis": self.company_id.city or "",
            "num_iden_recp": self.partner_id.vat or "",
            "cod_tip_nif_recp": tipo_doc_cliente,
            "nom_rzn_soc_recp": self.partner_id.complete_name or "Sin Razon Social",
            "txt_dmcl_fisc_recep": self.partner_id.street or "Sin dirección",
            "txt_correo_adquiriente": self.partner_id.email or "",
            
            "mnt_tot_gravadas": round(mnt_tot_gravadas, 2),
            "mnt_tot_inafectas": round(mnt_tot_inafectas, 2),
            "mnt_tot_exoneradas": round(mnt_tot_exoneradas, 2),
            "mnt_tot_gratuitas": round(mnt_tot_gratuitas, 2),
            "mnt_tot_desc_global": 0.00,
            "mnt_tot_igv": self.amount_tax,
            "mnt_tot": self.amount_total,
            "cod_operacion": "0101",
            "flag_pagado": 0,
            "observaciones": "Emitido desde Odoo",
            "cod_tip_frmpgo": 1,
            
            "mnt_tot_detrac": self.l10n_pe_detraction_amount or 0.00,
            "tip_detrac": self.l10n_pe_detraction_code or "",
            
            "detalles": detalles
        }

        # Lógica Específica para NC / ND
        if doc_code in ['07', '08']:
            factura_original = self.reversed_entry_id or self.debit_origin_id
            if not factura_original and self.ref and '-' in self.ref:
                factura_original = self.env['account.move'].search([('name', '=', self.ref), ('company_id', '=', self.company_id.id)], limit=1)

            if not factura_original:
                raise UserError("Debe seleccionar el Documento Origen para emitir una Nota de Crédito/Débito.")

            cod_motivo = self.l10n_pe_credit_note_type if doc_code == '07' else self.l10n_pe_debit_note_type
            
            payload.update({
                "cod_tip_nc_nd_ref": cod_motivo,
                "txt_serie_ref": factura_original.journal_id.l10n_pe_serie or "",
                "txt_correlativo_cpe_ref": factura_original._get_correlativo_sunat(),
                "fec_emis_ref": factura_original.invoice_date.strftime("%Y-%m-%d"),
                # AQUÍ TAMBIÉN CORREGIMOS EL CAMPO
                "cod_cpe_ref": getattr(factura_original.l10n_latam_document_type_id, 'code', '01'),
                "txt_sustento": self.ref or "Modificación de documento",
            })

        return payload

    def action_show_payload(self):
        self.ensure_one()
        payload = self._prepare_pse_payload()
        lines_info = [f"Línea {i+1}: {line.name}\nSubtotal: {line.price_subtotal}" for i, line in enumerate(self.invoice_line_ids.filtered(lambda l: l.display_type == 'product'))]
        
        debug_rec = self.env['payload.debug'].create({
            'invoice_id': self.id,
            'payload_data': json.dumps(payload, indent=2),
            'line_details': "\n\n".join(lines_info)
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Detalle del Payload a Enviar',
            'view_mode': 'form',
            'res_model': 'payload.debug',
            'res_id': debug_rec.id,
            'target': 'new',
        }
    
    def action_send_pse(self):
        for move in self:
            if move.state != 'posted':
                raise UserError("El comprobante debe estar confirmado (Publicado) para enviarse al PSE.")
            
            company = move.company_id
            api_url = company.l10n_pe_pse_url
            token = company.l10n_pe_pse_token

            if not api_url or not token:
                raise UserError("Debe configurar la URL y el Token del PSE en Ajustes > Usuarios y Empresas > Empresas.")

            payload = move._prepare_pse_payload()

            headers = {
                'Content-Type': 'application/json',
                'Authorization': token 
            }

            try:
                response = requests.post(api_url, json=payload, headers=headers, timeout=20)
                try:
                    data = response.json()
                except ValueError:
                    data = {"Mensaje": response.text}

                if response.status_code in (200, 201) and isinstance(data, dict):
                    is_valid = data.get('Resultado', False)
                    error_msg = data.get('Mensaje', 'Mensaje no especificado por el PSE')

                    if is_valid:
                        move.write({
                            'l10n_pe_edi_status': 'accepted',
                            'l10n_pe_edi_response': json.dumps(data, indent=2),
                            'l10n_pe_edi_ticket': data.get('hash') or data.get('Ticket') or 'OK'
                        })
                        move.message_post(body=f"✅ Comprobante aceptado por el PSE.<br/>Mensaje: {error_msg}")
                    else:
                        move.write({
                            'l10n_pe_edi_status': 'rejected',
                            'l10n_pe_edi_response': json.dumps(data, indent=2)
                        })
                        move.message_post(body=f"❌ Comprobante rechazado por el PSE.<br/>Motivo: {error_msg}")
                else:
                    move.write({
                        'l10n_pe_edi_status': 'error',
                        'l10n_pe_edi_response': json.dumps(data, indent=2)
                    })
                    move.message_post(body=f"🔴 Error devuelto por el servidor PSE (HTTP {response.status_code}):<br/>{data.get('Mensaje')}")

            except requests.exceptions.Timeout:
                move.write({
                    'l10n_pe_edi_status': 'error',
                    'l10n_pe_edi_response': "Tiempo de espera agotado (Timeout)."
                })
                move.message_post(body="🔴 El servidor del PSE tardó demasiado en responder.")
                
            except requests.exceptions.RequestException as e:
                move.write({
                    'l10n_pe_edi_status': 'error',
                    'l10n_pe_edi_response': str(e)
                })
                move.message_post(body=f"🔴 Fallo crítico de conexión de red:<br/>{str(e)}")