# -*- coding: utf-8 -*-
{
    'name': 'Precio Fijo en Dólares (Producto)',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Agrega un campo manual de Precio USD en la ficha del producto',
    'description': """
        Este módulo agrega un campo 'Precio Venta USD' en la ficha del producto.
        Útil para referencias visuales o para usar en fórmulas de listas de precios.
    """,
    'author': 'Mejores Horizontes: Manuel Fernando Mesones Sanchez',
    'depends': ['product', 'sale'],
    'data': [
        'views/product_view.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}