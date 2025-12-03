
from odoo import models, fields, api
import requests
import logging
import json



_logger = logging.getLogger(__name__)



##INICIO
class AccountMove(models.Model):
    _inherit = 'account.move'

    """ Aqui se crea el campo en la BD con el nombre ws_response para almacenar la respuesta del WS """
    ws_response = fields.Char(string="Respuesta WS", readonly=True)

    #esta variable se utilizará para poder saber la serie del documento Fa, Bo, Nc
    # a través de su asiento diario
    ws_diario = ""

    """ Aqui se crea el campo en la BD con el nombre SerieCorre para almacenar la Serie del Correlativo """
    #ws_seriecorre = fields.Char(string="Serie Correlativo", readonly=True)

    #def action_post(self):
    def action_fe_payload(self):
        """Genera el diccionario con los datos de la factura para el API."""
        global  ws_diario

        res = super().action_post()
        
        #     """ Llama al WS para validar la factura """    
        #    Se ejecjuta el WS cuando presionamos el boton de confirmar Documento
        if self.move_type == 'out_invoice' and self.l10n_latam_document_type_id.code == '01': # and self.invoice_payment_state == 'paid':
             ws_diario = self.env['account.journal'].search([('name', 'ilike', 'Facturas de clientes')], limit=1)
             self._prepare_api_factura()
        elif self.move_type == 'out_invoice' and self.l10n_latam_document_type_id.code == '03': # and self.invoice_payment_state == 'paid':
              ws_diario = self.env['account.journal'].search([('name', 'ilike', 'Boletas de Clientes')], limit=1)
              self._prepare_api_boleta()
        elif self.move_type == 'out_refund' and self.l10n_latam_document_type_id.code == '07': # and self.invoice_payment_state == 'paid':
              ws_diario = self.env['account.journal'].search([('name', 'ilike', 'Facturas de clientes')], limit=1)
              self._prepare_api_notacredito()
        elif self.move_type == 'out_invoice' and self.l10n_latam_document_type_id.code == '08': # and self.invoice_payment_state == 'paid':
              ws_diario = self.env['account.journal'].search([('name', 'ilike', 'Facturas de clientes')], limit=1)
              self._prepare_api_notadebito()
        return res
    

    def _prepare_api_factura(self):
        """Genera el diccionario con los datos de la factura para el API."""
        global  ws_diario

        """ Método para consumir el WS de prueba """
        #api_url = "http://localhost:5000/validate_invoice"
        api_url = "https://testsee.itc.com.pe/api/billservice"

        """Genera el JSON en el formato específico requerido."""
        self.ensure_one()

        
        #Esta Variable se utilizan para saber el valor del Impuesto(IGV)
        Tax=0.18

        #Esta Variable se utilizan para saber el valor del tipo de impuesto, igv, inafecto, exonerado
        TipTax="IGV"

        #Esta Variable se utilizan para saber si un documento está afecto al IGV(cod 10)
        cod_tip_afect_igv_item=30

        #Estas Variables se utilizan para totalizar un documento dependiente de si la transaccion
        #tiene IGV o es inafecto, exonerado o gratuito
        mnt_tot_gravadas= 0.00
        mnt_tot_inafectas = 0.00
        mnt_tot_exoneradas = 0.00
        mnt_tot_gratuitas = 0.00

        #-----DETALLE----
        detalles = []
        for i, line in enumerate(self.invoice_line_ids, start=1):
            TipTax = line.tax_ids.tax_group_id.name,
            Tax = line.tax_ids.amount/100, #debo probar poniendo esta linea en el mismo detalle

            if TipTax[0] == "IGV" :
                cod_tip_afect_igv_item=10
            elif TipTax[0] == "EXO" :
                cod_tip_afect_igv_item = 20
            elif TipTax[0] == "INA" :
                cod_tip_afect_igv_item = 30

            detalles.append({
                "num_lin_item": i,  #1,
                "cod_unid_item": "NIU",
                "cant_unid_item": line.quantity, #3, cantidad del item solicitado
                #val_vta_item = precio total de item solicitados sin igv: 3und x 10S/ = 30
                "val_vta_item": line.price_subtotal, #30.00, 
                "cod_tip_afect_igv_item": cod_tip_afect_igv_item, #10, 
                #prc_vta_unit_item = valor unitario de un item mas igv: 10 x 1.18 = 11.80
                "prc_vta_unit_item": line.price_unit * (1.00 + Tax[0]), #round(line.price_unit * (self.amount_total / self.amount_untaxed),2), #11.80, 
                "mnt_dscto_item": 0.00,
                #mnt_igv_item = Solo IGV del total de item vendido = 3und x 10Soles * 0.18 = 5.40
                "mnt_igv_item": line.price_subtotal * Tax[0], #round(line.price_subtotal * ((self.amount_total / self.amount_untaxed)-1),2), #5.40,
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
                "importe_total_item": line.price_subtotal * (1.00 + Tax[0]), #round(line.price_subtotal *(self.amount_total / self.amount_untaxed),2), #35.40,
                "val_unit_icbper": 0.00,
                "cant_icbper_item": 0.00,
                "mnt_icbper_item": 0.00
             })
            
        # --- CABECERA ---
        #self.ws_seriecorre=ws_diario.code

        if TipTax[0] == "IGV" :
            mnt_tot_gravadas=self.amount_untaxed
        elif TipTax[0] == "INA" :
            mnt_tot_inafectas = self.amount_untaxed
        elif TipTax[0] == "EXO" :
            mnt_tot_exoneradas = self.amount_untaxed
        elif TipTax[0] == "GRA" :
            mnt_tot_gratuitas = self.amount_untaxed
        else :
            mnt_tot_exoneradas = 0
        
        payload = {
            "identificador": "FC",
            "fec_emis": self.invoice_date.strftime("%Y-%m-%d"), #"2025-06-05",
            "hora_emis": "00:00:00",
            "txt_serie": ws_diario.code, #self.sequence_prefix, #, #"F001",
            "txt_correlativo": self.name[5:], #self.name, #, #"00000077",
            "cod_tip_cpe": "01",
            "cod_mnd": self.currency_id.name, #"PEN",
            "cod_tip_escenario": "01",
            "txt_placa": "",
            "cod_cliente_emis": 799,
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
            "mnt_tot_gravadas":   mnt_tot_gravadas,#100.00, #self.amount_untaxed,
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
            "observaciones": "ambiente de prueba",
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
            "detalles": detalles
        }
       

        headers = {
                'Content-Type': 'application/json',
                'Authorization': f'WsC0nexBYB@:YQSa3C13gQKQb3LbLUdG2w==',  # ⭐¡Aquí va el token!
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
            

            if isinstance(data, dict):  # Primero verifica que data sea un diccionario
                is_valid = data.get('Resultado', False)  # Valor por defecto False si no existe
                error_msg = data.get('Mensaje', 'Error no especificado')  # Mensaje por defecto
                
                if bool(is_valid):  # Asegura que is_valid sea booleano
                    self.ws_response = "✅ Validado por API"
                else:
                    self.ws_response = f"❌ Error: {error_msg}"
            else:
                self.ws_response = "🔴 Respuesta del API no válida"
                _logger.error("La respuesta del API no es un diccionario: %s", str(data))

        except Exception as e:
                _logger.error("Error al llamar al WS: %s", str(e))
                self.ws_response = f"Error: {str(e)}"

    def _prepare_api_boleta(self):
        """Genera el diccionario con los datos de la factura para el API."""
        global  ws_diario

        """ Método para consumir el WS de prueba """
        #api_url = "http://localhost:5000/validate_invoice"
        api_url = "https://testsee.itc.com.pe/api/billservice"

        """Genera el JSON en el formato específico requerido."""
        self.ensure_one()

        #Esta Variable se utilizan para saber el valor del Impuesto(IGV)
        Tax=0.18

        #Esta Variable se utilizan para saber el valor del tipo de impuesto, igv, inafecto, exonerado
        TipTax="IGV"

        #Esta Variable se utilizan para saber si un documento está afecto al IGV(cod 10)
        cod_tip_afect_igv_item=30

        #Estas Variables se utilizan para totalizar un documento dependiente de si la transaccion
        #tiene IGV o es inafecto, exonerado o gratuito
        mnt_tot_gravadas= 0.00
        mnt_tot_inafectas = 0.00
        mnt_tot_exoneradas = 0.00
        mnt_tot_gratuitas = 0.00

        #-----DETALLE----
        detalles = []
        for i, line in enumerate(self.invoice_line_ids, start=1):
            TipTax = line.tax_ids.tax_group_id.name,
            Tax = line.tax_ids.amount/100,

            if TipTax[0] == "IGV" :
                cod_tip_afect_igv_item=10
            elif TipTax[0] == "EXO" :
                cod_tip_afect_igv_item = 20
            elif TipTax[0] == "INA" :
                cod_tip_afect_igv_item = 30

            detalles.append({
                "num_lin_item": i,  #1,
                "cod_unid_item": "NIU",
                "cant_unid_item": line.quantity, #3,
                "val_vta_item": line.price_subtotal, #30.00,
                "cod_tip_afect_igv_item": cod_tip_afect_igv_item, #10,
                "prc_vta_unit_item": line.price_unit * (1.00 + Tax[0]), #11.80,
                "mnt_dscto_item": 0.00,
                "mnt_igv_item": line.price_subtotal * (Tax[0]), #5.40,
                "txt_descr_item": line.name, #"Cartera",
                "cod_prod_sunat": "31201501",
                "cod_item": str(line.product_id), #"00001", #ver la posibilidad que sea el codigo del producto
                "val_unit_item": line.price_unit, #10.00,
                "cod_tip_sist_isc": "",
                "mnt_isc_item": 0.00,
                "porcentaje_isc": "",
                "dato_extra_1": "",
                "dato_extra_2": "",
                "importe_total_item": line.price_subtotal * (1.00 + Tax[0]), #35.40,
                "val_unit_icbper": 0.00,
                "cant_icbper_item": 0.00,
                "mnt_icbper_item": 0.00
             })
            
        # --- CABECERA ---
        #self.ws_seriecorre=ws_diario.code
        
        if TipTax[0] == "IGV" :
            mnt_tot_gravadas=self.amount_untaxed
        elif TipTax[0] == "INA" :
            mnt_tot_inafectas = self.amount_untaxed
        elif TipTax[0] == "EXO" :
            mnt_tot_exoneradas = self.amount_untaxed
        elif TipTax[0] == "GRA" :
            mnt_tot_gratuitas = self.amount_untaxed
        else :
            mnt_tot_exoneradas = 0

        payload = {
            "identificador": "BC",
            "fec_emis": self.invoice_date.strftime("%Y-%m-%d"), #"2025-06-05",
            "hora_emis": "00:00:00",
            "txt_serie": ws_diario.code, #self.sequence_prefix, #, #"B001",
            "txt_correlativo": self.name[5:], #self.name, #self.name[2:], #"00000077",
            "cod_tip_cpe": "03",
            "cod_mnd": self.currency_id.name, #"PEN",
            "cod_tip_escenario": "01",
            "txt_placa": "",
            "cod_cliente_emis": 799,
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
            "mnt_tot_gravadas":  mnt_tot_gravadas, #self.amount_untaxed,, #100.00,
            "mnt_tot_inafectas": mnt_tot_inafectas, #0, 
            "mnt_tot_exoneradas": mnt_tot_exoneradas, #0, 
            "mnt_tot_gratuitas": mnt_tot_gratuitas, #0, 
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
            "observaciones": "ambiente de prueba",
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
            "mnt_tot_icbper":0,
            "cod_tip_frmpgo": 1,
            "mnto_crdt_ttal": 0.00,
            "mnto_crdt_cta":0,
            "fch_cta":"",
            "detalles": detalles
        }
       

        headers = {
                'Content-Type': 'application/json',
                'Authorization': f'WsC0nexBYB@:YQSa3C13gQKQb3LbLUdG2w==',  # ⭐¡Aquí va el token!
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
            

            if isinstance(data, dict):  # Primero verifica que data sea un diccionario
                is_valid = data.get('Resultado', False)  # Valor por defecto False si no existe
                error_msg = data.get('Mensaje', 'Error no especificado')  # Mensaje por defecto
                
                if bool(is_valid):  # Asegura que is_valid sea booleano
                    self.ws_response = "✅ Validado por API"
                else:
                    self.ws_response = f"❌ Error: {error_msg}"
            else:
                self.ws_response = "🔴 Respuesta del API no válida"
                _logger.error("La respuesta del API no es un diccionario: %s", str(data))

        except Exception as e:
                _logger.error("Error al llamar al WS: %s", str(e))
                self.ws_response = f"Error: {str(e)}"

    def _prepare_api_notacredito(self):
        """Genera el diccionario con los datos de la factura para el API."""
        global  ws_diario

        """ Método para consumir el WS de prueba """
        #api_url = "http://localhost:5000/validate_invoice"
        api_url = "https://testsee.itc.com.pe/api/billservice"

        """Genera el JSON en el formato específico requerido."""
        self.ensure_one()

        #Esta Variable se utilizan para saber el valor del Impuesto(IGV)
        Tax=0.18

        #Esta Variable se utilizan para saber el valor del tipo de impuesto, igv, inafecto, exonerado
        TipTax="IGV"

        #Esta Variable se utilizan para saber si un documento está afecto al IGV(cod 10)
        cod_tip_afect_igv_item=30

        #Estas Variables se utilizan para totalizar un documento dependiente de si la transaccion
        #tiene IGV o es inafecto, exonerado o gratuito
        mnt_tot_gravadas= 0.00
        mnt_tot_inafectas = 0.00
        mnt_tot_exoneradas = 0.00
        mnt_tot_gratuitas = 0.00

        """Obtiene Datos de la Factura."""
        factura_original = self.reversed_entry_id

        #-----DETALLE----
        detalles = []
        for i, line in enumerate(self.invoice_line_ids, start=1):
            TipTax = line.tax_ids.tax_group_id.name,
            Tax = line.tax_ids.amount/100,

            if TipTax[0] == "IGV" :
                cod_tip_afect_igv_item=10
            elif TipTax[0] == "EXO" :
                cod_tip_afect_igv_item = 20
            elif TipTax[0] == "INA" :
                cod_tip_afect_igv_item = 30

            detalles.append({
                "num_lin_item": i,  #1,
                "cod_unid_item": "NIU",
                "cant_unid_item": line.quantity, #3,
                "val_vta_item": line.price_subtotal, #30.00,
                "cod_tip_afect_igv_item": cod_tip_afect_igv_item, #10,
                "prc_vta_unit_item": line.price_unit * (1.00 + Tax[0]), #11.80,
                "mnt_dscto_item": 0.00,
                "mnt_igv_item": line.price_subtotal * (Tax[0]), #5.40,
                "txt_descr_item": line.name, #"Cartera",
                "cod_prod_sunat": "31201501",
                "cod_item": str(line.product_id), #"00001", #ver la posibilidad que sea el codigo del producto
                "val_unit_item": line.price_unit, #10.00,
                "cod_tip_sist_isc": "",
                "mnt_isc_item": 0.00,
                "porcentaje_isc": "",
                "dato_extra_1": "",
                "dato_extra_2": "",
                "importe_total_item": line.price_subtotal * (1.00 + Tax[0]), #35.40,
                "val_unit_icbper": 0.00,
                "cant_icbper_item": 0.00,
                "mnt_icbper_item": 0.00
             })
            
        # --- CABECERA ---
        #self.ws_seriecorre=ws_diario.code

        if TipTax[0] == "IGV" :
            mnt_tot_gravadas=self.amount_untaxed
        elif TipTax[0] == "INA" :
            mnt_tot_inafectas = self.amount_untaxed
        elif TipTax[0] == "EXO" :
            mnt_tot_exoneradas = self.amount_untaxed
        elif TipTax[0] == "GRA" :
            mnt_tot_gratuitas = self.amount_untaxed
        else :
            mnt_tot_exoneradas = 0

        payload = {
            "identificador": "CC",
            "fec_emis": self.invoice_date.strftime("%Y-%m-%d"), #"2025-06-05",
            "hora_emis": "00:00:00",
            "txt_serie": self.sequence_prefix, #"F001", #factura_original.ws_seriecorre, #, #ws_diario.code, #
            "txt_correlativo": self.name[5:], #self.name, #self.name[2:], #"00000077",
            "cod_tip_cpe": "07",
            "cod_mnd": self.currency_id.name, #"PEN",
            "cod_tip_escenario": "01",
            "txt_placa": "",
            "cod_cliente_emis": 799,
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
            "mnt_tot_gravadas":  mnt_tot_gravadas, #self.amount_untaxed,, #100.00,
            "mnt_tot_inafectas": mnt_tot_inafectas, #0, 
            "mnt_tot_exoneradas": mnt_tot_exoneradas, #0, 
            "mnt_tot_gratuitas": mnt_tot_gratuitas, #0, 
            "mnt_tot_desc_global": 0.00,
            "mnt_tot_igv": self.amount_tax, #18.00,
            "mnt_tot_igv_isc": 0.00,
            "mnt_tot_base_imponible": 0.00,
            "mnt_tot_percepcion": 0.00,
            "mnt_tot_a_percibir": 0.00,
            "mnt_tot": self.amount_total, #118.00,
            "cod_tip_nc_nd_ref": "01",  #codigo nota de credito
            "txt_serie_ref": factura_original.sequence_prefix, #"F001", #serie de documento afectado
            "txt_correlativo_cpe_ref": factura_original.name[5:], #factura_original.name, #, #"00000091", #correlativo de documento afectado
            "fec_emis_ref":factura_original.invoice_date.strftime("%Y-%m-%d"), #"2025-06-11", #Fecha de emision del documento relacionado
            "cod_cpe_ref":"01", #codigo de tipo de documento afectado
            "txt_sustento":self.ref, #"equivocacion", #Motivo y/o descripcion de la Nota
            "cod_operacion": "0101",
            "porcentaje_dscto": "",
            "mnt_anticipo": 0.00,
            "mnt_otros_cargos": 0.00,
            "tipo_percepcion": "",
            "porcentaje_percepcion": "",    
            "tipo_cambio": 0.00,
            "observaciones": "prueba desde Postman",
            "flag_envio_automatico": 1,
            "dato_extra_1": "extra",
            "dato_extra_2": "extra",
            "dato_extra_3": "extra",
            "dato_extra_4": "extra",
            "mnt_tot_icbper": 0.00,
            "cod_tip_frmpgo": 1,
            "mnto_crdt_ttal": 0.00,
            "mnto_crdt_cta": 0.00,
            "fch_cta":0,           
            "detalles": detalles
        }
       

        headers = {
                'Content-Type': 'application/json',
                'Authorization': f'WsC0nexBYB@:YQSa3C13gQKQb3LbLUdG2w==',  # ⭐¡Aquí va el token!
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
            

            if isinstance(data, dict):  # Primero verifica que data sea un diccionario
                is_valid = data.get('Resultado', False)  # Valor por defecto False si no existe
                error_msg = data.get('Mensaje', 'Error no especificado')  # Mensaje por defecto
                
                if bool(is_valid):  # Asegura que is_valid sea booleano
                    self.ws_response = "✅ Validado por API"
                else:
                    self.ws_response = f"❌ Error: {error_msg}"
            else:
                self.ws_response = "🔴 Respuesta del API no válida"
                _logger.error("La respuesta del API no es un diccionario: %s", str(data))

        except Exception as e:
                _logger.error("Error al llamar al WS: %s", str(e))
                self.ws_response = f"Error: {str(e)}"

    def _prepare_api_notadebito(self):
        """Genera el diccionario con los datos de la factura para el API."""
        global  ws_diario

        """ Método para consumir el WS de prueba """
        #api_url = "http://localhost:5000/validate_invoice"
        api_url = "https://testsee.itc.com.pe/api/billservice"

        """Genera el JSON en el formato específico requerido."""
        self.ensure_one()

        #Esta Variable se utilizan para saber el valor del Impuesto(IGV)
        Tax=0.18

        #Esta Variable se utilizan para saber el valor del tipo de impuesto, igv, inafecto, exonerado
        TipTax="IGV"

        #Esta Variable se utilizan para saber si un documento está afecto al IGV(cod 10)
        cod_tip_afect_igv_item=30

        #Estas Variables se utilizan para totalizar un documento dependiente de si la transaccion
        #tiene IGV o es inafecto, exonerado o gratuito
        mnt_tot_gravadas= 0.00
        mnt_tot_inafectas = 0.00
        mnt_tot_exoneradas = 0.00
        mnt_tot_gratuitas = 0.00

        """Obtiene Datos de la Factura."""
        factura_original = self.debit_origin_id

        #-----DETALLE----
        detalles = []
        for i, line in enumerate(self.invoice_line_ids, start=1):
            TipTax = line.tax_ids.tax_group_id.name,
            Tax = line.tax_ids.amount/100,

            if TipTax[0] == "IGV" :
                cod_tip_afect_igv_item=10
            elif TipTax[0] == "EXO" :
                cod_tip_afect_igv_item = 20
            elif TipTax[0] == "INA" :
                cod_tip_afect_igv_item = 30

            detalles.append({
                "num_lin_item": i,  #1,
                "cod_unid_item": "NIU",
                "cant_unid_item": line.quantity, #3,
                "val_vta_item": line.price_subtotal, #30.00,
                "cod_tip_afect_igv_item": cod_tip_afect_igv_item, #10,
                "prc_vta_unit_item": line.price_unit * (1.00 + Tax[0]), #11.80,
                "mnt_dscto_item": 0.00,
                "mnt_igv_item": line.price_subtotal * (Tax[0]), #5.40,
                "txt_descr_item": line.name, #"Cartera",
                "cod_prod_sunat": "31201501",
                "cod_item": str(line.product_id), #"00001", #ver la posibilidad que sea el codigo del producto
                "val_unit_item": line.price_unit, #10.00,
                "cod_tip_sist_isc": "",
                "mnt_isc_item": 0.00,
                "porcentaje_isc": "",
                "dato_extra_1": "",
                "dato_extra_2": "",
                "importe_total_item": line.price_subtotal * (1.00 + Tax[0]), #35.40,
                "val_unit_icbper": 0.00,
                "cant_icbper_item": 0.00,
                "mnt_icbper_item": 0.00
             })
            
        # --- CABECERA ---
        #self.ws_seriecorre=ws_diario.code

        if TipTax[0] == "IGV" :
            mnt_tot_gravadas=self.amount_untaxed
        elif TipTax[0] == "INA" :
            mnt_tot_inafectas = self.amount_untaxed
        elif TipTax[0] == "EXO" :
            mnt_tot_exoneradas = self.amount_untaxed
        elif TipTax[0] == "GRA" :
            mnt_tot_gratuitas = self.amount_untaxed
        else :
            mnt_tot_exoneradas = 0
        payload = {
            "identificador": "DC",
            "fec_emis": self.invoice_date.strftime("%Y-%m-%d"), #"2025-06-05",
            "hora_emis": "00:00:00",
            "txt_serie": self.sequence_prefix, #"F001", #factura_original.ws_seriecorre, #, #ws_diario.code, #
            "txt_correlativo": self.name[5:], #self.name, #self.name[2:], #"00000077",
            "cod_tip_cpe": "08",
            "cod_mnd": self.currency_id.name, #"PEN",
            "cod_tip_escenario": "01",
            "txt_placa": "",
            "cod_cliente_emis": 799,
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
            "mnt_tot_gravadas":  mnt_tot_gravadas, #self.amount_untaxed,, #100.00,
            "mnt_tot_inafectas": mnt_tot_inafectas, #0, 
            "mnt_tot_exoneradas": mnt_tot_exoneradas, #0, 
            "mnt_tot_gratuitas": mnt_tot_gratuitas, #0, 
            "mnt_tot_desc_global": 0.00,
            "mnt_tot_igv": self.amount_tax, #18.00,
            "mnt_tot_igv_isc": 0.00,
            "mnt_tot_base_imponible": 0.00,
            "mnt_tot_percepcion": 0.00,
            "mnt_tot_a_percibir": 0.00,
            "mnt_tot": self.amount_total, #118.00,
            "cod_tip_nc_nd_ref": "01",  #codigo nota de debito
            "txt_serie_ref": factura_original.sequence_prefix, #"F001", #serie de documento afectado
            "txt_correlativo_cpe_ref": factura_original.name[5:], #factura_original.name, #, #"00000091", #correlativo de documento afectado
            "fec_emis_ref":factura_original.invoice_date.strftime("%Y-%m-%d"), #"2025-06-11", #Fecha de emision del documento relacionado
            "cod_cpe_ref":"01", #codigo de tipo de documento afectado
            "txt_sustento":self.ref, #"equivocacion", #Motivo y/o descripcion de la Nota
            "cod_operacion": "0101",
            "porcentaje_dscto": "",
            "mnt_anticipo": 0.00,
            "mnt_otros_cargos": 0.00,
            "tipo_percepcion": "",
            "porcentaje_percepcion": "",    
            "tipo_cambio": 0.00,
            "observaciones": "prueba desde Postman",
            "flag_envio_automatico": 1,
            "dato_extra_1": "extra",
            "dato_extra_2": "extra",
            "dato_extra_3": "extra",
            "dato_extra_4": "extra",
            "mnt_tot_icbper": 0.00,
            "detalles": detalles
        }
       

        headers = {
                'Content-Type': 'application/json',
                'Authorization': f'WsC0nexBYB@:YQSa3C13gQKQb3LbLUdG2w==',  # ⭐¡Aquí va el token!
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
            

            if isinstance(data, dict):  # Primero verifica que data sea un diccionario
                is_valid = data.get('Resultado', False)  # Valor por defecto False si no existe
                error_msg = data.get('Mensaje', 'Error no especificado')  # Mensaje por defecto
                
                if bool(is_valid):  # Asegura que is_valid sea booleano
                    self.ws_response = "✅ Validado por API"
                else:
                    self.ws_response = f"❌ Error: {error_msg}"
            else:
                self.ws_response = "🔴 Respuesta del API no válida"
                _logger.error("La respuesta del API no es un diccionario: %s", str(data))

        except Exception as e:
                _logger.error("Error al llamar al WS: %s", str(e))
                self.ws_response = f"Error: {str(e)}"

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
        ws_diario = self.env['account.journal'].search([], limit=1)

        return {
            'invoice': {
                    # "serie": ws_diario.code,
                    # "fec_emis": self.invoice_date.strftime("%Y-%m-%d"), #"2025-05-27",
                    # "txt_correlativo": self.name, #self.name[2:], #'00000036',
                    # "cod_mnd": self.currency_id.name, #"PEN",
                    # "num_iden_recp": self.partner_id.vat or "Sin RUC", #"20600184718",
                    # "nom_rzn_soc_recp": self.partner_id.complete_name or "Sin Razon Social", #"AquaJet Store SAC -",
                    # "txt_dmcl_fisc_recep": self.partner_id.contact_address or "Sin dirección", #"AV ABANCAY 176",
                    # "mnt_tot_gravadas": self.amount_untaxed,
                    # "mnt_tot_igv":  self.amount_tax,
                    # "mnt_tot": self.amount_total,

                    "identificador": "FC",
                    "fec_emis": self.invoice_date.strftime("%Y-%m-%d"), #"2025-06-05",
                    "hora_emis": "00:00:00",
                    "txt_serie": ws_diario.code, #self.sequence_prefix, #, #"F001",
                    "txt_correlativo": self.name[5:], #self.name, #, #"00000077",
                    "cod_tip_cpe": "01",
                    "cod_mnd": self.currency_id.name, #"PEN",
                    "cod_tip_escenario": "01",
                    "txt_placa": "",
                    "cod_cliente_emis": 799,
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
                    "observaciones": "ambiente de prueba",
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
            "fec_emis": self.invoice_date.strftime("%Y-%m-%d"), #"2025-06-05",
            "txt_serie": "F001",
            "txt_correlativo": self.name, #self.name[2:], #"00000077",
            "cod_tip_cpe": "07",
            "cod_mnd": self.currency_id.name, #"PEN",
            "cod_tip_escenario": "01",
            "cod_cliente_emis": 799,
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
                "prc_vta_unit_item": line.price_unit * (1.00 + Tax[0]), #11.80,
                "mnt_igv_item": line.price_subtotal * (Tax[0]), #5.40,
                "txt_descr_item": line.name, #"Cartera",
                "cod_prod_sunat": "31201501",
                "cod_item": str(line.product_id), #"00001", #ver la posibilidad que sea el codigo del producto
                "val_unit_item": line.price_unit, #10.00,
                "importe_total_item": line.price_subtotal * (1.00 + Tax[0]), #35.40,
                }
                for line in self.invoice_line_ids
            ]
        }
    
    def action_show_payload(self):
        self.ensure_one()
        
        # Prepara detalles de líneas
        lines_info = [
             f"Línea {i+1}: {line.name}\nSubtotal: {line.price_subtotal}"
             for i, line in enumerate(self.invoice_line_ids)
         ]
        
        # Crea registro temporal
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
        
        # Prepara detalles de líneas
        lines_info = [
             f"Línea {i+1}: {line.name}\nSubtotal: {line.price_subtotal}"
             for i, line in enumerate(self.invoice_line_ids)
         ]
        
        # Crea registro temporal
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
