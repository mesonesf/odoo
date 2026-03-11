from odoo import models, fields, api, _
from odoo.exceptions import UserError

class TreasuryMovement(models.Model):
    _name = 'treasury.movement.v3'
    _description = 'Movimientos de Tesorería Perú'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string="Número", readonly=True, copy=False, default='/')
    date = fields.Date(string="Fecha", required=True, default=fields.Date.today, tracking=True)
    
    type = fields.Selection([
        ('inbound', 'Ingreso (Cobro)'),
        ('outbound', 'Egreso (Pago)')
    ], string="Tipo", required=True, default='outbound')

    partner_id = fields.Many2one('res.partner', string="Contacto")
    amount = fields.Float(string="Monto total", required=True, tracking=True)
    
    # Cuentas Contables necesarias para el asiento
    payment_account_id = fields.Many2one('account.account', string="Cuenta Caja/Banco", required=True)
    counterpart_account_id = fields.Many2one('account.account', string="Cuenta Contrapartida", required=True)
    journal_id = fields.Many2one('account.journal', string="Diario", required=True)

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('posted', 'Publicado')
    ], string="Estado", default='draft', tracking=True)

    memo = fields.Char(string="Glosa / Referencia", required=True)
    move_id = fields.Many2one('account.move', string="Asiento Contable", readonly=True)

    payment_method = fields.Selection([
        ('001', 'Depósito en Cuenta'),
        ('003', 'Transferencia de Fondos'),
        ('007', 'Cheques'),
        ('008', 'Efectivo'),
        ('999', 'Otros')
    ], string="Medio de Pago", default='003')

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('treasury.movement') or '/'
        return super(TreasuryMovement, self).create(vals)

    def action_post(self):
        for record in self:
            if record.amount <= 0:
                raise UserError("El monto debe ser mayor a cero.")
            
            # Lógica de DEBITO y CREDITO según tipo
            debit_acc = record.payment_account_id.id if record.type == 'inbound' else record.counterpart_account_id.id
            credit_acc = record.counterpart_account_id.id if record.type == 'inbound' else record.payment_account_id.id

            move_vals = {
                'ref': f"{record.name} - {record.memo}",
                'date': record.date,
                'journal_id': record.journal_id.id,
                'move_type': 'entry',
                'line_ids': [
                    (0, 0, {'name': record.memo, 'account_id': debit_acc, 'debit': record.amount, 'credit': 0.0}),
                    (0, 0, {'name': record.memo, 'account_id': credit_acc, 'debit': 0.0, 'credit': record.amount}),
                ],
            }
            move = self.env['account.move'].create(move_vals)
            move.action_post()
            record.write({'move_id': move.id, 'state': 'posted'})
        return True

    def action_draft(self):
        for record in self:
            if record.move_id:
                record.move_id.button_draft()
                record.move_id.button_cancel()
                record.move_id.unlink()
            record.state = 'draft'