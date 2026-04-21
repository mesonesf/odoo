import base64
import csv
import io
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class PurchaseRequisition(models.Model):
    _name = 'purchase.requisition'
    _inherit = ['purchase.requisition', 'approval.mixin']

    vendor_id = fields.Many2one('res.partner', string="Proveedor", required=False)
    approver_ids = fields.Many2many('res.users', relation='pr_approvers_rel')
    approved_user_ids = fields.Many2many('res.users', relation='pr_approved_rel')

    def action_request_approval(self):
        for record in self:
            if not record.line_ids:
                raise UserError("Debes agregar al menos un producto.")
            for line in record.line_ids:
                if line.price_unit <= 0.0:
                    raise UserError(f"Falta precio para {line.product_id.display_name}")
        return super(PurchaseRequisition, self).action_request_approval()

    def action_confirm(self):
        for record in self:
            if record.approval_status == 'draft':
                record.action_request_approval()
            if record.approval_status != 'approved':
                return False
        return super(PurchaseRequisition, self).action_confirm()

    def action_reject(self, reason=False):
        res = super(PurchaseRequisition, self).action_reject(reason=reason) if hasattr(super(PurchaseRequisition, self), 'action_reject') else True
        for record in self:
            record.approval_status = 'draft'
            record.write({'state': 'draft'})
            record.message_post(body="❌ Solicitud Rechazada. Regresada a borrador.")
        return res

    def action_open_import_wizard(self):
        return {
            'name': 'Importar Precios Referenciales',
            'type': 'ir.actions.act_window',
            'res_model': 'requisition.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_requisition_id': self.id}
        }

class PurchaseRequisitionLine(models.Model):
    _inherit = 'purchase.requisition.line'

    is_user_quoter = fields.Boolean(compute='_compute_is_user_quoter')

    def _compute_is_user_quoter(self):
        for line in self:
            line.is_user_quoter = self.env.user.has_group('supply_chain_approvals.group_supply_chain_quoters')

    def write(self, vals):
        if 'price_unit' in vals or 'product_qty' in vals:
            for line in self:
                old_price, old_qty = line.price_unit, line.product_qty
                new_price, new_qty = vals.get('price_unit', old_price), vals.get('product_qty', old_qty)
                cambios = []
                if 'price_unit' in vals and old_price != new_price:
                    cambios.append(f"<li><b>Precio:</b> {old_price} ➔ {new_price}</li>")
                if 'product_qty' in vals and old_qty != new_qty:
                    cambios.append(f"<li><b>Cantidad:</b> {old_qty} ➔ {new_qty}</li>")
                if cambios:
                    line.requisition_id.message_post(body=f"⚠️ <b>Edición en {line.product_id.display_name}:</b><ul>{''.join(cambios)}</ul>")
        return super(PurchaseRequisitionLine, self).write(vals)


# ==========================================
# WIZARD: IMPORTADOR DE PRECIOS DEFINITIVO
# ==========================================
class RequisitionImportWizard(models.TransientModel):
    _name = 'requisition.import.wizard'
    _description = 'Asistente para importar precios'

    requisition_id = fields.Many2one('purchase.requisition', string="Solicitud")
    file = fields.Binary(string="Subir Archivo CSV", required=False)
    file_name = fields.Char(string="Nombre del archivo subido")

    # Función que se ejecuta al presionar el botón de descarga
    def action_download_template(self):
        self.ensure_one()
        if not self.requisition_id:
            return

        # Genera el CSV en memoria
        output = io.StringIO()
        writer = csv.writer(output, delimiter=',')
        writer.writerow(['line_id', 'producto', 'precio_referencial'])
        
        for line in self.requisition_id.line_ids:
            precio = line.price_unit if line.price_unit else 0.0
            writer.writerow([line.id, line.product_id.display_name, precio])
        
        export_file = base64.b64encode(output.getvalue().encode('utf-8'))
        file_name = f'Plantilla_Precios_{self.requisition_id.name or "Borrador"}.csv'

        # Crea el archivo temporal y fuerza la descarga al navegador
        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'type': 'binary',
            'datas': export_file,
            'res_model': 'requisition.import.wizard',
            'res_id': self.id,
            'mimetype': 'text/csv',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def action_import_prices(self):
        if not self.file:
            raise UserError("Debe subir el archivo CSV con los precios llenos antes de procesar.")
        
        try:
            data = base64.b64decode(self.file)
            file_input = io.StringIO(data.decode('utf-8'))
            reader = csv.DictReader(file_input, delimiter=',')
        except Exception:
            raise UserError("El archivo no se pudo leer. Asegúrese de que sea un CSV válido.")
            
        updated_count = 0
        errores_ids = []

        for row in reader:
            line_id_str = row.get('line_id')
            precio_str = row.get('precio_referencial')
            
            if line_id_str and precio_str:
                try:
                    line_id = int(line_id_str)
                    new_price = float(precio_str)
                except ValueError:
                    continue # Ignora filas con formato dañado

                line = self.env['purchase.requisition.line'].browse(line_id)
                
                # VALIDACIÓN ESTRICTA: ¿La línea existe y pertenece a esta solicitud?
                if line.exists() and line.requisition_id.id == self.requisition_id.id:
                    line.write({'price_unit': new_price})
                    updated_count += 1
                else:
                    errores_ids.append(str(line_id))
                    
        if errores_ids:
            raise UserError(f"Error de Integridad: Se encontraron IDs en el archivo ({', '.join(errores_ids)}) que NO pertenecen a esta solicitud de pedido. Verifique que está usando la plantilla correcta.")
                    
        self.requisition_id.message_post(body=f"✅ <b>Importación Masiva (CSV):</b> Se actualizaron los precios de {updated_count} productos.")