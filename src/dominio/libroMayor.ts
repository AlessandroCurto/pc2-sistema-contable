import type { Caso, Cuenta, TipoCuenta } from './tipos';
import { ETIQUETA_TIPO, TIPOS_CUENTA, esNaturalezaDeudora, indicePorId, ordenarCuentas } from './cuentas';
import { ordenarAsientos } from './asientos';
import { redondear, sumar } from './numeros';

export interface MovimientoMayor {
  fecha: string;
  numero: number;
  glosa: string;
  debe: number;
  haber: number;
  /** Saldo acumulado con signo positivo en la naturaleza de la cuenta. */
  saldo: number;
}

export interface CuentaMayor {
  cuenta: Cuenta;
  movimientos: MovimientoMayor[];
  totalDebe: number;
  totalHaber: number;
  saldo: number;
  naturalezaSaldo: 'DEUDOR' | 'ACREEDOR';
}

export interface GrupoMayor {
  tipo: TipoCuenta;
  etiqueta: string;
  cuentas: CuentaMayor[];
  totalDebe: number;
  totalHaber: number;
}

export interface LibroMayor {
  grupos: GrupoMayor[];
  totalDebe: number;
  totalHaber: number;
}

/**
 * Libro Mayor: agrupa los movimientos de los asientos por cuenta y por tipo,
 * acumulando el saldo en el orden cronológico de los asientos.
 */
export function construirLibroMayor(caso: Caso): LibroMayor {
  const cuentasPorId = indicePorId(caso.cuentas);
  const acumulado = new Map<string, MovimientoMayor[]>();

  for (const asiento of ordenarAsientos(caso.asientos)) {
    for (const linea of asiento.lineas) {
      const cuenta = cuentasPorId.get(linea.cuentaId);
      if (!cuenta) continue;
      const lista = acumulado.get(cuenta.id) ?? [];
      const deudora = esNaturalezaDeudora(cuenta.tipo);
      const anterior = lista.length > 0 ? lista[lista.length - 1].saldo : 0;
      const efecto = deudora ? linea.debe - linea.haber : linea.haber - linea.debe;
      lista.push({
        fecha: asiento.fecha,
        numero: asiento.numero,
        glosa: asiento.glosa,
        debe: linea.debe,
        haber: linea.haber,
        saldo: redondear(anterior + efecto),
      });
      acumulado.set(cuenta.id, lista);
    }
  }

  const grupos: GrupoMayor[] = TIPOS_CUENTA.map((tipo) => {
    const cuentas = ordenarCuentas(caso.cuentas.filter((cuenta) => cuenta.tipo === tipo))
      .filter((cuenta) => (acumulado.get(cuenta.id)?.length ?? 0) > 0)
      .map<CuentaMayor>((cuenta) => {
        const movimientos = acumulado.get(cuenta.id) ?? [];
        const totalDebe = sumar(movimientos.map((movimiento) => movimiento.debe));
        const totalHaber = sumar(movimientos.map((movimiento) => movimiento.haber));
        const diferencia = redondear(totalDebe - totalHaber);
        return {
          cuenta,
          movimientos,
          totalDebe,
          totalHaber,
          saldo: Math.abs(diferencia),
          naturalezaSaldo: diferencia >= 0 ? 'DEUDOR' : 'ACREEDOR',
        };
      });

    return {
      tipo,
      etiqueta: ETIQUETA_TIPO[tipo],
      cuentas,
      totalDebe: sumar(cuentas.map((item) => item.totalDebe)),
      totalHaber: sumar(cuentas.map((item) => item.totalHaber)),
    };
  }).filter((grupo) => grupo.cuentas.length > 0);

  return {
    grupos,
    totalDebe: sumar(grupos.map((grupo) => grupo.totalDebe)),
    totalHaber: sumar(grupos.map((grupo) => grupo.totalHaber)),
  };
}
