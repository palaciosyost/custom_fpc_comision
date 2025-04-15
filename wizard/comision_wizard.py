from odoo import fields, models, api, _
from odoo.exceptions import UserError


class WizardComision(models.TransientModel):
    _name = "wizard.comision.ventas"

    empleado = fields.Many2one("hr.employee", string="Empleado", compute="_get_contacto", store=True)
    contacto_res = fields.Many2one("res.partner", string="Contacto", compute="_get_contacto", store=True)
    comision_jd = fields.Many2one("comisiones.move", string="Comisión del empleado")
    nomina_id = fields.Many2one('hr.payslip', string="Nómina", default=lambda self: self.env.context.get("default_nomina_id"))

    @api.depends("nomina_id")
    def _get_contacto(self):
        for wizard in self:
            if wizard.nomina_id and wizard.nomina_id.employee_id.user_id:
                wizard.empleado = wizard.nomina_id.employee_id
                wizard.contacto_res = wizard.nomina_id.employee_id.user_id.partner_id

    def action_confirm_comision(self):
        for rec in self:
            if not rec.nomina_id:
                raise UserError(_("No se ha detectado una nómina."))
            if not rec.comision_jd:
                raise UserError(_("Debe seleccionar una comisión."))

            rec.nomina_id.input_line_ids.create({
                'name': 'Comisión',
                'amount': rec.comision_jd.gran_total or 0.0,
                'input_type_id': self.env.ref('hr_payroll.ALW').id,  # Usa tu propio tipo si tienes uno
                'payslip_id': rec.nomina_id.id,
            })

        return {'type': 'ir.actions.act_window_close'}
