from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta

# --- NUEVO: Heredamos la línea de factura para saber si ya se usó ---
class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    
    asset_peru_ids = fields.One2many('account.asset.peru.v3', 'invoice_line_id', string='Activos Vinculados')


class AccountAssetPeru(models.Model):
    _name = 'account.asset.peru.v3'
    _description = 'Activos Fijos Perú v3'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Nombre del Activo", required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('open', 'En Curso'),
        ('close', 'Cerrado')
    ], string='Estado', default='draft', tracking=True)
    
    # Campo de cantidad
    quantity = fields.Float(string="Cantidad", default=1.0)
    purchase_date = fields.Date(string="Fecha de Compra", required=True, default=fields.Date.today)
    purchase_value = fields.Float(string="Valor de Compra", required=True)
    salvage_value = fields.Float(string="Valor Residual", default=0.0)
    method_period = fields.Integer(string='Meses de Vida Útil', default=60)
    
    # --- CAMPO MODIFICADO: Filtro anti-duplicidad (asset_peru_ids = False) ---
    invoice_line_id = fields.Many2one(
        'account.move.line', 
        string="Línea de Factura",
        domain="[('move_id.move_type', '=', 'in_invoice'), ('parent_state', '=', 'posted'), ('account_id.code', '=like', '33%'), ('asset_peru_ids', '=', False)]"
    )
    
    asset_account_id = fields.Many2one('account.account', string="Cuenta de Activo (33)", required=True)
    depreciation_account_id = fields.Many2one('account.account', string="Cuenta de Gasto (68)", required=True)
    accumulated_account_id = fields.Many2one('account.account', string="Cuenta Depreciación Acumulada (39)", required=True)
    journal_id = fields.Many2one('account.journal', string="Diario", required=True)
    
    depreciation_line_ids = fields.One2many('account.asset.peru.line.v3', 'asset_id', string="Líneas de Depreciación")

    # --- NUEVA FUNCIÓN: Autocompletar datos de la factura ---
    @api.onchange('invoice_line_id')
    def _onchange_invoice_line_id(self):
        if self.invoice_line_id:
            self.name = self.invoice_line_id.name or f"Activo s/ Factura {self.invoice_line_id.move_id.name}"
            self.purchase_value = self.invoice_line_id.debit
            self.purchase_date = self.invoice_line_id.move_id.invoice_date or self.invoice_line_id.date
            self.asset_account_id = self.invoice_line_id.account_id.id
            self.quantity = self.invoice_line_id.quantity  # Autocompleta la cantidad

    def compute_depreciation_board(self):
        for record in self:
            record.depreciation_line_ids.unlink()
            if record.purchase_value <= record.salvage_value:
                raise UserError("El valor de compra debe ser mayor al valor residual.")
            
            amount_to_depreciate = record.purchase_value - record.salvage_value
            monthly_amount = amount_to_depreciate / record.method_period
            
            lines = []
            current_date = record.purchase_date
            for i in range(record.method_period):
                current_date = current_date + relativedelta(months=1)
                lines.append((0, 0, {
                    'name': f"Depreciación Mes {i+1}",
                    'depreciation_date': current_date,
                    'amount': monthly_amount,
                    'is_posted': False,
                }))
            record.write({'depreciation_line_ids': lines, 'state': 'open'})

    def action_post_pending_depreciation(self):
        for record in self:
            pending_lines = record.depreciation_line_ids.filtered(lambda l: not l.is_posted and l.depreciation_date <= fields.Date.today())
            if not pending_lines:
                raise UserError("No hay cuotas pendientes de contabilizar a la fecha.")
            
            for line in pending_lines:
                move_vals = {
                    'ref': f"DEP {record.name}: {line.name}",
                    'date': line.depreciation_date,
                    'journal_id': record.journal_id.id,
                    'move_type': 'entry',
                    'line_ids': [
                        (0, 0, {'name': line.name, 'account_id': record.depreciation_account_id.id, 'debit': line.amount, 'credit': 0.0}),
                        (0, 0, {'name': line.name, 'account_id': record.accumulated_account_id.id, 'debit': 0.0, 'credit': line.amount}),
                    ],
                }
                move = self.env['account.move'].create(move_vals)
                move.action_post()
                line.write({'is_posted': True, 'move_id': move.id})


class AccountAssetPeruLine(models.Model):
    _name = 'account.asset.peru.line.v3'
    _description = 'Línea de Depreciación'
    _order = 'depreciation_date asc'

    asset_id = fields.Many2one('account.asset.peru.v3', string="Activo", ondelete='cascade')
    name = fields.Char(string="Referencia")
    depreciation_date = fields.Date(string="Fecha")
    amount = fields.Float(string="Monto")
    is_posted = fields.Boolean(string="Contabilizado", default=False)
    move_id = fields.Many2one('account.move', string="Asiento Contable", readonly=True)