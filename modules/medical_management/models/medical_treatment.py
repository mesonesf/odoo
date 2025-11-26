from odoo import models, fields, api, Command
from odoo.exceptions import ValidationError, UserError

class MedicalTreatment(models.Model):
    _name = 'medical.treatment'
    _description = 'Plan de Tratamiento'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'
    
    name = fields.Char(string='Referencia', readonly=True, default='Nuevo')
    
    # ... (Tus campos existentes: patient_id, evaluation_id, etc.) ...
    patient_id = fields.Many2one('medical.patient', string='Paciente', required=True, tracking=True)
    evaluation_id = fields.Many2one('medical.evaluation', string='Evaluación Origen', readonly=True)
    specialty_id = fields.Many2one('medical.specialty', string='Especialidad', required=True)
    practitioner_id = fields.Many2one('hr.employee', string='Especialista Responsable', required=True)
    date = fields.Datetime(string='Fecha de Creación', default=fields.Datetime.now, required=True)
    treatment_type = fields.Selection([
        ('in_person', 'Presencial (Centro Médico)'),
        ('home', 'Domiciliario')
    ], string='Tipo de Tratamiento', required=True, default='in_person', tracking=True)
    
    line_ids = fields.One2many('medical.treatment.line', 'treatment_id', string='Prescripción/Servicios')
    session_ids = fields.One2many('medical.treatment.session', 'treatment_id', string='Sesiones Programadas')
    session_count = fields.Integer(string='N° Sesiones', compute='_compute_session_count', store=True)
    notes = fields.Text(string='Indicaciones Generales')
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('in_progress', 'En Progreso'),
        ('done', 'Finalizado'),
        ('cancel', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)

    # --- NUEVOS CAMPOS PARA FACTURACIÓN ---
    invoice_ids = fields.One2many('account.move', 'treatment_id', string='Facturas')
    invoice_count = fields.Integer(string='N° Facturas', compute='_compute_invoice_count')

    # --- CÓMPUTOS ---
    @api.depends('session_ids')
    def _compute_session_count(self):
        for record in self:
            record.session_count = len(record.session_ids)

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for record in self:
            record.invoice_count = len(record.invoice_ids)

    # --- ACCIONES EXISTENTES ---
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('medical.treatment') or 'Nuevo'
        return super().create(vals_list)

    def action_confirm(self):
        self.state = 'confirmed'

    def action_done(self):
        if self.treatment_type == 'in_person':
            pending_sessions = self.session_ids.filtered(lambda s: s.state not in ['done', 'cancel'])
            if pending_sessions:
                raise ValidationError('No puede finalizar el tratamiento si hay sesiones pendientes.')
        self.state = 'done'
        
    def action_cancel(self):
        self.state = 'cancel'

    # --- NUEVA ACCIÓN: CREAR FACTURA ---
    def action_create_invoice(self):
        """Crea una factura borrador con las líneas del tratamiento"""
        self.ensure_one()
        
        if not self.line_ids:
            raise UserError('No hay servicios ni productos para facturar en este tratamiento.')

        # Preparamos las líneas de la factura
        invoice_lines = []
        for line in self.line_ids:
            invoice_lines.append(Command.create({
                'product_id': line.product_id.id,
                'quantity': line.quantity,
                'name': line.product_id.name, # Descripción
                # Odoo calculará el precio automáticamente basado en el producto
            }))

        # Creamos la factura
        invoice_vals = {
            'move_type': 'out_invoice', # Factura de Cliente
            'partner_id': self.patient_id.partner_id.id, # Usamos el partner_id del paciente
            'invoice_line_ids': invoice_lines,
            'invoice_origin': self.name, # Referencia al tratamiento
            'treatment_id': self.id, # Vinculamos para el smart button
            'invoice_date': fields.Date.context_today(self),
        }
        
        new_invoice = self.env['account.move'].create(invoice_vals)
        
        # Abrimos la factura creada
        return {
            'type': 'ir.actions.act_window',
            'name': 'Factura Borrador',
            'res_model': 'account.move',
            'res_id': new_invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_invoices(self):
        """Botón inteligente para ver las facturas"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Facturas',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
            'context': {'default_partner_id': self.patient_id.partner_id.id}
        }

# ... (Clases MedicalTreatmentLine y MedicalTreatmentSession se mantienen igual) ...
class MedicalTreatmentLine(models.Model):
    _name = 'medical.treatment.line'
    _description = 'Línea de Tratamiento (Producto/Servicio)'
    
    treatment_id = fields.Many2one('medical.treatment', string='Tratamiento', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Producto/Servicio', required=True)
    quantity = fields.Float(string='Cantidad', default=1.0)
    instructions = fields.Char(string='Indicaciones Específicas')

class MedicalTreatmentSession(models.Model):
    # ... (El código de sesiones que ya tenías se mantiene igual) ...
    _name = 'medical.treatment.session'
    _description = 'Sesión de Tratamiento'
    _inherit = ['mail.thread']
    _order = 'date asc'
    
    name = fields.Char(string='Sesión', compute='_compute_name', store=True)
    treatment_id = fields.Many2one('medical.treatment', string='Tratamiento', required=True, ondelete='cascade')
    patient_id = fields.Many2one(related='treatment_id.patient_id', store=True)
    date = fields.Datetime(string='Fecha y Hora', required=True)
    practitioner_id = fields.Many2one('hr.employee', string='Especialista', required=True)
    procedure_notes = fields.Text(string='Procedimiento Realizado')
    state = fields.Selection([
        ('scheduled', 'Programada'),
        ('done', 'Realizada'),
        ('cancel', 'Cancelada')
    ], string='Estado', default='scheduled', tracking=True)

    @api.depends('treatment_id', 'date')
    def _compute_name(self):
        for session in self:
            if session.treatment_id:
                session.name = f"{session.treatment_id.name} - {session.date}"
            else:
                session.name = "Nueva Sesión"

    def action_mark_done(self):
        self.state = 'done'
        if self.treatment_id.state == 'confirmed':
            self.treatment_id.state = 'in_progress'

    def action_cancel(self):
        self.state = 'cancel'

# --- EXTENSIÓN DEL MODELO ACCOUNT.MOVE ---
# Necesitamos añadir un campo a account.move para que el campo One2many funcione
class AccountMove(models.Model):
    _inherit = 'account.move'
    
    treatment_id = fields.Many2one('medical.treatment', string='Tratamiento Origen', readonly=True)