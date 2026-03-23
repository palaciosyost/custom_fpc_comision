from odoo import models, api, fields, _
from odoo.exceptions import UserError
from odoo.fields import Date

import logging
_logger = logging.getLogger(__name__)
class LineaAcoount(models.Model):
    _inherit = "account.move.line"

    subtotal_base = fields.Float(
        string="Subtotal base",
        compute="_compute_subtotal_base",
        store=True
    )

    @api.depends('price_subtotal', 'currency_id', 'move_id.currency_id', 'move_id.invoice_date')
    def _compute_subtotal_base(self):
        usd = self.env.ref('base.USD')
        pen = self.env.ref('base.PEN')

        for rec in self:
            if rec.move_id.currency_id == usd:
                rec.subtotal_base = rec.currency_id._convert(
                    rec.price_subtotal,
                    pen,
                    rec.company_id,
                    rec.move_id.invoice_date
                )
            else:
                rec.subtotal_base = rec.price_subtotal


class ComisionesRelation(models.Model):
    _name = "comision.line"

    factura_id = fields.Many2one("account.move", string="Factura")
    fecha_factura = fields.Date(string="Fecha de factura")
    total = fields.Float(string="Total vendido")
    comision_id = fields.Many2one("comisiones.move", string="Comision")
    moneda = fields.Many2one("res.currency", string="Moneda")
    tipo_cambio = fields.Float(
        string="T/C", readonly=True,
    )
    moneda_base = fields.Many2one(
        "res.currency",
        string="Moneda base",
        default=lambda self: self.env.ref('base.PEN'),
    )


class ComisionesRelationItem(models.Model):
    _name = "comision.line.item"

    name = fields.Char(string="Nombre")
    porcentaje = fields.Float(string="Porcentaje")
    comision_id = fields.Many2one(
        "comisiones.move", string="Linea de comision")
    moneda = fields.Many2one("res.currency", string="Moneda")
    tipo_cambio = fields.Float(
        string="T/C", readonly=True,
    )
    moneda_base = fields.Many2one(
        "res.currency",
        string="Moneda base",
        default=lambda self: self.env.ref('base.PEN'),
    )
    fecha_factura = fields.Date(string="Fecha de factura")
    total = fields.Float(string="Total vendido")
    factura_id = fields.Many2one("account.move", string="Factura")


