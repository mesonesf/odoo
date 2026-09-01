import base64
from unittest.mock import patch, Mock
from odoo.tests.common import TransactionCase

class TestSunatRucValidation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestSunatRucValidation, cls).setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.batch_model = cls.env['sunat.ruc.batch']
        cls.line_model = cls.env['sunat.ruc.line']

    def test_01_read_txt_and_create_lines(self):
        """Test reading a valid TXT file creates lines"""
        txt_content = "10123456789\n20123456781\n"
        encoded_content = base64.b64encode(txt_content.encode('utf-8'))
        batch = self.batch_model.create({
            'txt_file': encoded_content
        })
        batch.action_confirm()
        
        lines = self.line_model.search([('batch_id', '=', batch.id)])
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].ruc, "10123456789")
        self.assertEqual(lines[0].status, "pending")

    def test_02_invalid_ruc_length(self):
        """Test reading a TXT file with invalid RUC length"""
        txt_content = "10123\n" # invalid length
        encoded_content = base64.b64encode(txt_content.encode('utf-8'))
        batch = self.batch_model.create({
            'txt_file': encoded_content
        })
        batch.action_confirm()
        lines = self.line_model.search([('batch_id', '=', batch.id)])
        self.assertEqual(len(lines), 0, "No lines should be created for invalid RUCs")

    @patch('odoo.addons.sunat_ruc_validation.models.sunat_ruc_line.requests.post')
    def test_03_api_success(self, mock_post):
        """Test API success response 200"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": {
                "ruc": "20123456781",
                "nombre_o_razon_social": "EMPRESA DE PRUEBA S.A.C.",
                "estado": "ACTIVO",
                "condicion": "HABIDO",
                "direccion": "AV. LOS INCAS 123",
                "direccion_completa": "AV. LOS INCAS 123",
                "tipo_contribuyente": "SOCIEDAD ANONIMA CERRADA",
                "fecha_inscripcion": "2010-01-01",
                "actividades_economicas": ["1234 - ACTIVIDAD DE PRUEBA"]
            }
        }
        mock_post.return_value = mock_response

        batch = self.batch_model.create({})
        line = self.line_model.create({
            'batch_id': batch.id,
            'ruc': '20123456781',
            'status': 'pending'
        })

        line.process_api()
        
        self.assertEqual(line.status, 'success')
        self.assertEqual(line.nombre_o_razon_social, "EMPRESA DE PRUEBA S.A.C.")
        self.assertEqual(line.estado, "ACTIVO")

    @patch('odoo.addons.sunat_ruc_validation.models.sunat_ruc_line.requests.post')
    def test_04_api_400_invalid_ruc(self, mock_post):
        """Test API response 400 Invalid RUC"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response

        batch = self.batch_model.create({})
        line = self.line_model.create({
            'batch_id': batch.id,
            'ruc': '00000000000',
            'status': 'pending'
        })

        line.process_api()
        
        self.assertEqual(line.status, 'failed')
        self.assertEqual(line.error_message, "El RUC es incorrecto")

    @patch('odoo.addons.sunat_ruc_validation.models.sunat_ruc_line.requests.post')
    def test_05_api_404_not_found(self, mock_post):
        """Test API response 404 RUC not found"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_post.return_value = mock_response

        batch = self.batch_model.create({})
        line = self.line_model.create({
            'batch_id': batch.id,
            'ruc': '20123456789',
            'status': 'pending'
        })

        line.process_api()
        
        self.assertEqual(line.status, 'failed')
        self.assertEqual(line.error_message, "El RUC no existe")

    @patch('odoo.addons.sunat_ruc_validation.models.sunat_ruc_line.requests.post')
    def test_06_api_503_retry(self, mock_post):
        """Test API response 503 Retry"""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_post.return_value = mock_response

        batch = self.batch_model.create({})
        line = self.line_model.create({
            'batch_id': batch.id,
            'ruc': '20123456789',
            'status': 'pending'
        })

        # Process should ideally throw a RetryableJobError for queue_job to retry
        from odoo.addons.queue_job.exception import RetryableJobError
        with self.assertRaises(RetryableJobError):
            line.process_api()
        
        self.assertEqual(line.status, 'pending')
        self.assertIn("Servicio no disponible", line.error_message)
