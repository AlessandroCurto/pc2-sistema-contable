import type { Caso, Cuenta } from './tipos';
import { indicePorId, ordenarCuentas } from './cuentas';
import { redondear, sonIguales, sumar } from './numeros';

export interface FilaBalance {
  cuenta: Cuenta;
  sumaDebe: number;
  sumaHaber: number;
  saldoDeudor: number;
  saldoAcreedor: number;
}

export interface BalanceComprobacion {
  filas: FilaBalance[];
  totalDebe: number;
  totalHaber: number;
  totalDeudor: number;
  totalAcreedor: number;
  cuadrado: boolean;
  diferenciaSumas: number;
  diferenciaSaldos: number;
}

/**
 * Balance de Comprobación: sumas y saldos por cuenta.
 * Está cuadrado cuando el total del Debe iguala al del Haber
 * y el total deudor iguala al acreedor.
 */
export function construirBalanceComprobacion(caso: Caso): BalanceComprobacion {
  const cuentasPorId = indicePorId(caso.cuentas);
  const sumas = new Map<string, { debe: number; haber: number }>();

  for (const asiento of caso.asientos) {
    for (const linea of asiento.lineas) {
      if (!cuentasPorId.has(linea.cuentaId)) continue;
      const actual = sumas.get(linea.cuentaId) ?? { debe: 0, haber: 0 };
      actual.debe = redondear(actual.debe + linea.debe);
      actual.haber = redondear(actual.haber + linea.haber);
      sumas.set(linea.cuentaId, actual);
    }
  }

  const filas: FilaBalance[] = ordenarCuentas(caso.cuentas)
    .filter((cuenta) => sumas.has(cuenta.id))
    .map((cuenta) => {
      const suma = sumas.get(cuenta.id) ?? { debe: 0, haber: 0 };
      const diferencia = redondear(suma.debe - suma.haber);
      return {
        cuenta,
        sumaDebe: suma.debe,
        sumaHaber: suma.haber,
        saldoDeudor: diferencia > 0 ? diferencia : 0,
        saldoAcreedor: diferencia < 0 ? Math.abs(diferencia) : 0,
      };
    });

  const totalDebe = sumar(filas.map((fila) => fila.sumaDebe));
  const totalHaber = sumar(filas.map((fila) => fila.sumaHaber));
  const totalDeudor = sumar(filas.map((fila) => fila.saldoDeudor));
  const totalAcreedor = sumar(filas.map((fila) => fila.saldoAcreedor));

  return {
    filas,
    totalDebe,
    totalHaber,
    totalDeudor,
    totalAcreedor,
    cuadrado: sonIguales(totalDebe, totalHaber) && sonIguales(totalDeudor, totalAcreedor),
    diferenciaSumas: redondear(totalDebe - totalHaber),
    diferenciaSaldos: redondear(totalDeudor - totalAcreedor),
  };
}