class Comision(models.Model):
    _name = "comisiones.move"
    _order = "name desc"

    name = fields.Char(string="Nombre", readonly=True,
                       copy=False, default="Nuevo")
    fecha_init = fields.Date(string="Fecha de inicio")
    fecha_finish = fields.Date(string="Fecha de corte")
    creado_por = fields.Many2one(
        "res.users", string="Creado por", default=lambda self: self.env.uid
    )
    fecha_create = fields.Date(
        string="Fecha de creación", default=fields.Date.today)
    users_id = fields.Many2one("res.partner", string="Empleado")
    tipo_comision = fields.Selection(
        [("servicios", "Servicios"), ("ventas", "Comercial")], string="Tipo de comision"
    )
    lineas_comision = fields.One2many(
        "comision.line", "comision_id", string="Lineas de Comision"
    )
    total = fields.Float(string="Total ventas", compute="_get_total_form")
    total_objectivo = fields.Float(
        string="Objetivo (%)", compute="_total_objetivo_form"
    )
    tiene_acelerador = fields.Boolean(string="Tiene Acelerador?")
    total_acelerador = fields.Float(string="Acelerador")
    gran_total = fields.Float(string="Gran Total")
    monto_objetivo = fields.Float(string="Monto del objetivo")
    pre_total = fields.Float(string="Pre total")
    objetivo = fields.Float(string="Objetivo")
    moneda_base = fields.Many2one(
        "res.currency",
        string="Moneda",
        default=lambda self: self.env.ref('base.PEN'),
    )
    is_procentaje = fields.Boolean(string="¿Es comision por porcentaje?")
    p_equipo = fields.Integer(string="% por equipos")
    p_repuestos = fields.Integer(string="% por repuestos")
    p_servicios = fields.Integer(string="% por servicios")

    lineas_comision_item = fields.Many2many(
        "account.move.line", string="Lineas de Comision por item"
    )
    
    total_comision_porcentage = fields.Float(string="Total comision")
    total_comision_servicios = fields.Float(string="Total por Servicios")
    total_comision_repuestos = fields.Float(string="Total por Repuestos")
    total_comision_equipos = fields.Float(string="Total por Equipos")


    @api.onchange("users_id")
    def _onchange_users_id(self):
        if self.users_id:
            self.is_procentaje = self.users_id.is_procentaje
            self.p_equipo = self.users_id.p_equipo
            self.p_repuestos = self.users_id.p_repuestos
            self.p_servicios = self.users_id.p_servicios

    @api.model
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nuevo") == "Nuevo":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "comisiones.move") or "Nuevo"
                )
        return super().create(vals_list)



    def action_generate_comision(self):
        if not self.fecha_init or not self.fecha_finish:
            raise UserError(
                _("La fecha de inicio y fin tiene que estar establecido")
            )
        if self.fecha_init > self.fecha_finish:
            raise UserError(
                _("La fecha de incio no puede ser mayor a la fecha de corte")
            )

        if not self.users_id:
            raise UserError(_("Debe seleccionar al agente de comision"))

        if self.tipo_comision and self.is_procentaje == False:
            self.generate_comision_comercial()
        if self.tipo_comision and self.is_procentaje == True:
            self.generate_comision_porcentaje()

    def generate_comision_porcentaje(self):
        _logger.info("=== INICIO generate_comision_porcentaje ===")

        _logger.info("Empleado (partner): %s", self.users_id.name)
        _logger.info("Fecha inicio: %s | Fecha fin: %s", self.fecha_init, self.fecha_finish)

        user = self.env["res.users"].search([
            ("partner_id", "=", self.users_id.id)
        ], limit=1)

        _logger.info("Usuario encontrado: %s (ID: %s)", user.name if user else None, user.id if user else None)

        items_factura = self.env["account.move.line"].search([
            ("move_id.invoice_user_id", "=", user.id),
            ("move_id.date", ">=", self.fecha_init),
            ("move_id.date", "<=", self.fecha_finish),
            ("product_id", "!=", False),
            ("move_id.move_type", "=", "out_invoice"),
            ("move_id.state", "=", "posted"),
            ("move_id.edi_state", "=", "sent"),
            ("move_id.payment_state", "in", ["paid", "in_payment"]),
        ])

        _logger.info("Cantidad de items encontrados: %s", len(items_factura))

        # Mostrar algunos IDs
        _logger.info("IDs de líneas: %s", items_factura.ids[:10])

        # Asignar Many2many
        self.lineas_comision_item = [(6, 0, items_factura.ids)]

        _logger.info("Asignación de lineas_comision_item completada")

        # Validación porcentajes
        if not (self.p_equipo and self.p_repuestos and self.p_servicios):
            _logger.warning("Porcentajes incompletos: equipo=%s, repuestos=%s, servicios=%s",
                            self.p_equipo, self.p_repuestos, self.p_servicios)
            raise UserError("Complete el % de equipos, repuestos y servicios")

        # Inicializar
        total_equipos = 0.0
        total_repuestos = 0.0
        total_servicios = 0.0

        _logger.info("=== INICIO CALCULO ===")

        for line in items_factura:
            product = line.product_id

            if not product:
                _logger.warning("Linea sin producto ID: %s", line.id)
                continue

            subtotal = line.subtotal_base

            _logger.info(
                "Linea ID: %s | Producto: %s | Subtotal_base: %s",
                line.id, product.name, subtotal
            )

            # EQUIPO
            if getattr(product, "is_equipo", False):
                comision = subtotal * (self.p_equipo / 100)
                total_equipos += comision

                _logger.info(
                    " -> EQUIPO | %%=%s | Comisión=%s",
                    self.p_equipo, comision
                )

            # REPUESTO
            elif getattr(product, "is_repuesto", False):
                comision = subtotal * (self.p_repuestos / 100)
                total_repuestos += comision

                _logger.info(
                    " -> REPUESTO | %%=%s | Comisión=%s",
                    self.p_repuestos, comision
                )

            # SERVICIO
            elif product.type == "service":
                comision = subtotal * (self.p_servicios / 100)
                total_servicios += comision

                _logger.info(
                    " -> SERVICIO | %%=%s | Comisión=%s",
                    self.p_servicios, comision
                )
            else:
                _logger.info(" -> Producto no clasificado")

        _logger.info("=== RESULTADOS ===")
        _logger.info("Total equipos: %s", total_equipos)
        _logger.info("Total repuestos: %s", total_repuestos)
        _logger.info("Total servicios: %s", total_servicios)

        total_final = total_equipos + total_repuestos + total_servicios

        _logger.info("TOTAL COMISION: %s", total_final)

        # Guardar
        self.total_comision_equipos = total_equipos
        self.total_comision_repuestos = total_repuestos
        self.total_comision_servicios = total_servicios
        self.total_comision_porcentage = total_final

        _logger.info("=== FIN generate_comision_porcentaje ===")


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
            ("move_type", "=", "pout_invoiced"),
            ("edi_state", "=", "sent"),
            ("payment_state", "in", ["paid", "in_payment"]),
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
                    "tipo_cambio": fac.tipo_cambio_dolar_sistema,
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
                self.pre_total = (self.total_objectivo /
                                  100) * self.monto_objetivo
                self.gran_total = monto + self.total_acelerador
