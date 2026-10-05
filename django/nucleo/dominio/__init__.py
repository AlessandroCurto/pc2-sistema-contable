"""Motor contable puro: sin Django, sin base de datos, sin interfaz.

Trabaja sobre las dataclasses de `tipos.py`, así que se puede probar solo.
Los modelos de la aplicación se convierten a esas dataclasses con `a_dominio()`.
"""

from .asientos import (  # noqa: F401
    ErroresAsiento,
    ResumenAsiento,
    normalizar_lineas,
    ordenar_asientos,
    resumir_asiento,
    siguiente_numero,
    total_asiento,
    validar_asiento,
)
from .balance_comprobacion import construir_balance_comprobacion  # noqa: F401
from .balance_general import construir_balance_general  # noqa: F401
from .cuentas import (  # noqa: F401
    ETIQUETA_RUBRO,
    ETIQUETA_TIPO,
    TIPOS_CUENTA,
    es_naturaleza_deudora,
    etiqueta_cuenta,
    indice_por_id,
    movimiento_desde_signo,
    ordenar_cuentas,
    rubro_efectivo,
    rubro_por_defecto,
    rubros_permitidos,
    validar_cuenta,
)
from .estado_resultados import construir_estado_resultados  # noqa: F401
from .formato import formatear_fecha, formatear_moneda, formatear_numero  # noqa: F401
from .libro_diario import FiltroDiario, construir_libro_diario  # noqa: F401
from .libro_mayor import construir_libro_mayor  # noqa: F401
from .numeros import TOLERANCIA, a_numero, es_cero, redondear, son_iguales, sumar  # noqa: F401
from .tipos import (  # noqa: F401
    Asiento,
    Caso,
    Cuenta,
    Empresa,
    LineaAsiento,
    Naturaleza,
    Rubro,
    TipoCuenta,
)
