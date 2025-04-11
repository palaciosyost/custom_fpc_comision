from odoo import models, api, fields, _


class RuleAcelerador(models.Model):
    _name = "rule.acelerador"

    name = fields.Char(string="Nombre")
    limit_sup = fields.Float(string="Limite Superior %", required=True)
    limit_inf = fields.Float(string="Limite Inferior %")
    acelerador = fields.Float(string="Acelerador %")

    