from odoo import models, fields, api, Command
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta

class MedicalTreatment(models.Model):
    _name = 'medical.treatment'
    _description = 'Plan de Tratamiento'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'
    
    name = fields.Char(string='Referencia', readonly=True, default='Nuevo')
    
    patient_id = fields.Many2one('medical.patient', string='Paciente', required=True, tracking=True)
    evaluation_id = fields.Many2one('medical.evaluation', string='Evaluación Origen', readonly=True)
    specialty_id = fields.Many2one('medical.specialty', string='Especialidad', required=True)
    practitioner_id = fields.Many2one('hr.employee', string='Especialista Responsable', required=True)
    date = fields.Datetime(string='Fecha de Creación', default=fields.Datetime.now, required=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company)
    
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

    invoice_ids = fields.One2many('account.move', 'treatment_id', string='Facturas')
    invoice_count = fields.Integer(string='N° Facturas', compute='_compute_invoice_count')

    @api.depends('session_ids')
    def _compute_session_count(self):
        for record in self:
            record.session_count = len(record.session_ids)

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for record in self:
            record.invoice_count = len(record.invoice_ids)

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

    def action_create_invoice(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError('No hay servicios ni productos para facturar en este tratamiento.')

        invoice_lines = []
        for line in self.line_ids:
            invoice_lines.append(Command.create({
                'product_id': line.product_id.id,
                'quantity': line.quantity,
                'name': line.product_id.name,
            }))

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.patient_id.partner_id.id,
            'invoice_line_ids': invoice_lines,
            'invoice_origin': self.name,
            'treatment_id': self.id,
            'invoice_date': fields.Date.context_today(self),
        }
        new_invoice = self.env['account.move'].create(invoice_vals)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Factura Borrador',
            'res_model': 'account.move',
            'res_id': new_invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Facturas',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
            'context': {'default_partner_id': self.patient_id.partner_id.id}
        }

class MedicalTreatmentLine(models.Model):
    _name = 'medical.treatment.line'
    _description = 'Línea de Tratamiento (Producto/Servicio)'
    
    treatment_id = fields.Many2one('medical.treatment', string='Tratamiento', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Producto/Servicio', required=True)
    
    # --- NUEVOS CAMPOS DE PRECIO ---
    price_unit = fields.Float(string='Precio Unitario', digits='Product Price')
    quantity = fields.Float(string='Cantidad', default=1.0)
    price_subtotal = fields.Monetary(string='Subtotal', compute='_compute_subtotal', currency_field='currency_id')
    
    # Campo necesario para manejar monedas (si usas la moneda de la compañía)
    currency_id = fields.Many2one('res.currency', related='treatment_id.company_id.currency_id')
    instructions = fields.Char(string='Indicaciones Específicas')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Al elegir producto, jalar su precio de venta automáticamente"""
        if self.product_id:
            self.price_unit = self.product_id.list_price

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        """Calcular Precio x Cantidad"""
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit



class MedicalTreatmentSession(models.Model):
    _name = 'medical.treatment.session'
    _description = 'Sesión de Tratamiento'
    _inherit = ['mail.thread']
    _order = 'date asc'
    _rec_name = 'patient_id' 

    name = fields.Char(string='Sesión', compute='_compute_name', store=True)
    treatment_id = fields.Many2one('medical.treatment', string='Tratamiento', required=True, ondelete='cascade')
    
    specialty_id = fields.Many2one(
        related='treatment_id.specialty_id', 
        string='Especialidad', 
        store=True, 
        readonly=True
    )

    patient_id = fields.Many2one(related='treatment_id.patient_id', store=True)
    date = fields.Datetime(string='Fecha y Hora', required=True)
    practitioner_id = fields.Many2one('hr.employee', string='Especialista', required=True)
    procedure_notes = fields.Text(string='Procedimiento Realizado')
    state = fields.Selection([
        ('scheduled', 'Programada'),
        ('done', 'Realizada'),
        ('cancel', 'Cancelada')
    ], string='Estado', default='scheduled', tracking=True)

    # Campo para vincular con el Calendario de Odoo
    calendar_event_id = fields.Many2one('calendar.event', string='Evento de Calendario', ondelete='set null')

    @api.depends('treatment_id', 'date')
    def _compute_name(self):
        for session in self:
            if session.treatment_id:
                session.name = f"{session.treatment_id.name} - {session.date}"
            else:
                session.name = "Nueva Sesión"

    # --- LÓGICA DE SINCRONIZACIÓN CON CALENDARIO ---

    def _sync_to_calendar(self):
        """Crea o actualiza el evento en el calendario de Odoo"""
        for record in self:
            if not record.date or not record.patient_id:
                continue
            
            # Participantes: Paciente + Especialista (si tiene usuario en Odoo)
            partner_ids = [record.patient_id.partner_id.id]
            if record.practitioner_id.user_id:
                partner_ids.append(record.practitioner_id.user_id.partner_id.id)

            vals = {
                'name': f"Cita: {record.patient_id.name} - {record.specialty_id.name or ''}",
                'start': record.date,
                'stop': record.date + timedelta(hours=1), # Duración de 1 hora
                'partner_ids': [Command.set(partner_ids)],
                'description': record.procedure_notes or f"Sesión del Plan {record.treatment_id.name}",
                'user_id': record.practitioner_id.user_id.id if record.practitioner_id.user_id else self.env.user.id,
            }

            if record.calendar_event_id:
                record.calendar_event_id.write(vals)
            else:
                event = self.env['calendar.event'].with_context(no_mail_index=False).create(vals)
                record.calendar_event_id = event

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._sync_to_calendar()
        return records

    def write(self, vals):
        result = super().write(vals)
        if any(field in vals for field in ['date', 'practitioner_id', 'patient_id', 'procedure_notes']):
            self._sync_to_calendar()
        return result

    def unlink(self):
        """Elimina el evento del calendario si se borra la sesión"""
        events_to_delete = self.mapped('calendar_event_id')
        res = super().unlink()
        if events_to_delete:
            events_to_delete.unlink()
        return res

    # --- ACCIONES ---

    def action_mark_done(self):
        self.state = 'done'
        if self.treatment_id.state == 'confirmed':
            self.treatment_id.state = 'in_progress'

    def action_cancel(self):
        self.state = 'cancel'
        if self.calendar_event_id:
            self.calendar_event_id.unlink()

class AccountMove(models.Model):
    _inherit = 'account.move'
    treatment_id = fields.Many2one('medical.treatment', string='Tratamiento Origen', readonly=True)