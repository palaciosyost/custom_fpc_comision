from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_agente_comision = fields.Boolean(string="¿Es agente de comisión?")
    objetivo = fields.Float(string="Objetivo")
    monto_objetivo = fields.Float(string="Monto por objetivo")
    tipo_comision = fields.Selection(
        [
            ("ventas", "Ventas comercial"),
            ("servicios", "Servicios"),
        ],
        string="Tipo de Comisión",
    )
    

    def write(self, vals):
        res = super(ResPartner, self).write(vals)
        if "tipo_comision" in vals:
            self.validate_comicion_type()
        return res

    @api.depends("tipo_comision")
    def validate_comicion_type(self):
        res = self.env["res.partner"].search([("tipo_comision", "=", "servicios")])
        print("RESLUTADO DE LA BIQUEDA")
        print(res)
        if self.tipo_comision == "servicios" and res:
            raise UserError(
                _("Ya existe otro agente con el tipo de comision 'Servicios'")
            )
    