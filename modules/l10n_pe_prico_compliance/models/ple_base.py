from odoo import models

class PleReportBase(models.AbstractModel):
    _name = 'ple.report.base'
    _description = 'Motor Base para Reportes PLE y SIRE'

    def _get_ple_filename(self, company, period_str, book_identifier, contains_data=True, currency_code='PEN'):
        """
        Genera la nomenclatura oficial de SUNAT.
        Estructura: LE + RUC(11) + AAAA(4) + MM(2) + DD(2) + ID_LIBRO(6) + CodOperacion(2) + Moneda(1) + Indicador(1) + Estado(1) + .txt
        Ejemplo Libro Diario 5.1: LE2012345678920260300050100001111.txt
        """
        ruc = company.vat or '00000000000'
        has_data = '1' if contains_data else '0'
        
        # Moneda: SUNAT usa '1' para Soles, '2' para Dólares (varía según el libro, parametrizado por defecto a PEN)
        moneda_indicador = '1' if currency_code == 'PEN' else '2'

        # El bloque final '111' suele representar: PLE (1) + Con Datos/Sin Datos (1 o 0) + Moneda Nacional (1)
        filename = f"LE{ruc}{period_str}00{book_identifier}001{has_data}{moneda_indicador}1.txt"
        return filename

    def _format_amount(self, amount):
        """
        Asegura que todos los montos en el TXT tengan estrictamente 2 decimales,
        incluso si son enteros (ej. 100 -> 100.00).
        """
        if not amount:
            return "0.00"
        return "{:.2f}".format(amount)