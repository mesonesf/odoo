from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    purchase_approver_ids = fields.Many2many('res.users', 'rel_usr_purch_app', 'uid', 'aid', string="Aprobadores de Compras")
    stock_approver_ids = fields.Many2many('res.users', 'rel_usr_stock_app', 'uid', 'aid', string="Aprobadores de Inventario")
    account_approver_ids = fields.Many2many('res.users', 'rel_usr_acc_app', 'uid', 'aid', string="Aprobadores de Facturas")
    payment_approver_ids = fields.Many2many('res.users', 'rel_usr_pay_app', 'uid', 'aid', string="Aprobadores de Pagos")