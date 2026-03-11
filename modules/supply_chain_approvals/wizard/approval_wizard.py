from odoo import models, fields
from markupsafe import Markup

class ApprovalWizard(models.TransientModel):
    _name = 'approval.wizard'
    _description = 'Asistente de Aprobación'

    reason = fields.Text(string="Observación / Motivo", required=True)
    res_model = fields.Char()
    res_id = fields.Integer()
    action_type = fields.Selection([('approve', 'Aprobar'), ('reject', 'Rechazar')])

    def action_confirm(self):
        record = self.env[self.res_model].browse(self.res_id)
        
        action_label = "FIRMADO / APROBADO" if self.action_type == 'approve' else "RECHAZADO"
        color = "#e6fffa" if self.action_type == 'approve' else "#ffe6e6"
        border = "green" if self.action_type == 'approve' else "red"
        
        # 1. Definimos la plantilla HTML 100% segura para Odoo
        html_template = Markup("""
            <div style="background-color: %s; padding: 10px; border-left: 5px solid %s;">
                <strong>Acción: %s</strong><br/>
                Usuario: %s<br/>
                Comentario: %s
            </div>
        """)
        
        # 2. Inyectamos las variables de forma segura
        msg_body = html_template % (color, border, action_label, self.env.user.name, self.reason)

        # 3. Publicamos como Nota Interna
        record.message_post(
            body=msg_body,
            message_type='comment',
            subtype_xmlid='mail.mt_note'
        )

        if self.action_type == 'approve':
            record.action_approve_process()
        else:
            record.action_reject_process()