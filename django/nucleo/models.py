"""Modelos de la base de datos.

Reemplazan al almacenamiento del navegador de la versión web estática. Cada
modelo sabe convertirse a la dataclass del motor contable con a_dominio(): así
el motor no depende de Django y se puede probar solo.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models

from .dominio import tipos
from .dominio.cuentas import ETIQUETA_RUBRO, ETIQUETA_TIPO, rubro_efectivo

TIPOS_CUENTA_CHOICES = [(tipo.value, ETIQUETA_TIPO[tipo]) for tipo in tipos.TipoCuenta]
RUBROS_CHOICES = [(rubro.value, ETIQUETA_RUBRO[rubro]) for rubro in tipos.Rubro]


class Caso(models.Model):
    """Un enunciado completo: la empresa, su plan de cuentas y sus asientos."""

    nombre = models.CharField("nombre del caso", max_length=80)
    razon_social = models.CharField("razón social", max_length=120)
    ruc = models.CharField("RUC", max_length=11, blank=True)
    simbolo_moneda = models.CharField("símbolo de la moneda", max_length=5, default="S/")
    periodo_inicio = models.DateField("inicio del período", null=True, blank=True)
    periodo_fin = models.DateField("fin del período", null=True, blank=True)
    tasa_impuesto_renta = models.DecimalField(
        "tasa del impuesto a la renta (%)", max_digits=5, decimal_places=2, default=Decimal("0")
    )
    impuesto_afecta_patrimonio = models.BooleanField(
        "el impuesto a la renta afecta al patrimonio",
        default=True,
        help_text=(
            "Marcado (lo correcto): el patrimonio muestra la utilidad neta y el impuesto "
            "aparece como pasivo por pagar. Sin marcar, el patrimonio muestra la utilidad "
            "antes de impuestos y no se registra la deuda con SUNAT."
        ),
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "caso"
        verbose_name_plural = "casos"
        ordering = ["-actualizado_en"]

    def __str__(self) -> str:
        return self.nombre

    @property
    def periodo_definido(self) -> bool:
        return bool(self.periodo_inicio and self.periodo_fin)

    def empresa_a_dominio(self) -> tipos.Empresa:
        return tipos.Empresa(
            nombre=self.razon_social or self.nombre,
            ruc=self.ruc,
            simbolo_moneda=self.simbolo_moneda,
            periodo_inicio=self.periodo_inicio,
            periodo_fin=self.periodo_fin,
            tasa_impuesto_renta=self.tasa_impuesto_renta,
            impuesto_afecta_patrimonio=self.impuesto_afecta_patrimonio,
        )

    def a_dominio(self) -> tipos.Caso:
        """Arma el caso completo para el motor contable.

        Las líneas se traen con prefetch_related para no golpear la base de
        datos dentro de los bucles de los reportes.
        """
        cuentas = [cuenta.a_dominio() for cuenta in self.cuentas.all()]
        asientos = [
            asiento.a_dominio()
            for asiento in self.asientos.all().prefetch_related("lineas__cuenta")
        ]
        return tipos.Caso(
            id=str(self.pk),
            nombre=self.nombre,
            empresa=self.empresa_a_dominio(),
            cuentas=cuentas,
            asientos=asientos,
        )


class Cuenta(models.Model):
    """Cuenta del plan de cuentas: código, nombre, tipo y clasificación."""

    caso = models.ForeignKey(Caso, related_name="cuentas", on_delete=models.CASCADE)
    codigo = models.CharField("código", max_length=12)
    nombre = models.CharField("nombre", max_length=80)
    tipo = models.CharField("tipo", max_length=12, choices=TIPOS_CUENTA_CHOICES)
    rubro = models.CharField("clasificación", max_length=24, choices=RUBROS_CHOICES, blank=True)

    class Meta:
        verbose_name = "cuenta"
        verbose_name_plural = "cuentas"
        ordering = ["codigo"]
        constraints = [
            models.UniqueConstraint(fields=["caso", "codigo"], name="codigo_unico_por_caso")
        ]

    def __str__(self) -> str:
        return self.codigo + " - " + self.nombre

    def a_dominio(self) -> tipos.Cuenta:
        return tipos.Cuenta(
            id=str(self.pk),
            codigo=self.codigo,
            nombre=self.nombre,
            tipo=tipos.TipoCuenta(self.tipo),
            rubro=tipos.Rubro(self.rubro) if self.rubro else None,
        )

    @property
    def etiqueta_tipo(self) -> str:
        return ETIQUETA_TIPO[tipos.TipoCuenta(self.tipo)]

    @property
    def etiqueta_rubro(self) -> str:
        efectivo = rubro_efectivo(self.a_dominio())
        return ETIQUETA_RUBRO[efectivo] if efectivo else "-"

    @property
    def tiene_movimientos(self) -> bool:
        return self.lineas.exists()


class Asiento(models.Model):
    """Asiento contable. Solo se guarda cuando el Debe iguala al Haber."""

    caso = models.ForeignKey(Caso, related_name="asientos", on_delete=models.CASCADE)
    numero = models.PositiveIntegerField("número")
    fecha = models.DateField("fecha")
    glosa = models.CharField("glosa", max_length=140, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "asiento"
        verbose_name_plural = "asientos"
        ordering = ["fecha", "numero"]

    def __str__(self) -> str:
        return "Asiento numero " + str(self.numero)

    def a_dominio(self) -> tipos.Asiento:
        return tipos.Asiento(
            id=str(self.pk),
            numero=self.numero,
            fecha=self.fecha,
            glosa=self.glosa,
            lineas=[linea.a_dominio() for linea in self.lineas.all()],
        )


class LineaAsiento(models.Model):
    """Una línea del asiento: una cuenta con importe al Debe o al Haber."""

    asiento = models.ForeignKey(Asiento, related_name="lineas", on_delete=models.CASCADE)
    #: En cascada, no protegida: con PROTECT no se podia borrar un caso entero
    #: (al borrar el caso se borran sus cuentas, y las lineas las protegian).
    #: Que no se borre una cuenta con movimientos lo revisa la pantalla del plan
    #: de cuentas con tiene_movimientos, que ademas avisa el motivo.
    cuenta = models.ForeignKey(Cuenta, related_name="lineas", on_delete=models.CASCADE)
    debe = models.DecimalField("debe", max_digits=14, decimal_places=2, default=Decimal("0"))
    haber = models.DecimalField("haber", max_digits=14, decimal_places=2, default=Decimal("0"))
    orden = models.PositiveSmallIntegerField("orden", default=0)

    class Meta:
        verbose_name = "línea del asiento"
        verbose_name_plural = "líneas del asiento"
        ordering = ["orden", "pk"]

    def __str__(self) -> str:
        return str(self.cuenta) + " debe " + str(self.debe) + " haber " + str(self.haber)

    def a_dominio(self) -> tipos.LineaAsiento:
        return tipos.LineaAsiento(
            id=str(self.pk),
            cuenta_id=str(self.cuenta_id),
            debe=self.debe,
            haber=self.haber,
        )


class UsoAsistente(models.Model):
    """Cuántas consultas del asistente llegaron a la API en un día.

    La página es pública: sin un tope global, cualquiera podría gastar el saldo
    de la cuenta. El límite por sesión no alcanza, porque basta con borrar las
    cookies para empezar otra. Esta cuenta es de todo el sitio.
    """

    fecha = models.DateField("fecha", unique=True)
    consultas = models.PositiveIntegerField("consultas a la API", default=0)

    class Meta:
        verbose_name = "uso del asistente"
        verbose_name_plural = "uso del asistente"
        ordering = ["-fecha"]

    def __str__(self) -> str:
        return f"{self.fecha}: {self.consultas}"
