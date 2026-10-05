"""Formularios. Validan con las reglas del motor contable, no por su cuenta.

Así la regla Debe = Haber y la validación de cuentas viven en un solo lugar y
valen igual para la interfaz, para el admin y para los scripts.
"""

from __future__ import annotations

from decimal import Decimal

from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from .datos.casos_demo import OPCIONES_CASO_DEMO
from .datos.plantillas_cuentas import OPCIONES_PLANTILLA
from .dominio import tipos
from .dominio.asientos import validar_asiento
from .dominio.cuentas import (
    ETIQUETA_RUBRO,
    movimiento_desde_signo,
    rubros_permitidos,
    validar_cuenta,
)
from .dominio.numeros import es_cero, redondear
from .models import Asiento, Caso, Cuenta, LineaAsiento
from .servicios.pdf import SECCIONES


class CasoForm(forms.ModelForm):
    """Datos de la empresa del caso. Es el mismo formulario de Configuración."""

    class Meta:
        model = Caso
        fields = [
            "nombre",
            "razon_social",
            "ruc",
            "simbolo_moneda",
            "periodo_inicio",
            "periodo_fin",
            "tasa_impuesto_renta",
            "impuesto_afecta_patrimonio",
        ]
        widgets = {
            "periodo_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "periodo_fin": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def clean_ruc(self):
        ruc = (self.cleaned_data.get("ruc") or "").strip()
        if ruc and (len(ruc) != 11 or not ruc.isdigit()):
            raise forms.ValidationError("El RUC tiene 11 dígitos.")
        return ruc

    def clean_tasa_impuesto_renta(self):
        tasa = self.cleaned_data.get("tasa_impuesto_renta") or Decimal("0")
        if tasa < 0 or tasa > 100:
            raise forms.ValidationError("La tasa va de 0 a 100.")
        return tasa

    def clean(self):
        datos = super().clean()
        inicio = datos.get("periodo_inicio")
        fin = datos.get("periodo_fin")
        if inicio and fin and fin < inicio:
            self.add_error("periodo_fin", "El fin del período no puede ser anterior al inicio.")
        return datos


class CasoNuevoForm(CasoForm):
    """Caso nuevo: además de la empresa, elige el plan de cuentas inicial."""

    plantilla_cuentas = forms.ChoiceField(
        label="Plan de cuentas inicial", choices=OPCIONES_PLANTILLA, initial="pcge"
    )


class CuentaForm(forms.ModelForm):
    """Cuenta del plan. La validación real la hace validar_cuenta() del dominio."""

    class Meta:
        model = Cuenta
        fields = ["codigo", "nombre", "tipo", "rubro"]

    def __init__(self, *args, caso=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.caso = caso or getattr(self.instance, "caso", None)
        self.fields["rubro"].required = False
        self.fields["rubro"].choices = [("", "Automática según el tipo")] + [
            (rubro.value, ETIQUETA_RUBRO[rubro]) for rubro in tipos.Rubro
        ]

    def clean(self):
        datos = super().clean()
        existentes = []
        if self.caso is not None:
            existentes = [cuenta.a_dominio() for cuenta in self.caso.cuentas.all()]
        errores = validar_cuenta(
            datos.get("codigo", ""),
            datos.get("nombre", ""),
            datos.get("tipo", ""),
            existentes,
            id_en_edicion=str(self.instance.pk) if self.instance.pk else None,
        )
        for campo, mensaje in errores.items():
            self.add_error(campo, mensaje)

        tipo = datos.get("tipo")
        rubro = datos.get("rubro")
        if tipo and rubro:
            permitidos = [item.value for item in rubros_permitidos(tipos.TipoCuenta(tipo))]
            if rubro not in permitidos:
                self.add_error("rubro", "Esa clasificación no corresponde a este tipo de cuenta.")
        return datos


class AsientoForm(forms.ModelForm):
    class Meta:
        model = Asiento
        fields = ["fecha", "glosa"]
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


class LineaAsientoForm(forms.ModelForm):
    """Una línea del asiento. Acepta el modo Debe/Haber y el modo de signo."""

    MODO_SIGNO = [("", "Debe / Haber"), ("+", "Aumenta (+)"), ("-", "Disminuye (-)")]

    signo = forms.ChoiceField(label="Signo", choices=MODO_SIGNO, required=False)
    monto = forms.DecimalField(
        label="Monto", required=False, max_digits=14, decimal_places=2, min_value=Decimal("0")
    )

    class Meta:
        model = LineaAsiento
        fields = ["cuenta", "debe", "haber"]

    def __init__(self, *args, caso=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.caso = caso
        if caso is not None:
            self.fields["cuenta"].queryset = caso.cuentas.all()
        self.fields["cuenta"].required = False
        self.fields["debe"].required = False
        self.fields["haber"].required = False

    def clean(self):
        datos = super().clean()
        cuenta = datos.get("cuenta")
        signo = datos.get("signo") or ""
        monto = datos.get("monto") or Decimal("0")

        # Modo de signo: el dominio decide si el importe va al Debe o al Haber.
        if cuenta is not None and signo and not es_cero(monto):
            debe, haber = movimiento_desde_signo(tipos.TipoCuenta(cuenta.tipo), signo, monto)
            datos["debe"] = debe
            datos["haber"] = haber

        datos["debe"] = redondear(datos.get("debe") or Decimal("0"))
        datos["haber"] = redondear(datos.get("haber") or Decimal("0"))
        return datos


class LineasFormSet(BaseInlineFormSet):
    """Revisa el asiento completo con validar_asiento() del dominio."""

    def __init__(self, *args, caso=None, formulario_asiento=None, **kwargs):
        self.caso = caso
        self.formulario_asiento = formulario_asiento
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs["caso"] = self.caso
        return kwargs

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        if self.caso is None:
            return

        lineas = []
        for indice, formulario in enumerate(self.forms):
            datos = getattr(formulario, "cleaned_data", None) or {}
            if datos.get("DELETE"):
                continue
            cuenta = datos.get("cuenta")
            debe = datos.get("debe") or Decimal("0")
            haber = datos.get("haber") or Decimal("0")
            if cuenta is None and es_cero(debe) and es_cero(haber):
                continue
            lineas.append(
                (
                    formulario,
                    tipos.LineaAsiento(
                        id=str(indice),
                        cuenta_id=str(cuenta.pk) if cuenta else "",
                        debe=debe,
                        haber=haber,
                    ),
                )
            )

        fecha = None
        glosa = ""
        if self.formulario_asiento is not None:
            datos_asiento = getattr(self.formulario_asiento, "cleaned_data", None) or {}
            fecha = datos_asiento.get("fecha")
            glosa = datos_asiento.get("glosa") or ""

        cuentas = [cuenta.a_dominio() for cuenta in self.caso.cuentas.all()]
        errores = validar_asiento(fecha, glosa, [linea for _, linea in lineas], cuentas)

        for formulario, linea in lineas:
            mensaje = errores.por_linea.get(linea.id)
            if mensaje:
                formulario.add_error(None, mensaje)

        mensajes = [texto for texto in (errores.lineas, errores.cuadre) if texto]
        if mensajes:
            raise forms.ValidationError(mensajes)


LineaFormSetFactory = inlineformset_factory(
    Asiento,
    LineaAsiento,
    form=LineaAsientoForm,
    formset=LineasFormSet,
    extra=4,
    can_delete=True,
)


class SeleccionDemoForm(forms.Form):
    """Carga uno de los casos de ejemplo."""

    plantilla = forms.ChoiceField(label="Caso de ejemplo", choices=OPCIONES_CASO_DEMO)


class ImportarCasoForm(forms.Form):
    """Importa un caso desde el JSON exportado por la aplicación."""

    archivo = forms.FileField(label="Archivo JSON del caso")


class FiltroDiarioForm(forms.Form):
    """Filtros del Libro Diario: fechas, cuenta y búsqueda de texto."""

    desde = forms.DateField(
        label="Desde", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    hasta = forms.DateField(
        label="Hasta", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    cuenta = forms.ModelChoiceField(
        label="Cuenta", required=False, queryset=Cuenta.objects.none(), empty_label="Todas"
    )
    texto = forms.CharField(label="Buscar", required=False, max_length=80)

    def __init__(self, *args, caso=None, **kwargs):
        super().__init__(*args, **kwargs)
        if caso is not None:
            self.fields["cuenta"].queryset = caso.cuentas.all()


class ReporteForm(forms.Form):
    """Elige qué reportes entran en el PDF."""

    nombre_empresa = forms.CharField(
        label="Nombre de la empresa en el PDF", required=False, max_length=120
    )
    correo = forms.EmailField(label="Correo electrónico de destino", required=False)
    secciones = forms.MultipleChoiceField(
        label="Reportes incluidos",
        choices=[(clave, etiqueta) for clave, etiqueta in SECCIONES],
        initial=[clave for clave, _ in SECCIONES],
        widget=forms.CheckboxSelectMultiple,
    )


class ImportarAsientosForm(forms.Form):
    """Importa asientos desde un Excel o CSV (lo lee pandas)."""

    archivo = forms.FileField(label="Archivo de asientos (.xlsx o .csv)")
    crear_cuentas = forms.BooleanField(
        label="Crear las cuentas que no esten en el plan",
        required=False,
        help_text="Se crean como activo corriente; luego se corrigen en el plan de cuentas.",
    )
