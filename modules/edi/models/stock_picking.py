from odoo import models, fields, api
import requests
import logging
import json

#modifique el 2025.10.09 INI
from odoo.exceptions import ValidationError
#modifique el 2025.10.09 FIN


_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    """ Aqui se crea el campo en la BD con el nombre ws_response para almacenar la respuesta del WS """
    ws_response = fields.Char(string="Respuesta WS", readonly=True)

    """ Aqui se crea el campo en la BD con el nombre SerieCorre para almacenar la Serie del Correlativo """
    #ws_seriecorre = fields.Char(string="Serie Correlativo", readonly=True)

    """ Aqui se crea el Campo para conductor (relacionado con fleet.vehicle) """
    # driver_id = fields.Many2one(
    #      'fleet.vehicle',
    #      string='Conductor',
    #      domain="[('driver_id', '!=', False)]",  # Opcional: filtrar conductor
    # )

    """ Aqui se crea el Campo para vehículo (relacionado con fleet.vehicle) """
    vehicle_id_guia = fields.Many2one(
        'fleet.vehicle',
        string='Vehiculo',
        domain="[('model_id', '!=', False)]",  # Opcional: filtrar vehículos
        required=False,  # 👈 Campo obligatorio
        help="Seleccione el vehículo asignado a esta guía."
    )


    #modifique el 2025.10.09 INI
    #esta variable se utilizará para poder saber la serie de la guia a través de su asiento diario
    ws_diario = ""
    def button_validate(self):
         print("✅ MI VALIDACIÓN SE ESTÁ EJECUTANDO")
         """Genera el diccionario con los datos de la factura para el API."""
         global  ws_diario
         result = super(StockPicking, self).button_validate()

         for picking in self:
            if (picking.picking_type_id.code == 'outgoing'):
                if not picking.vehicle_id_guia:
                        raise ValidationError("🚛 ¡Debess seleccionar un vehículo para guías de remisión!")
                else:
                        ws_diario = self.env['account.journal'].search([('name', 'ilike', 'Guias de Remision')], limit=1)
                        picking._send_guia_to_ws()
            return result
    #modifique el 2025.10.09 FIN



    
    def _send_guia_to_ws(self):

        """Genera el diccionario con los datos de la factura para el API."""
        global  ws_diario

        """ Método para consumir el WS de prueba """
        #api_url = "http://localhost:5000/validate_invoice"
        api_url = self.company_id.service_url #"https://testsee.itc.com.pe/api/billservice"

        """Genera el JSON en el formato específico requerido."""
        self.ensure_one()

        # Datos de la Guía de Remisión
        # DETALLES (Líneas de productos)
        detalles = []
        for index, line in enumerate(self.move_ids_without_package, start=1):

            detalles.append({
            'num_lin_item': index,
            'cod_item': str(line.product_id), #line.product_id.default_code or '',
            'txt_descr_item': line.product_id.name,
            #'cod_prod_sunat':'SUNAT001',
            'cant_unid_item': line.quantity,
            'cod_unid_item':"NIU"
        })

        if self.vehicle_id_guia.model_id.name[:6] == "propio" :
            #Privada   
            guia_data = {
               # CABECERA
                "identificador": "GR",
                "cod_tip_cpe": "09",
                "cod_cliente_emis": self.company_id.service_code or "", #self.company_id.service_code or "", #799,
                'txt_serie': ws_diario.code, #G001
                'txt_correlativo': self.name[7:], #self.name, #, #"00000077",
                'num_ruc_rem': self.company_id.partner_id.vat or '',
                'nom_rzn_soc_rem': self.company_id.partner_id.name or '',
                'cod_tip_nif_rem':6,
                'num_ruc_dest': self.partner_id.vat or '',
                'nom_rzn_soc_dest': self.partner_id.name,
                'cod_tip_nif_dest':6,
                'num_iden_prov': '',  # Ajustar si el proveedor está en otro campo
                'nom_rzn_soc_prov': '',  # Ajustar según necesidad
                #'cod_tip_nif_prov':6,
                'fec_emis': self.date_done.strftime('%Y-%m-%d') if self.date_done else '',
                'hora_emis':"00:00:00",
                'cod_ubi_partida': "150101",
                'txt_domicilio_partida': self.company_id.street or '',
                'txt_domicilio_llegada': self.partner_id.street or '',
                'cod_ubi_llegada':"150101",
                'trans_fec_emis': self.date_done.strftime('%Y-%m-%d') if self.date_done else '',
                'trans_fec_ini' : self.date_done.strftime('%Y-%m-%d') if self.date_done else '',
                'trans_entid_emt_auto':"MTC",
                'cod_unid_peso_bruto':"KGM",
                'mnt_tot_peso_bruto':sum(move.product_id.weight * move.quantity for move in self.move_ids if move.product_id.weight) or 0,
                'cod_mot_trasalado':"01",
                'trans_cod_tip_modalidad':"02",
                'observaciones':"la guia de remision tiene que ser llevada obligatoriamente",
                "txt_desc_motiv_tras": "VENTA - transporte privado",
                "indicador": [
                    {
                        "ind_nom": "SUNAT_Envio_IndicadorTransbordoProgramado"
                    }
                ],               
                "documentoVehiculo": [
                    {
                        "veh_alt": 1,
                        "veh_txt_placa": self.vehicle_id_guia.license_plate or "No Asignado",
                        "veh_tarj_unic_circ": "",
                        "veh_reg_mtc": "",
                        "veh_ent_emt_auto": "MTC",
                        "veh_num_auto": ""
                    }
                ],
                "documentoConductor": [
                    {
                        "con_alt": 1,
                        "con_tip_iden": "1",
                        "con_num_iden": self.vehicle_id_guia.driver_id.vat or "No Asignado",
                        "con_nombre": self.vehicle_id_guia.driver_id.commercial_partner_id.name or "No asignado",
                        "con_apellido": self.vehicle_id_guia.driver_id.commercial_partner_id.name or "No asignado",
                        "con_num_lic": self.vehicle_id_guia.driver_id.function or "No Asignado",
                    }
                ],
                "detalles": detalles
            }
        else :
            #Publica
            guia_data = {
                # CABECERA
                "identificador": "GR",
                "cod_tip_cpe": "09",
                "cod_cliente_emis": self.company_id.service_code or "", #self.company_id.service_code or "", #799,
                'txt_serie': ws_diario.code, #G001
                'txt_correlativo': self.name[7:], #self.name, #, #"00000077",
                'num_ruc_rem': self.company_id.partner_id.vat or '',
                'nom_rzn_soc_rem': self.company_id.partner_id.name or '',
                'cod_tip_nif_rem':6,
                'num_ruc_dest': self.partner_id.vat or '',
                'nom_rzn_soc_dest': self.partner_id.name,
                'cod_tip_nif_dest':6,
                'num_iden_prov': '',  # Ajustar si el proveedor está en otro campo
                'nom_rzn_soc_prov': '',  # Ajustar según necesidad
                #'cod_tip_nif_prov':6,
                'fec_emis': self.date_done.strftime('%Y-%m-%d') if self.date_done else '',
                'hora_emis':"00:00:00",
                'cod_ubi_partida': "150101",
                'txt_domicilio_partida': self.company_id.street or '',
                'txt_domicilio_llegada': self.partner_id.street or '',
                'cod_ubi_llegada':"150101",
                'trans_entid_emt_auto':"MTC",
                'cod_unid_peso_bruto':"KGM",
                'mnt_tot_peso_bruto':sum(move.product_id.weight * move.quantity for move in self.move_ids if move.product_id.weight) or 0,
                'cod_mot_trasalado':"01",
                'observaciones':"la guia de remision tiene que ser llevada obligatoriament",
                'txt_desc_motiv_tras':"venta",
                # DATOS DEL VEHÍCULO (Flota)
                'veh_txt_placa': self.vehicle_id_guia.license_plate or "No Asignado",
                'veh_ent_emt_auto':"MTC",
                'trans_cod_emt_auto':"obtener codigo de entidad autorizadora",
                # DATOS DEL CONDUCTOR (Flota/Contactos)
                'trans_txt_nombre':self.vehicle_id_guia.driver_id.commercial_partner_id.name or "No asignado",
                'trans_txt_ruc':self.vehicle_id_guia.driver_id.commercial_partner_id.vat or "No asignado",
                'trans_cod_tip_nif':"6",
                'trans_fec_ini': self.scheduled_date.strftime('%Y-%m-%d'),
                'trans_cod_tip_modalidad':"01",
                'trans_conduct_num_iden': self.vehicle_id_guia.driver_id.vat or "No Asignado",
                'trans_conduct_nom_ape': self.vehicle_id_guia.driver_id.name or "No Asignado",
                'con_num_lic': self.vehicle_id_guia.driver_id.function or "No Asignado",
                "detalles": detalles
            }

        headers = {
                'Content-Type': 'application/json',
                'Authorization': self.company_id.service_token #f'WsC0nexBYB@:YQSa3C13gQKQb3LbLUdG2w==',  # ⭐¡Aquí va el token!
            }
            
        try:
            response = requests.post(
                api_url,
                json=guia_data,
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
    def _prepare_guia_emitir(self):
        """Genera el diccionario con los datos de la factura para el API."""
        global ws_diario 
        modelo=""

        self.ensure_one()

        # # Busca el diario (ej: Diario de Ventas)
        ws_diario = self.env['account.journal'].search([], limit=1)
        if self.vehicle_id_guia.model_id.name[:6] == "propio" :
            modelo="propio"
        else :
            modelo=self.vehicle_id_guia.model_id.name

        return {
            'invoice': {
            # "txt_serie": ws_diario.code,
            # 'txt_correlativo': self.name[7:], #self.name, #, #"00000077",
            # "identificador": "GR",
            # "modelo": modelo,
            # "cod_tip_cpe": "09",
            # "cod_cliente_emis": self.company_id.service_code or "", #self.company_id.service_code or "", #799,
            # 'num_ruc_rem': self.company_id.partner_id.vat or '',
            # 'nom_rzn_soc_rem': self.company_id.partner_id.name or '',
            # 'cod_tip_nif_rem':6,
            # 'num_ruc_dest': self.partner_id.vat or '',
            # 'nom_rzn_soc_dest': self.partner_id.name,
            # 'fec_emis': self.date_done.strftime('%Y-%m-%d') if self.date_done else '',
            # 'txt_domicilio_partida': self.company_id.street or '',
            # 'txt_domicilio_llegada': self.partner_id.street or '',
            # 'trans_cod_tip_modalidad':"01",
            # 'trans_cod_tip_nif':"6",
            # 'trans_txt_nombre': self.vehicle_id.driver_id.commercial_partner_id.name or "No asignado", #datos_guia['razon_social_transportista'] or "No Asignado", 
            # 'trans_txt_ruc': self.vehicle_id.driver_id.commercial_partner_id.vat or "No asignado",
            # 'trans_conduct_nom_ape': self.vehicle_id.driver_id.name or "No Asignado",
            # 'trans_conduct_num_iden': self.vehicle_id.driver_id.vat or "No Asignado",
            # 'veh_txt_placa': self.vehicle_id.license_plate or "No Asignado",
            # 'con_num_lic': self.vehicle_id.driver_id.function or "No Asignado",
            # 'mnt_tot_peso_bruto':sum(move.product_id.weight * move.quantity for move in self.move_ids if move.product_id.weight) or 0,
            # INICIO
            
            "identificador": "GR",
            "cod_tip_cpe": "09",
            "cod_cliente_emis": self.company_id.service_code or "", #self.company_id.service_code or "", #799,
            'txt_serie': ws_diario.code, #G001
            'txt_correlativo': self.name[7:], #self.name, #, #"00000077",
            'num_ruc_rem': self.company_id.partner_id.vat or '',
            'nom_rzn_soc_rem': self.company_id.partner_id.name or '',
            'cod_tip_nif_rem':6,
            'num_ruc_dest': self.partner_id.vat or '',
            'nom_rzn_soc_dest': self.partner_id.name,
            'cod_tip_nif_dest':6,
            'num_iden_prov': '',  # Ajustar si el proveedor está en otro campo
            'nom_rzn_soc_prov': '',  # Ajustar según necesidad
            #'cod_tip_nif_prov':6,
            'fec_emis': self.date_done.strftime('%Y-%m-%d') if self.date_done else '',
            'hora_emis':"00:00:00",
            'cod_ubi_partida': "150101",
            'txt_domicilio_partida': self.company_id.street or '',
            'txt_domicilio_llegada': self.partner_id.street or '',
            'cod_ubi_llegada':"150101",
            'trans_fec_emis': self.date_done.strftime('%Y-%m-%d') if self.date_done else '',
            'trans_fec_ini' : self.date_done.strftime('%Y-%m-%d') if self.date_done else '',
            'trans_entid_emt_auto':"MTC",
            'cod_unid_peso_bruto':"KGM",
            'mnt_tot_peso_bruto':sum(move.product_id.weight * move.quantity for move in self.move_ids if move.product_id.weight) or 0,
            'cod_mot_trasalado':"01",
            'trans_cod_tip_modalidad':"02",
            'observaciones':"la guia de remision tiene que ser llevada obligatoriament",
            "txt_desc_motiv_tras": "VENTA - transporte privado",
            "indicador": [
                {
                    "ind_nom": "SUNAT_Envio_IndicadorTransbordoProgramado"
                }
            ],               
            "documentoVehiculo": [
                {
                    "veh_alt": 1,
                    "veh_txt_placa": self.vehicle_id_guia.license_plate or "No Asignado",
                    "veh_tarj_unic_circ": "",
                    "veh_reg_mtc": "",
                    "veh_ent_emt_auto": "MTC",
                    "veh_num_auto": ""
                }
            ],
            "documentoConductor": [
                {
                    "con_alt": 1,
                    "con_tip_iden": "1",
                    "con_num_iden": self.vehicle_id_guia.driver_id.vat or "No Asignado",
                    "con_nombre": self.vehicle_id_guia.driver_id.commercial_partner_id.name or "No asignado",
                    "con_apellido": self.vehicle_id_guia.driver_id.commercial_partner_id.name or "No asignado",
                    "con_num_lic": self.vehicle_id_guia.driver_id.function or "No Asignado",
                }
            ],
            # FIN
            },
            'lines': 
                [{
                'cod_item': str(line.product_id), # line.product_id.default_code or '',
                'txt_descr_item': line.product_id.name,
                #'cod_prod_sunat':'SUNAT001',
                'cant_unid_item': line.quantity,
                'cod_unid_item':"NIU",
                }
                for line in self.move_ids_without_package #self.move_ids  
            ]
        
        }

    def action_show_guia(self):
        self.ensure_one()
        
        # Prepara detalles de líneas
        lines_info = [
             f"Línea {i+1}: {line.name}\nCantidad: {line.quantity}"
             for i, line in enumerate(self.move_ids_without_package)
        ]
        
        # Crea registro temporal
        debug_rec = self.env['guia.debug'].create({
            'guia_id': self.id,
            'guia_data': json.dumps(self._prepare_guia_emitir(), indent=2),
            'line_details': "\n\n".join(lines_info)
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Detalle de la Guia',
            'view_mode': 'form',
            'res_model': 'guia.debug',
            'res_id': debug_rec.id,
            'target': 'new',
        }
    

# SELECT * FROM stock_picking

# SELECT * FROM stock_move order by id

# SELECT * FROM fleet_vehicle

# SELECT * FROM account_move
