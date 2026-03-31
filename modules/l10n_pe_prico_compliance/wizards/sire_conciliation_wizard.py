# -*- coding: utf-8 -*-
import base64
from odoo import models, fields, api
from odoo.exceptions import UserError

class SireConciliationWizard(models.TransientModel):
    _name = 'sire.conciliation.wizard'
    _description = 'Conciliación SIRE vs Odoo (Compras)'

    date_from = fields.Date(string='Fecha Inicio', required=True)
    date_to = fields.Date(string='Fecha Fin', required=True)
    
    proposal_file = fields.Binary(string='TXT Propuesta SUNAT', required=True)
    proposal_filename = fields.Char(string='Nombre Archivo')
    
    state = fields.Selection([('upload', 'Subir Archivo'), ('results', 'Resultados')], default='upload')
    line_ids = fields.One2many('sire.conciliation.line', 'wizard_id', string='Detalles de Conciliación')

    def action_compare(self):
        # 1. Decodificar el archivo TXT de SUNAT
        try:
            file_content = base64.b64decode(self.proposal_file).decode('utf-8')
        except UnicodeDecodeError:
            file_content = base64.b64decode(self.proposal_file).decode('latin-1')
        except Exception as e:
            raise UserError(f"Error al leer el archivo. Asegúrese de que sea un TXT válido. Detalle: {str(e)}")

        sunat_data = {}
        for line in file_content.splitlines():
            if not line.strip(): 
                continue
            cols = line.split('|')
            if len(cols) < 25: 
                continue # Validación básica para ignorar cabeceras o líneas rotas
            
            try:
                # Índices estándar de la propuesta RCE de SUNAT
                ruc_prov = cols[12].strip()
                tipo_doc = cols[6].strip()
                serie = cols[7].strip()
                numero = cols[9].strip()
                
                # Limpiamos ceros a la izquierda para evitar falsos positivos (ej. 0001 vs 1)
                serie_clean = serie.lstrip('0') or '0'
                numero_clean = numero.lstrip('0') or '0'
                
                key = f"{ruc_prov}-{tipo_doc}-{serie_clean}-{numero_clean}"
                
                sunat_data[key] = {
                    'fecha': cols[4],
                    'proveedor': cols[13][:40], # Recortar nombre muy largo
                    'total': float(cols[26] if cols[26].strip() else 0.0),
                }
            except Exception:
                continue # Ignorar líneas mal formadas silenciosamente

        # 2. Leer facturas de Compras en Odoo
        domain = [
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
            ('state', '=', 'posted'),
            ('move_type', 'in', ('in_invoice', 'in_refund'))
        ]
        moves = self.env['account.move'].search(domain)
        
        odoo_data = {}
        for move in moves:
            ruc_prov = move.partner_id.vat or '0'
            tipo_doc = move.l10n_latam_document_type_id.code if move.l10n_latam_document_type_id else '00'
            
            serie = '0'
            numero = '0'
            if move.name and '-' in move.name:
                parts = move.name.split('-')
                serie = parts[0][-4:].lstrip('0') or '0'
                numero = parts[1].lstrip('0') or '0'
            
            key = f"{ruc_prov}-{tipo_doc}-{serie}-{numero}"
            
            odoo_data[key] = {
                'move_id': move.id,
                'fecha': move.invoice_date.strftime('%d/%m/%Y') if move.invoice_date else '',
                'proveedor': (move.partner_id.name or '')[:40],
                'total': abs(move.amount_total),
            }

        # 3. Cruzar la información (El Match)
        lines_to_create = []
        all_keys = set(sunat_data.keys()).union(set(odoo_data.keys()))
        
        for key in all_keys:
            in_sunat = key in sunat_data
            in_odoo = key in odoo_data
            
            s_data = sunat_data.get(key, {})
            o_data = odoo_data.get(key, {})
            
            estado = 'ok'
            diff_total = 0.0
            
            if in_sunat and in_odoo:
                diff_total = abs(s_data.get('total', 0.0) - o_data.get('total', 0.0))
                # Tolerancia de 0.50 céntimos por temas de redondeo
                if diff_total > 0.50: 
                    estado = 'diff'
            elif in_sunat and not in_odoo:
                estado = 'missing_odoo'
            elif in_odoo and not in_sunat:
                estado = 'missing_sunat'
                
            lines_to_create.append((0, 0, {
                'key_ref': key,
                'fecha': s_data.get('fecha') or o_data.get('fecha'),
                'proveedor': s_data.get('proveedor') or o_data.get('proveedor'),
                'sunat_total': s_data.get('total', 0.0),
                'odoo_total': o_data.get('total', 0.0),
                'diferencia': diff_total if estado == 'diff' else 0.0,
                'estado': estado,
                'move_id': o_data.get('move_id', False)
            }))

        # Actualizar el wizard con los resultados y cambiar de vista
        self.line_ids = False 
        self.write({
            'line_ids': lines_to_create,
            'state': 'results'
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sire.conciliation.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

class SireConciliationLine(models.TransientModel):
    _name = 'sire.conciliation.line'
    _description = 'Línea de Conciliación SIRE'

    wizard_id = fields.Many2one('sire.conciliation.wizard', ondelete='cascade')
    key_ref = fields.Char(string='Referencia (RUC-Doc-Ser-Num)')
    fecha = fields.Char(string='Fecha')
    proveedor = fields.Char(string='Proveedor')
    sunat_total = fields.Float(string='Total SUNAT')
    odoo_total = fields.Float(string='Total Odoo')
    diferencia = fields.Float(string='Diferencia')
    move_id = fields.Many2one('account.move', string='Ver en Odoo')
    
    estado = fields.Selection([
        ('ok', 'Conciliado'),
        ('diff', 'Dif. Montos'),
        ('missing_odoo', 'Falta en Odoo'),
        ('missing_sunat', 'Falta en SUNAT')
    ], string='Estado')