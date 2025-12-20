from odoo import models, fields, api
import requests
import logging
import json

_logger = logging.getLogger(__name__)

# Variable global para mantener compatibilidad con tu estructura
ws_diario = ""

class AccountMove(models.Model):
    _inherit = 'account.move'

    ws_response = fields.Char(string="Respuesta WS", readonly=True)

    # -------------------------------------------------------------------------
    # UTILITARIOS
    # -------------------------------------------------------------------------
    def _get_correlativo_sunat(self):
        """
        Obtiene el número correlativo limpio a 8 dígitos basándose en la secuencia de Odoo.
        Esto permite que el usuario configure el inicio (ej. 500) usando la función
        'Renumerar' de Odoo en la interfaz.
        """
        if not self.name or self.name == '/':
            return "00000000"
        
        # Odoo genera nombres tipo "F001-00000500" o "INV/2025/00500"
        # Esta lógica extrae solo la parte numérica final
        parts = self.name.split('-')
        if len(parts) > 1:
            numero = parts[-1]
        else:
            # Fallback por si el formato de secuencia es diferente
            import re
            numbers = re.findall(r'\d+', self.name)
            numero = numbers[-1] if numbers else "0"
            
        return numero.zfill(8)

    # -------------------------------------------------------------------------
    # ACCIÓN DEL BOTÓN ELECTRONICO 
    # -------------------------------------------------------------------------
    def action_fe_payload(self):
        global ws_diario
        
        # 1. Ejecutar lógica nativa de Odoo
        res = super().action_post()
        
        # 2. VALIDACIÓN DE CONFIGURACIÓN
        # Aquí evitamos el hardcode. Si el usuario no configuró el diario, lanzamos error.
        if not self.journal_id.l10n_pe_serie:
            self.ws_response = "❌ Error de Configuración: Vaya a Contabilidad > Diarios y configure el campo 'Serie Electrónica SUNAT' (Ej: F001) para el diario actual."
            return res

        ws_diario = self.journal_id  # Asignamos el diario actual
       
        # Agrega esto antes de los if
        #print("DEBUG TIPO DOC:", self.l10n_latam_document_type_id.name)
        #print("DEBUG CODIGO:", self.l10n_latam_document_type_id.code)
        #print("DEBUG MOVE TYPE:", self.move_type)

        # 3. Direccionamiento dinámico
        # Nota: Ya no depende del nombre del diario, sino del tipo de documento y configuración
        if self.move_type == 'out_invoice' and self.l10n_latam_document_type_id.code == '01': 
             self._prepare_api_factura()
        elif self.move_type == 'out_invoice' and self.l10n_latam_document_type_id.code == '03': 
             self._prepare_api_boleta()
        elif self.move_type == 'out_refund' and self.l10n_latam_document_type_id.code == '07': 
             self._prepare_api_notacredito()
        elif self.move_type == 'out_invoice' and self.l10n_latam_document_type_id.code == '08': 
             self._prepare_api_notadebito()
        
        return res

    # -------------------------------------------------------------------------
    # FACTURA (01)
    # -------------------------------------------------------------------------
    def _prepare_api_factura(self):
        global ws_diario
        self.ensure_one()
        api_url = self.company_id.service_url

        #print("Ingreso Factura:")

        # Variables iniciales (limpias)
        Tax = 0.18
        TipTax = "IGV"
        cod_tip_afect_igv_item = 30
        mnt_tot_gravadas = 0.00
        mnt_tot_inafectas = 0.00
        mnt_tot_exoneradas = 0.00
        mnt_tot_gratuitas = 0.00

        detalles = []
        for i, line in enumerate(self.invoice_line_ids, start=1):
            # Obtener datos de impuestos dinámicamente
            tax_obj = line.tax_ids[:1]
            TipTax = tax_obj.tax_group_id.name if tax_obj else "IGV"
            Tax = (tax_obj.amount / 100) if tax_obj else 0.18

            # Clasificación de impuestos
            if "IGV" in str(TipTax).upper():
                cod_tip_afect_igv_item = 10
            elif "EXO" in str(TipTax).upper():
                cod_tip_afect_igv_item = 20
            elif "INA" in str(TipTax).upper():
                cod_tip_afect_igv_item = 30
            else:
                cod_tip_afect_igv_item = 10

            detalles.append({
                "num_lin_item": i,
                "cod_unid_item": "NIU",
                "cant_unid_item": line.quantity,
                "val_vta_item": line.price_subtotal,
                "cod_tip_afect_igv_item": cod_tip_afect_igv_item,
                "prc_vta_unit_item": line.price_unit * (1.00 + Tax),
                "mnt_dscto_item": 0.00,
                "mnt_igv_item": line.price_subtotal * Tax,
                "txt_descr_item": line.name,
                "cod_prod_sunat": "31201501",
                "cod_item": str(line.product_id.default_code or ''),
                "val_unit_item": line.price_unit,
                "cod_tip_sist_isc": "",
                "mnt_isc_item": 0.00,
                "porcentaje_isc": "",
                "dato_extra_1": "",
                "dato_extra_2": "",
                "importe_total_item": line.price_subtotal * (1.00 + Tax),
                "val_unit_icbper": 0.00,
                "cant_icbper_item": 0.00,
                "mnt_icbper_item": 0.00
            })

            # Acumuladores
            if cod_tip_afect_igv_item == 10:
                mnt_tot_gravadas += line.price_subtotal
            elif cod_tip_afect_igv_item == 30:
                mnt_tot_inafectas += line.price_subtotal
            elif cod_tip_afect_igv_item == 20:
                mnt_tot_exoneradas += line.price_subtotal

        # --- AQUI ESTA EL CAMBIO CLAVE ---
        # Leemos la serie directamente del diario configurado por el usuario
        txt_serie = self.journal_id.l10n_pe_serie 
        # El correlativo viene de la secuencia automática de Odoo
        txt_correlativo = self._get_correlativo_sunat()
        #print("SERIE:", txt_serie)
        #print("SERIE:", txt_correlativo)

        payload = {
            "identificador": "FC",
            "fec_emis": (self.invoice_date or fields.Date.context_today(self)).strftime("%Y-%m-%d"),
            "hora_emis": "00:00:00",
            "txt_serie": txt_serie,          # <--- VARIABLE CONFIGURABLE
            "txt_correlativo": txt_correlativo, # <--- VARIABLE CONFIGURABLE
            "cod_tip_cpe": "01",
            "cod_mnd": self.currency_id.name,
            "cod_tip_escenario": "01",
            "txt_placa": "",
            "cod_cliente_emis": self.company_id.service_code or "",
            "num_ruc_emis": self.company_id.vat or "",
            "nom_rzn_soc_emis": self.company_id.name or "",
            "cod_tip_nif_emis": 6,
            "cod_loc_emis": 1,
            "cod_ubi_emis": 150122,
            "txt_dmcl_fisc_emis": self.company_id.street or "",
            "txt_urb_emis": "URB. CERCADO DE MIRAFLORES",
            "txt_prov_emis": self.company_id.state_id.name or "",
            "txt_dpto_emis": self.company_id.state_id.name or "",
            "txt_distr_emis": self.company_id.city or "",
            "num_iden_recp": self.partner_id.vat or "",
            "cod_tip_nif_recp": 6,
            "nom_rzn_soc_recp": self.partner_id.name or "Sin Razon Social",
            "txt_dmcl_fisc_recep": self.partner_id.street or "Sin dirección",
            "txt_correo_adquiriente": self.partner_id.email or "",
            "mnt_tot_gravadas": mnt_tot_gravadas,
            "mnt_tot_inafectas": mnt_tot_inafectas,
            "mnt_tot_exoneradas": mnt_tot_exoneradas,
            "mnt_tot_gratuitas": mnt_tot_gratuitas,
            "mnt_tot_desc_global": 0.00,
            "mnt_tot_igv": self.amount_tax,
            "mnt_tot_igv_isc": 0.00,
            "mnt_tot_base_imponible": 0.00,
            "mnt_tot_percepcion": 0.00,
            "mnt_tot_a_percibir": 0.00,
            "mnt_tot": self.amount_total,
            "cod_operacion": "0101",
            "porcentaje_dscto": "",
            "mnt_anticipo": 0.00,
            "mnt_otros_cargos": 0.00,
            "tipo_percepcion": "",
            "porcentaje_percepcion": "",    
            "tipo_cambio": 0.00,
            "txt_condicion_pago": "20 dias",
            "flag_pagado": 0,
            "observaciones": "ambiente de produccion",
            "orden_compra": "",
            "guia_remision": ";;;",
            "flag_envio_automatico": 0,
            "guia_txt_cod_ubig": "", "guia_txt_dmcl_fisc": "", "guia_txt_urb": "", "guia_txt_prov": "", 
            "guia_txt_dpto": "", "guia_txt_distr": "", "guia_txt_pais": "", "guia_cod_ubig_llegda": "", 
            "guia_txt_dmcl_fisc_llegda": "", "guia_txt_urb_llegda": "", "guia_txt_prov_llegda": "", 
            "guia_txt_dpto_llegda": "", "guia_txt_distr_llegda": "", "guia_txt_pais_llegda": "", 
            "guia_txt_placa_auto_trnsp": "", "guia_txt_cert_auto_trnsp": "", "guia_txt_marca_auto_trnsp": "", 
            "guia_txt_lic_cond_trnsp": "", "guia_txt_ruc_trnsp": "", "guia_txt_cod_otr_trnsp": "", 
            "guia_txt_rzn_scl_trnsp": "", "guia_txt_cod_mod_trnsp": "", "guia_mnt_total_bruto": 0.00, 
            "guia_cod_unid_med": "", "dato_extra_1": "extra", "dato_extra_2": "extra", "dato_extra_3": "extra", 
            "dato_extra_4": "extra", "marca_expor": "", "origen_expor": "", "despacho_expor": "", 
            "soldto_expor": "", "shipto_expor": "", "numerocajas_expor": "", "pesobruto_expor": 0.00, 
            "pesoneto_expor": 0.00, "volumen_expor": 0.00, "fec_venci": "", "mnt_tot_detrac": 0.00, 
            "percent_detrac": "", "descrip_detrac": "", "num_cta_bn": "", "tip_detrac": "", "infos_detrac": "", 
            "txt_serie_anticipo": "", "txt_correlativo_anticipo": 0, "txt_cod_cpe_anticipo": "", 
            "mnt_tot_icbper": 0, "cod_tip_frmpgo": 1, "mnto_crdt_ttal": 0.00, "mnto_crdt_cta": 0.00, "fch_cta": "",
            "detalles": detalles
        }

        self._enviar_a_servicio(api_url, payload)

    # -------------------------------------------------------------------------
    # BOLETA (03)
    # -------------------------------------------------------------------------
    def _prepare_api_boleta(self):
        global ws_diario
        self.ensure_one()
        api_url = self.company_id.service_url

        #print("Ingreso Boleta:")

        Tax = 0.18
        TipTax = "IGV"
        cod_tip_afect_igv_item = 30
        mnt_tot_gravadas = 0.00
        mnt_tot_inafectas = 0.00
        mnt_tot_exoneradas = 0.00
        mnt_tot_gratuitas = 0.00

        detalles = []
        for i, line in enumerate(self.invoice_line_ids, start=1):
            tax_obj = line.tax_ids[:1]
            TipTax = tax_obj.tax_group_id.name if tax_obj else "IGV"
            Tax = (tax_obj.amount / 100) if tax_obj else 0.18

            if "IGV" in str(TipTax).upper():
                cod_tip_afect_igv_item = 10
            elif "EXO" in str(TipTax).upper():
                cod_tip_afect_igv_item = 20
            elif "INA" in str(TipTax).upper():
                cod_tip_afect_igv_item = 30
            else:
                cod_tip_afect_igv_item = 10

            detalles.append({
                "num_lin_item": i,
                "cod_unid_item": "NIU",
                "cant_unid_item": line.quantity,
                "val_vta_item": line.price_subtotal,
                "cod_tip_afect_igv_item": cod_tip_afect_igv_item,
                "prc_vta_unit_item": line.price_unit * (1.00 + Tax),
                "mnt_dscto_item": 0.00,
                "mnt_igv_item": line.price_subtotal * Tax,
                "txt_descr_item": line.name,
                "cod_prod_sunat": "31201501",
                "cod_item": str(line.product_id.default_code or ''),
                "val_unit_item": line.price_unit,
                "cod_tip_sist_isc": "",
                "mnt_isc_item": 0.00,
                "porcentaje_isc": "",
                "dato_extra_1": "",
                "dato_extra_2": "",
                "importe_total_item": line.price_subtotal * (1.00 + Tax),
                "val_unit_icbper": 0.00,
                "cant_icbper_item": 0.00,
                "mnt_icbper_item": 0.00
            })

            if cod_tip_afect_igv_item == 10:
                mnt_tot_gravadas += line.price_subtotal
            elif cod_tip_afect_igv_item == 30:
                mnt_tot_inafectas += line.price_subtotal
            elif cod_tip_afect_igv_item == 20:
                mnt_tot_exoneradas += line.price_subtotal

        # --- AQUI ESTA EL CAMBIO CLAVE ---
        txt_serie = self.journal_id.l10n_pe_serie 
        txt_correlativo = self._get_correlativo_sunat()
        #print("SERIE:", txt_serie)
        #print("SERIE:", txt_correlativo)

        payload = {
            "identificador": "BC",
            "fec_emis": (self.invoice_date or fields.Date.context_today(self)).strftime("%Y-%m-%d"),
            "hora_emis": "00:00:00",
            "txt_serie": txt_serie,          # <--- VARIABLE CONFIGURABLE
            "txt_correlativo": txt_correlativo, # <--- VARIABLE CONFIGURABLE
            "cod_tip_cpe": "03",
            "cod_mnd": self.currency_id.name,
            "cod_tip_escenario": "01",
            "txt_placa": "",
            "cod_cliente_emis": self.company_id.service_code or "",
            "num_ruc_emis": self.company_id.vat or "",
            "nom_rzn_soc_emis": self.company_id.name or "",
            "cod_tip_nif_emis": 6,
            "cod_loc_emis": 1,
            "cod_ubi_emis": 150122,
            "txt_dmcl_fisc_emis": self.company_id.street or "",
            "txt_urb_emis": "URB. CERCADO DE MIRAFLORES",
            "txt_prov_emis": self.company_id.state_id.name or "",
            "txt_dpto_emis": self.company_id.state_id.name or "",
            "txt_distr_emis": self.company_id.city or "",
            "num_iden_recp": self.partner_id.vat or "",
            "cod_tip_nif_recp": 6,
            "nom_rzn_soc_recp": self.partner_id.name or "Sin Razon Social",
            "txt_dmcl_fisc_recep": self.partner_id.street or "Sin dirección",
            "txt_correo_adquiriente": self.partner_id.email or "",
            "mnt_tot_gravadas": mnt_tot_gravadas,
            "mnt_tot_inafectas": mnt_tot_inafectas,
            "mnt_tot_exoneradas": mnt_tot_exoneradas,
            "mnt_tot_gratuitas": mnt_tot_gratuitas,
            "mnt_tot_desc_global": 0.00,
            "mnt_tot_igv": self.amount_tax,
            "mnt_tot_igv_isc": 0.00,
            "mnt_tot_base_imponible": 0.00,
            "mnt_tot_percepcion": 0.00,
            "mnt_tot_a_percibir": 0.00,
            "mnt_tot": self.amount_total,
            "cod_operacion": "0101",
            "porcentaje_dscto": "",
            "mnt_anticipo": 0.00,
            "mnt_otros_cargos": 0.00,
            "tipo_percepcion": "",
            "porcentaje_percepcion": "",    
            "tipo_cambio": 0.00,
            "txt_condicion_pago": "20 dias",
            "flag_pagado": 0,
            "observaciones": "ambiente de produccion",
            "orden_compra": "",
            "guia_remision": ";;;",
            "flag_envio_automatico": 0,
            "guia_txt_cod_ubig": "", "guia_txt_dmcl_fisc": "", "guia_txt_urb": "", "guia_txt_prov": "", 
            "guia_txt_dpto": "", "guia_txt_distr": "", "guia_txt_pais": "", "guia_cod_ubig_llegda": "", 
            "guia_txt_dmcl_fisc_llegda": "", "guia_txt_urb_llegda": "", "guia_txt_prov_llegda": "", 
            "guia_txt_dpto_llegda": "", "guia_txt_distr_llegda": "", "guia_txt_pais_llegda": "", 
            "guia_txt_placa_auto_trnsp": "", "guia_txt_cert_auto_trnsp": "", "guia_txt_marca_auto_trnsp": "", 
            "guia_txt_lic_cond_trnsp": "", "guia_txt_ruc_trnsp": "", "guia_txt_cod_otr_trnsp": "", 
            "guia_txt_rzn_scl_trnsp": "", "guia_txt_cod_mod_trnsp": "", "guia_mnt_total_bruto": 0.00, 
            "guia_cod_unid_med": "", "dato_extra_1": "extra", "dato_extra_2": "extra", "dato_extra_3": "extra", 
            "dato_extra_4": "extra", "marca_expor": "", "origen_expor": "", "despacho_expor": "", 
            "soldto_expor": "", "shipto_expor": "", "numerocajas_expor": "", "pesobruto_expor": 0.00, 
            "pesoneto_expor": 0.00, "volumen_expor": 0.00, "fec_venci": "", "mnt_tot_detrac": 0.00, 
            "percent_detrac": "", "descrip_detrac": "", "num_cta_bn": "", "tip_detrac": "", "infos_detrac": "", 
            "txt_serie_anticipo": "", "txt_correlativo_anticipo": 0, "txt_cod_cpe_anticipo": "", 
            "mnt_tot_icbper": 0, "cod_tip_frmpgo": 1, "mnto_crdt_ttal": 0.00, "mnto_crdt_cta": 0.00, "fch_cta": "",
            "detalles": detalles
        }
        self._enviar_a_servicio(api_url, payload)

    # -------------------------------------------------------------------------
    # NOTA DE CRÉDITO (07)
    # -------------------------------------------------------------------------
    def _prepare_api_notacredito(self):
        global ws_diario
        self.ensure_one()
        api_url = self.company_id.service_url

        #print("Ingreso NC:")

        mnt_tot_gravadas = 0.00
        mnt_tot_inafectas = 0.00
        mnt_tot_exoneradas = 0.00
        mnt_tot_gratuitas = 0.00
        Tax=0.18
        TipTax="IGV"

        factura_original = self.reversed_entry_id

        detalles = []
        for i, line in enumerate(self.invoice_line_ids, start=1):
            tax_obj = line.tax_ids[:1]
            TipTax = tax_obj.tax_group_id.name if tax_obj else "IGV"
            Tax = (tax_obj.amount / 100) if tax_obj else 0.18

            if "IGV" in str(TipTax).upper(): cod_tip_afect_igv_item = 10
            elif "EXO" in str(TipTax).upper(): cod_tip_afect_igv_item = 20
            elif "INA" in str(TipTax).upper(): cod_tip_afect_igv_item = 30
            else: cod_tip_afect_igv_item = 10

            detalles.append({
                "num_lin_item": i,
                "cod_unid_item": "NIU",
                "cant_unid_item": line.quantity,
                "val_vta_item": line.price_subtotal,
                "cod_tip_afect_igv_item": cod_tip_afect_igv_item,
                "prc_vta_unit_item": line.price_unit * (1.00 + Tax),
                "mnt_dscto_item": 0.00,
                "mnt_igv_item": line.price_subtotal * Tax,
                "txt_descr_item": line.name,
                "cod_prod_sunat": "31201501",
                "cod_item": str(line.product_id.default_code or ''),
                "val_unit_item": line.price_unit,
                "cod_tip_sist_isc": "",
                "mnt_isc_item": 0.00,
                "porcentaje_isc": "",
                "dato_extra_1": "",
                "dato_extra_2": "",
                "importe_total_item": line.price_subtotal * (1.00 + Tax),
                "val_unit_icbper": 0.00,
                "cant_icbper_item": 0.00,
                "mnt_icbper_item": 0.00
            })

            if cod_tip_afect_igv_item == 10: mnt_tot_gravadas += line.price_subtotal
            elif cod_tip_afect_igv_item == 30: mnt_tot_inafectas += line.price_subtotal
            elif cod_tip_afect_igv_item == 20: mnt_tot_exoneradas += line.price_subtotal

        # --- CONFIGURACIÓN DE SERIE PARA NC ---
        # El usuario debe haber seleccionado un diario de "Nota de Crédito" con la serie correcta (ej. FC01)
        txt_serie = self.journal_id.l10n_pe_serie
        txt_correlativo = self._get_correlativo_sunat()
        #print("SERIE:", txt_serie)
        #print("SERIE:", txt_correlativo)

        # Datos de la factura afectada
        # Aquí obtenemos la serie ORIGINAL de la factura que se está anulando
        serie_ref = factura_original.journal_id.l10n_pe_serie or "F000"
        correlativo_ref = factura_original._get_correlativo_sunat()

        payload = {
            "identificador": "CC",
            "fec_emis": (self.invoice_date or fields.Date.context_today(self)).strftime("%Y-%m-%d"),
            "hora_emis": "00:00:00",
            "txt_serie": txt_serie,          # <--- VARIABLE CONFIGURABLE (Del diario actual de NC)
            "txt_correlativo": txt_correlativo, # <--- VARIABLE CONFIGURABLE
            "cod_tip_cpe": "07",
            "cod_mnd": self.currency_id.name,
            "cod_tip_escenario": "01",
            "txt_placa": "",
            "cod_cliente_emis": self.company_id.service_code or "",
            "num_ruc_emis": self.company_id.vat or "",
            "nom_rzn_soc_emis": self.company_id.name or "",
            "cod_tip_nif_emis": 6,
            "cod_loc_emis": 1,
            "cod_ubi_emis": 150122,
            "txt_dmcl_fisc_emis": self.company_id.street or "",
            "txt_urb_emis": "URB. CERCADO DE MIRAFLORES",
            "txt_prov_emis": self.company_id.state_id.name or "",
            "txt_dpto_emis": self.company_id.state_id.name or "",
            "txt_distr_emis": self.company_id.city or "",
            "num_iden_recp": self.partner_id.vat or "",
            "cod_tip_nif_recp": 6,
            "nom_rzn_soc_recp": self.partner_id.name or "Sin Razon Social",
            "txt_dmcl_fisc_recep": self.partner_id.street or "Sin dirección",
            "txt_correo_adquiriente": self.partner_id.email or "",
            "mnt_tot_gravadas": mnt_tot_gravadas,
            "mnt_tot_inafectas": mnt_tot_inafectas,
            "mnt_tot_exoneradas": mnt_tot_exoneradas,
            "mnt_tot_gratuitas": mnt_tot_gratuitas,
            "mnt_tot_desc_global": 0.00,
            "mnt_tot_igv": self.amount_tax,
            "mnt_tot_igv_isc": 0.00,
            "mnt_tot_base_imponible": 0.00,
            "mnt_tot_percepcion": 0.00,
            "mnt_tot_a_percibir": 0.00,
            "mnt_tot": self.amount_total,
            "cod_tip_nc_nd_ref": "01",
            "txt_serie_ref": serie_ref,          # <--- Dinámico de la factura original
            "txt_correlativo_cpe_ref": correlativo_ref, # <--- Dinámico de la factura original
            "fec_emis_ref": factura_original.invoice_date.strftime("%Y-%m-%d"),
            "cod_cpe_ref": "01", 
            "txt_sustento": self.ref or "Devolucion",
            "cod_operacion": "0101",
            "porcentaje_dscto": "",
            "mnt_anticipo": 0.00,
            "mnt_otros_cargos": 0.00,
            "tipo_percepcion": "",
            "porcentaje_percepcion": "",    
            "tipo_cambio": 0.00,
            "observaciones": "Nota de Credito",
            "flag_envio_automatico": 1,
            "dato_extra_1": "extra", "dato_extra_2": "extra", "dato_extra_3": "extra", "dato_extra_4": "extra",
            "mnt_tot_icbper": 0.00,
            "cod_tip_frmpgo": 1,
            "mnto_crdt_ttal": 0.00,
            "mnto_crdt_cta": 0.00,
            "fch_cta": 0,          
            "detalles": detalles
        }
        self._enviar_a_servicio(api_url, payload)

    # -------------------------------------------------------------------------
    # NOTA DE DÉBITO (08)
    # -------------------------------------------------------------------------
    def _prepare_api_notadebito(self):
        # Importar UserError para mensajes amigables (asegúrate de tener esto arriba en tu archivo)
        from odoo.exceptions import UserError
        
        global ws_diario
        self.ensure_one()
        api_url = self.company_id.service_url

        #print("Ingreso ND:")

        # --- CORRECCIÓN 1: Búsqueda robusta del documento original ---
        # Primero buscamos en el campo estándar de Nota de Débito, si falla, buscamos en el de reversión
        factura_original = self.debit_origin_id or self.reversed_entry_id
        
        # --- CORRECCIÓN 2: Validación obligatoria ---
        if not factura_original:
             # Intento final: buscar por el campo 'ref' si tiene el formato SERIE-CORRELATIVO
             if self.ref and '-' in self.ref:
                 factura_original = self.env['account.move'].search([
                     ('name', '=', self.ref),
                     ('company_id', '=', self.company_id.id)
                 ], limit=1)
        
        if not factura_original:
            raise UserError("Error de Validación: No se ha encontrado el Comprobante de Pago original (Factura o Boleta) "
                            "al cual hace referencia esta Nota de Débito.\n\n"
                            "Asegúrese de haber creado este documento usando el botón 'Añadir nota de débito' "
                            "o verifique que el campo 'Documento Origen' esté lleno.")

        mnt_tot_gravadas = 0.00
        mnt_tot_inafectas = 0.00
        mnt_tot_exoneradas = 0.00
        mnt_tot_gratuitas = 0.00
        Tax=0.18
        TipTax="IGV"

        detalles = []
        for i, line in enumerate(self.invoice_line_ids, start=1):
            tax_obj = line.tax_ids[:1]
            TipTax = tax_obj.tax_group_id.name if tax_obj else "IGV"
            Tax = (tax_obj.amount / 100) if tax_obj else 0.18

            if "IGV" in str(TipTax).upper(): cod_tip_afect_igv_item = 10
            elif "EXO" in str(TipTax).upper(): cod_tip_afect_igv_item = 20
            elif "INA" in str(TipTax).upper(): cod_tip_afect_igv_item = 30
            else: cod_tip_afect_igv_item = 10

            detalles.append({
                "num_lin_item": i,
                "cod_unid_item": "NIU",
                "cant_unid_item": line.quantity,
                "val_vta_item": line.price_subtotal,
                "cod_tip_afect_igv_item": cod_tip_afect_igv_item,
                "prc_vta_unit_item": line.price_unit * (1.00 + Tax),
                "mnt_dscto_item": 0.00,
                "mnt_igv_item": line.price_subtotal * Tax,
                "txt_descr_item": line.name,
                "cod_prod_sunat": "31201501",
                "cod_item": str(line.product_id.default_code or ''),
                "val_unit_item": line.price_unit,
                "cod_tip_sist_isc": "",
                "mnt_isc_item": 0.00,
                "porcentaje_isc": "",
                "dato_extra_1": "",
                "dato_extra_2": "",
                "importe_total_item": line.price_subtotal * (1.00 + Tax),
                "val_unit_icbper": 0.00,
                "cant_icbper_item": 0.00,
                "mnt_icbper_item": 0.00
            })

            if cod_tip_afect_igv_item == 10: mnt_tot_gravadas += line.price_subtotal
            elif cod_tip_afect_igv_item == 30: mnt_tot_inafectas += line.price_subtotal
            elif cod_tip_afect_igv_item == 20: mnt_tot_exoneradas += line.price_subtotal

        # Parametrización ND
        txt_serie = self.journal_id.l10n_pe_serie 
        txt_correlativo = self._get_correlativo_sunat()
        #print("SERIE:", txt_serie)
        #print("CORRELATIVO:", txt_correlativo)
        
        # Datos de Referencia (Seguros)
        serie_ref = factura_original.journal_id.l10n_pe_serie or "F000"
        correlativo_ref = factura_original._get_correlativo_sunat() # Asumiendo que esta funcion existe en tu modelo
        
        # --- CORRECCIÓN 3: Fecha segura ---
        fecha_ref = factura_original.invoice_date or fields.Date.context_today(self)
        
        # Detectar si el original es Factura (01) o Boleta (03)
        # Esto es importante porque SUNAT valida que coincida
        cod_cpe_ref_val = "01" 
        if factura_original.l10n_latam_document_type_id.code == '03':
            cod_cpe_ref_val = "03"

        payload = {
            "identificador": "DC",
            "fec_emis": (self.invoice_date or fields.Date.context_today(self)).strftime("%Y-%m-%d"),
            "hora_emis": "00:00:00",
            "txt_serie": txt_serie,
            "txt_correlativo": txt_correlativo,
            "cod_tip_cpe": "08", # Nota de Debito
            "cod_mnd": self.currency_id.name,
            "cod_tip_escenario": "01",
            "txt_placa": "",
            "cod_cliente_emis": self.company_id.service_code or "",
            "num_ruc_emis": self.company_id.vat or "",
            "nom_rzn_soc_emis": self.company_id.name or "",
            "cod_tip_nif_emis": 6,
            "cod_loc_emis": 1,
            "cod_ubi_emis": 150122,
            "txt_dmcl_fisc_emis": self.company_id.street or "",
            "txt_urb_emis": "URB. CERCADO DE MIRAFLORES",
            "txt_prov_emis": self.company_id.state_id.name or "",
            "txt_dpto_emis": self.company_id.state_id.name or "",
            "txt_distr_emis": self.company_id.city or "",
            "num_iden_recp": self.partner_id.vat or "",
            "cod_tip_nif_recp": 6,
            "nom_rzn_soc_recp": self.partner_id.name or "Sin Razon Social",
            "txt_dmcl_fisc_recep": self.partner_id.street or "Sin dirección",
            "txt_correo_adquiriente": self.partner_id.email or "",
            "mnt_tot_gravadas": mnt_tot_gravadas,
            "mnt_tot_inafectas": mnt_tot_inafectas,
            "mnt_tot_exoneradas": mnt_tot_exoneradas,
            "mnt_tot_gratuitas": mnt_tot_gratuitas,
            "mnt_tot_desc_global": 0.00,
            "mnt_tot_igv": self.amount_tax,
            "mnt_tot_igv_isc": 0.00,
            "mnt_tot_base_imponible": 0.00,
            "mnt_tot_percepcion": 0.00,
            "mnt_tot_a_percibir": 0.00,
            "mnt_tot": self.amount_total,
            "cod_tip_nc_nd_ref": "01", # Codigo de motivo SUNAT (Interes por mora, etc)
            "txt_serie_ref": serie_ref,
            "txt_correlativo_cpe_ref": correlativo_ref,
            "fec_emis_ref": fecha_ref.strftime("%Y-%m-%d"), # <--- YA NO FALLARÁ AQUÍ
            "cod_cpe_ref": cod_cpe_ref_val, # <--- Ahora dinámico (01 o 03)
            "txt_sustento": self.ref or "Interes por mora",
            "cod_operacion": "0101",
            "porcentaje_dscto": "",
            "mnt_anticipo": 0.00,
            "mnt_otros_cargos": 0.00,
            "tipo_percepcion": "",
            "porcentaje_percepcion": "",    
            "tipo_cambio": 0.00,
            "observaciones": "Nota de Debito",
            "flag_envio_automatico": 1,
            "dato_extra_1": "extra", "dato_extra_2": "extra", "dato_extra_3": "extra", "dato_extra_4": "extra",
            "mnt_tot_icbper": 0.00,
            "detalles": detalles
        }
        self._enviar_a_servicio(api_url, payload)


    # -------------------------------------------------------------------------
    # ENVÍO GENÉRICO (Para evitar repetir el request)
    # -------------------------------------------------------------------------
    def _enviar_a_servicio(self, api_url, payload):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': self.company_id.service_token
        }
        try:
            response = requests.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            _logger.info("Respuesta del WS simulado: %s", data)

            if isinstance(data, dict):
                is_valid = data.get('Resultado', False)
                error_msg = data.get('Mensaje', 'Error no especificado')
                if bool(is_valid):
                    self.ws_response = "✅ Validado por API"
                else:
                    self.ws_response = f"❌ Error: {error_msg}"
            else:
                self.ws_response = "🔴 Respuesta del API no válida"
                _logger.error("La respuesta del API no es un diccionario: %s", str(data))

        except Exception as e:
            _logger.error("Error al llamar al WS: %s", str(e))
            self.ws_response = f"Error: {str(e)}"

    # -------------------------------------------------------------------------
    # FUNCIONES DE DEBUG / VISUALIZACIÓN
    # -------------------------------------------------------------------------
      # --- Método del botón ---
    def _prepare_invoice_payload(self):
        """Genera el diccionario con los datos de la factura para el API."""
        global  ws_diario

        self.ensure_one()

        #Estas Variables se utilizan para totalizar un documento dependiente de si la transaccion
        #tiene IGV o es inafecto, exonerado o gratuito
        mnt_tot_gravadas= 0.00
        mnt_tot_inafectas = 0.00
        mnt_tot_exoneradas = 0.00
        mnt_tot_gratuitas = 0.00

        Tax=0.18
       
        # Busca el diario (ej: Diario de Ventas)
        #ws_diario = self.env['account.journal'].search([], limit=1)

        # --- AQUI ESTA EL CAMBIO CLAVE ---
        # Leemos la serie directamente del diario configurado por el usuario
        txt_serie = self.journal_id.l10n_pe_serie 
        # El correlativo viene de la secuencia automática de Odoo
        txt_correlativo = self._get_correlativo_sunat()

        return {
            'invoice': {
                    # "serie": ws_diario.code,
                    # "fec_emis": (self.invoice_date or fields.Date.context_today(self)).strftime("%Y-%m-%d"),
                    # "txt_correlativo": self.name, #self.name[2:], #'00000036',
                    # "txt_correlativo": self.name if self.name and self.name != '/' else "", #self.name, #, #"00000077",
                    # "cod_mnd": self.currency_id.name, #"PEN",
                    # "num_iden_recp": self.partner_id.vat or "Sin RUC", #"20600184718",
                    # "nom_rzn_soc_recp": self.partner_id.complete_name or "Sin Razon Social", #"AquaJet Store SAC -",
                    # "txt_dmcl_fisc_recep": self.partner_id.contact_address or "Sin dirección", #"AV ABANCAY 176",
                    # "mnt_tot_gravadas": self.amount_untaxed,
                    # "mnt_tot_igv":  self.amount_tax,
                    # "mnt_tot": self.amount_total,

                    "identificador": "FC",
                    "fec_emis": (self.invoice_date or fields.Date.context_today(self)).strftime("%Y-%m-%d"),
                    "hora_emis": "00:00:00",
                    "txt_serie": txt_serie, #ws_diario.code, #self.sequence_prefix, #, #"F001",
                    #"txt_correlativo": self.name[5:], #self.name, #, #"00000077",
                    "txt_correlativo": txt_correlativo, #self.name[5:] if self.name and self.name != '/' else "", #self.name, #, #"00000077",
                    "cod_tip_cpe": "01",
                    "cod_mnd": self.currency_id.name, #"PEN",
                    "cod_tip_escenario": "01",
                    "txt_placa": "",
                    "cod_cliente_emis": self.company_id.service_code or "", #self.company_id.service_code or "", #799,
                    "num_ruc_emis": self.company_id.vat or "", #"20603073828",
                    "nom_rzn_soc_emis": self.company_id.name or "", #"BYBCOM",
                    "cod_tip_nif_emis": 6,
                    "cod_loc_emis": 1,
                    "cod_ubi_emis": 150122,
                    "txt_dmcl_fisc_emis": self.company_id.street or "", #"PJ. MARTIR JOSE OLAYA",
                    "txt_urb_emis": "URB. CERCADO DE MIRAFLOR",
                    "txt_prov_emis": self.company_id.state_id.name or "", #"LIMA",
                    "txt_dpto_emis": self.company_id.state_id.name or "", #"LIMA",
                    "txt_distr_emis": self.company_id.city, #"MIRAFLORES",
                    "num_iden_recp": self.partner_id.vat or "", #"20600184718",
                    "cod_tip_nif_recp": 6,
                    "nom_rzn_soc_recp": self.partner_id.complete_name or "Sin Razon Social", #"AquaJet Store SAC -",
                    "txt_dmcl_fisc_recep": self.partner_id.street or "Sin dirección", #"AV ABANCAY 176",
                    "txt_correo_adquiriente": self.partner_id.email, #"soporte@itc.com.pe",
                    "mnt_tot_gravadas":   self.amount_untaxed,#100.00, #self.amount_untaxed,
                    "mnt_tot_inafectas": mnt_tot_inafectas, #0
                    "mnt_tot_exoneradas": mnt_tot_exoneradas, #0
                    "mnt_tot_gratuitas": mnt_tot_gratuitas, #0
                    "mnt_tot_desc_global": 0.00,
                    "mnt_tot_igv": self.amount_tax, #18.00,
                    "mnt_tot_igv_isc": 0.00,
                    "mnt_tot_base_imponible": 0.00,
                    "mnt_tot_percepcion": 0.00,
                    "mnt_tot_a_percibir": 0.00,
                    "mnt_tot": self.amount_total, #118.00,
                    "cod_operacion": "0101",
                    "porcentaje_dscto": "",
                    "mnt_anticipo": 0.00,
                    "mnt_otros_cargos": 0.00,
                    "tipo_percepcion": "",
                    "porcentaje_percepcion": "",    
                    "tipo_cambio": 0.00,
                    "txt_condicion_pago": "20 dias",
                    "flag_pagado": 0,
                    "observaciones": "ambiente de produccion",
                    "orden_compra": "",
                    "guia_remision": ";;;",
                    "flag_envio_automatico": 0,
                    "guia_txt_cod_ubig": "",
                    "guia_txt_dmcl_fisc": "",
                    "guia_txt_urb": "",
                    "guia_txt_prov": "",
                    "guia_txt_dpto": "",
                    "guia_txt_distr": "",
                    "guia_txt_pais": "",
                    "guia_cod_ubig_llegda": "", 
                    "guia_txt_dmcl_fisc_llegda": "",    
                    "guia_txt_urb_llegda": "",
                    "guia_txt_prov_llegda": "",
                    "guia_txt_dpto_llegda": "",
                    "guia_txt_distr_llegda": "",
                    "guia_txt_pais_llegda": "",
                    "guia_txt_placa_auto_trnsp": "",    
                    "guia_txt_cert_auto_trnsp": "",
                    "guia_txt_marca_auto_trnsp": "",
                    "guia_txt_lic_cond_trnsp": "",
                    "guia_txt_ruc_trnsp": "",
                    "guia_txt_cod_otr_trnsp": "",
                    "guia_txt_rzn_scl_trnsp": "",
                    "guia_txt_cod_mod_trnsp": "",
                    "guia_mnt_total_bruto": 0.00,
                    "guia_cod_unid_med": "",
                    "dato_extra_1": "extra",
                    "dato_extra_2": "extra",
                    "dato_extra_3": "extra",
                    "dato_extra_4": "extra",
                    "marca_expor": "",
                    "origen_expor": "",
                    "despacho_expor": "",
                    "soldto_expor": "",
                    "shipto_expor": "",
                    "numerocajas_expor": "",    
                    "pesobruto_expor": 0.00,
                    "pesoneto_expor": 0.00,
                    "volumen_expor": 0.00,
                    "fec_venci": "",
                    "mnt_tot_detrac": 0.00,
                    "percent_detrac": "",
                    "descrip_detrac": "",
                    "num_cta_bn": "",
                    "tip_detrac": "",
                    "infos_detrac": "",
                    "txt_serie_anticipo":"",
                    "txt_correlativo_anticipo":0,
                    "txt_cod_cpe_anticipo":"",
                    "mnt_tot_icbper": 0.00,
                    "mnt_tot_icbper":0,
                    "cod_tip_frmpgo": 1,
                    "mnto_crdt_ttal": 0.00,
                    "retencion_codigo":"",
                    "retencion_factor":0,
                    "retencion_base":0,

            },
            'lines': [
                {
                    # "Tipo IGV" :line.tax_ids.tax_group_id.name,
                    # "IGV" :line.tax_ids.amount,
                    # 'description': line.name,
                    # "cant_unid_item": line.quantity,
                    # "val_vta_item": line.price_subtotal, #40.00,
                    # "cod_tip_afect_igv_item": 10,
                    # "prc_vta_unit_item": line.price_unit * (1.00 + line.tax_ids.amount/100), #11.80,
                    # "mnt_dscto_item": 0.00,
                    # "mnt_igv_item": line.price_subtotal * (line.tax_ids.amount/100), #7.20,
                    # "txt_descr_item": line.name, #"zapatos",
                    # "cod_prod_sunat": "31201501",
                    # "cod_item": str(line.product_id),#"00001",
                    # "val_unit_item": line.price_unit, #10.0,
                    # "cod_tip_sist_isc": "",
                    # "mnt_isc_item": 0.00,
                    # "porcentaje_isc": "",
                    # "dato_extra_1": "",
                    # "dato_extra_2": "",
                    # "importe_total_item": line.price_subtotal * (1.00 + line.tax_ids.amount/100), #47.20,
                    # "val_unit_icbper": 0.00,
                    # "cant_icbper_item": 0.00,
                    # "mnt_icbper_item": 0.00,

                    "num_lin_item": 1, #i,  #1,
                    "cod_unid_item": "NIU",
                    "cant_unid_item": line.quantity, #3, cantidad del item solicitado
                    #val_vta_item = precio total de item solicitados sin igv: 3und x 10S/ = 30
                    "val_vta_item": line.price_subtotal, #30.00, 
                    "cod_tip_afect_igv_item": 10, #cod_tip_afect_igv_item, #10, 
                    #prc_vta_unit_item = valor unitario de un item mas igv: 10 x 1.18 = 11.80
                    "prc_vta_unit_item": line.price_unit * (1.00 + Tax), #round(line.price_unit * (self.amount_total / self.amount_untaxed),2), #11.80, 
                    "mnt_dscto_item": 0.00,
                    #mnt_igv_item = Solo IGV del total de item vendido = 3und x 10Soles * 0.18 = 5.40
                    "mnt_igv_item": line.price_subtotal * Tax, #round(line.price_subtotal * ((self.amount_total / self.amount_untaxed)-1),2), #5.40,
                    "txt_descr_item": line.name, #"Cartera",
                    "cod_prod_sunat": "31201501",
                    "cod_item": str(line.product_id), #"00001", codigo del producto
                    "val_unit_item": line.price_unit, #10.00, valor unitario de cada item
                    "cod_tip_sist_isc": "",
                    "mnt_isc_item": 0.00,
                    "porcentaje_isc": "",
                    "dato_extra_1": "",
                    "dato_extra_2": "",
                    #importe_total_item = Precio total de item solicitados más igv: 3und x 10S/ x 1.18 =35.40
                    "importe_total_item": line.price_subtotal * (1.00 + Tax), #round(line.price_subtotal *(self.amount_total / self.amount_untaxed),2), #35.40,
                    "val_unit_icbper": 0.00,
                    "cant_icbper_item": 0.00,
                    "mnt_icbper_item": 0.00

                }
                for line in self.invoice_line_ids
            ]
        }
    

    
    def _prepare_invoice_payloadNC(self):
        """Genera el diccionario con los datos de la factura para el API."""
        global ws_diario 

        self.ensure_one()

        Tax=0.18

        # Busca el diario (ej: Diario de Ventas)
        ws_diario = self.env['account.journal'].search([], limit=1)


        """Obtiene Datos de la Factura."""
        factura_original = self.reversed_entry_id
        return {
            'invoice': {
            "serie": ws_diario.code,
            "identificador": "CC",
            "fec_emis": (self.invoice_date or fields.Date.context_today(self)).strftime("%Y-%m-%d"),
            "txt_serie": self.journal_id.l10n_pe_serie, #"F001",
            #"txt_correlativo": self.name, #self.name[2:], #"00000077",
            "txt_correlativo": self.name if self.name and self.name != '/' else "", #self.name, #, #"00000077",
            "cod_tip_cpe": "07",
            "cod_mnd": self.currency_id.name, #"PEN",
            "cod_tip_escenario": "01",
            "cod_cliente_emis": self.company_id.service_code or "", #self.company_id.service_code or "", #799,
            "num_ruc_emis": self.company_id.vat or "", #"20603073828",
            "nom_rzn_soc_emis": self.company_id.name or "", #"BYBCOM",
            "cod_tip_nif_emis": 6,
            "cod_loc_emis": 1,
            "cod_ubi_emis": 150122,
            "txt_dmcl_fisc_emis": self.company_id.street or "", #"PJ. MARTIR JOSE OLAYA",
            "txt_prov_emis": self.company_id.state_id.name or "", #"LIMA",
            "txt_dpto_emis": self.company_id.state_id.name or "", #"LIMA",
            "txt_distr_emis": self.company_id.city, #"MIRAFLORES",
            "num_iden_recp": self.partner_id.vat or "", #"20600184718",
            "cod_tip_nif_recp": 6,
            "nom_rzn_soc_recp": self.partner_id.complete_name or "Sin Razon Social", #"AquaJet Store SAC -",
            "txt_dmcl_fisc_recep": self.partner_id.street or "Sin dirección", #"AV ABANCAY 176",
            "txt_correo_adquiriente": self.partner_id.email, #"soporte@itc.com.pe",
            "mnt_tot_gravadas": self.amount_untaxed, #100.00,
            "mnt_tot_igv": self.amount_tax, #18.00,
            "mnt_tot": self.amount_total, #118.00,
            "cod_tip_nc_nd_ref": "01",  #codigo nota de credito
            "txt_serie_ref": "F001", #serie de documento afectado
            "txt_correlativo_cpe_ref": factura_original.name, #factura_original.name[2:], #"00000091", #correlativo de documento afectado
            "fec_emis_ref":factura_original.invoice_date.strftime("%Y-%m-%d"), #"2025-06-11", #Fecha de emision del documento relacionado
            "cod_cpe_ref":"01", #codigo de tipo de documento afectado
            "txt_sustento":self.ref, #"equivocacion", #Motivo y/o descripcion de la Nota
            },
            'lines': 
                [{
                "cod_unid_item": "NIU",
                "cant_unid_item": line.quantity, #3,
                "val_vta_item": line.price_subtotal, #30.00,
                "cod_tip_afect_igv_item": 10,
                "prc_vta_unit_item": line.price_unit * (1.00 + Tax), #11.80,
                "mnt_igv_item": line.price_subtotal * (Tax), #5.40,
                "txt_descr_item": line.name, #"Cartera",
                "cod_prod_sunat": "31201501",
                "cod_item": str(line.product_id), #"00001", #ver la posibilidad que sea el codigo del producto
                "val_unit_item": line.price_unit, #10.00,
                "importe_total_item": line.price_subtotal * (1.00 + Tax), #35.40,
                }
                for line in self.invoice_line_ids
            ]
        }
    
    def action_show_payload(self):
        self.ensure_one()
        lines_info = [f"Línea {i+1}: {line.name}\nSubtotal: {line.price_subtotal}" for i, line in enumerate(self.invoice_line_ids)]
        debug_rec = self.env['payload.debug'].create({
            'invoice_id': self.id,
            'payload_data': json.dumps(self._prepare_invoice_payload(), indent=2),
            'line_details': "\n\n".join(lines_info)
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Detalle del Payload',
            'view_mode': 'form',
            'res_model': 'payload.debug',
            'res_id': debug_rec.id,
            'target': 'new',
        }
    
    def action_show_payloadNC(self):
        self.ensure_one()
        lines_info = [f"Línea {i+1}: {line.name}\nSubtotal: {line.price_subtotal}" for i, line in enumerate(self.invoice_line_ids)]
        debug_rec = self.env['payload.debug'].create({
            'invoice_id': self.id,
            'payload_data': json.dumps(self._prepare_invoice_payloadNC(), indent=2),
            'line_details': "\n\n".join(lines_info)
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Detalle del Payload',
            'view_mode': 'form',
            'res_model': 'payload.debug',
            'res_id': debug_rec.id,
            'target': 'new',
        }