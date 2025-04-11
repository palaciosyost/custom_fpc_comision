from odoo import models, api, fields, _
from odoo.exceptions import UserError
from odoo.fields import Date


class ComisionesRelation(models.Model):
    _name = "comision.line"

    factura_id = fields.Many2one("account.move", string="Factura")
    fecha_factura = fields.Date(string="Fecha de factura")
    total = fields.Float(string="Total vendido")
    comision_id = fields.Many2one("comisiones.move", string="Comision")
    moneda = fields.Many2one("res.currency", string="Moneda")


class Comision(models.Model):
    _name = "comisiones.move"

    name = fields.Char(string="Nombre", readonly=True, copy=False, default="Nuevo")
    fecha_init = fields.Date(string="Fecha de inicio")
    fecha_finish = fields.Date(string="Fecha de corte")
    creado_por = fields.Many2one(
        "res.users", string="Creado por", default=lambda self: self.env.uid
    )
    fecha_create = fields.Date(string="Fecha de creación", default=fields.Date.today)
    users_id = fields.Many2one("res.partner", string="Empleado")
    tipo_comision = fields.Selection(
        [("servicios", "Servicios"), ("ventas", "Comercial")], string="Tipo de comision"
    )
    lineas_comision = fields.One2many(
        "comision.line", "comision_id", string="Lineas de Comision"
    )
    total = fields.Float(string="Total", compute="_get_total_form")
    total_objectivo = fields.Float(
        string="Objetivo (%)", compute="_total_objetivo_form"
    )
    tiene_acelerador = fields.Boolean(string="Tiene Acelerador?")
    total_acelerador = fields.Float(string="Total con acelerador")
    gran_total = fields.Float(string="Gran Total")
    monto_objetivo = fields.Float(string="Monto del objetivo")
    objetivo = fields.Float(string="Objetivo")

    @api.model
    def create(self, vals):
        if vals.get("name", "Nuevo") == "Nuevo":
            vals["name"] = (
                self.env["ir.sequence"].next_by_code("comisiones.move") or "Nuevo"
            )
        return super().create(vals)

    def action_generate_comision(self):
        if self.fecha_init > self.fecha_finish:
            raise UserError(
                _("La fecha de incio no puede ser mayor a la fecha de corte")
            )

        if not self.users_id:
            raise UserError(_("Debe seleccionar al agente de comision"))
        if self.tipo_comision:
            self.generate_comision_comercial()

    def generate_comision_comercial(self):
        if not self.monto_objetivo:
            self.monto_objetivo = self.users_id.monto_objetivo
        if not self.objetivo:
            self.objetivo = self.users_id.objetivo
        userid = self.env.uid
        fecha_inicio = Date.to_string(self.fecha_init)
        fecha_fin = Date.to_string(self.fecha_finish)

        print("DATOS----------")
        print(self.users_id.tipo_comision)
        print(self.tipo_comision)
        id_contacto = self.users_id.id
        if self.users_id.tipo_comision != self.tipo_comision:
            raise UserError(
                _(
                    "El usuario no pertenece al tipo de comision de "
                    + self.tipo_comision
                )
            )
        agente = self.env["res.users"].search(
            [("partner_id", "=", id_contacto)], limit=1
        )
        print("DATOS DE CONSULTA")
        print(agente)
        domain = [
            ("invoice_user_id", "=", agente.id),
            # ("state", "=", "posted"),
            ("date", ">=", fecha_inicio),
            ("date", "<=", fecha_fin),
        ]
        print(domain)
        self.lineas_comision.unlink()
        facturas = self.env["account.move"].search(domain)
        for fac in facturas:
            self.env["comision.line"].create(
                {
                    "comision_id": self.id,
                    "factura_id": fac.id,
                    "fecha_factura": fac.invoice_date,
                    "moneda": fac.currency_id.id,
                    "total": fac.amount_untaxed_signed,
                }
            )
        print(facturas)

    @api.depends("lineas_comision.total")
    def _get_total_form(self):
        for record in self:
            total_monto = sum(line.total for line in record.lineas_comision)
            record.total = total_monto

    @api.depends("total", "users_id.objetivo")
    def _total_objetivo_form(self):
        for record in self:
            objetivo = record.objetivo or 0.00
            total = record.total

            # Evitar división por cero
            if not objetivo or objetivo == 0.0:
                record.total_objectivo = 0.0
                record.tiene_acelerador = False
                continue

            if total == 0:
                record.total_objectivo = 0.0
                record.tiene_acelerador = False
            else:
                porcentaje_objetivo = (total * 100) / objetivo
                record.total_objectivo = porcentaje_objetivo

                if porcentaje_objetivo > 100:
                    record.tiene_acelerador = True
                    record._set_total_acelerador()
                else:
                    record.tiene_acelerador = False

    @api.depends("tiene_acelerador")
    def _set_total_acelerador(self):
        for record in self:
            monto_acelerador = self.total_objectivo - 100
            regla = self.env["rule.acelerador"].search(
                [("limit_sup", ">=", monto_acelerador)], limit=1
            )
            if regla:
                peso = self.total_objectivo / 100
                monto = self.monto_objetivo * peso
                self.total_acelerador = (monto * regla.acelerador) / 100
                self.gran_total = monto + self.total_acelerador