from odoo import models, fields

# 2.1 Origen Típico
class CrmOrigen(models.Model):
    _name = 'crm.origen'
    _description = 'Origen Típico del Contacto'
    name = fields.Char('Nombre', required=True)

# 2.3 Nivel 1: Linea de Producto
class CrmLineaProducto(models.Model):
    _name = 'crm.linea.producto'
    _description = 'Línea de Producto'
    name = fields.Char('Línea', required=True)

# 2.3 Nivel 2: Tipo de Producto (Hijo de Línea)
class CrmTipoProducto(models.Model):
    _name = 'crm.tipo.producto'
    _description = 'Tipo de Producto'
    
    name = fields.Char('Tipo', required=True)
    linea_id = fields.Many2one('crm.linea.producto', string='Línea Padre', required=True)

# 2.5 Normativa
class CrmNormativa(models.Model):
    _name = 'crm.normativa'
    _description = 'Normativa Aplicable'
    name = fields.Char('Normativa', required=True)

# 2.6 Dolor (Pain Points)
class CrmDolor(models.Model):
    _name = 'crm.dolor'
    _description = 'Dolor del Cliente'
    name = fields.Char('Dolor Principal', required=True)