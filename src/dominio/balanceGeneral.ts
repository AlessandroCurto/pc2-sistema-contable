import type { Caso, Cuenta } from './tipos';
import { indicePorId, ordenarCuentas, rubroEfectivo } from './cuentas';
import { redondear, sonIguales, sumar } from './numeros';
import { construirEstadoResultados } from './estadoResultados';

export interface DetalleCuentaBalance {
  cuenta: Cuenta;
  monto: number;
}

export interface BloqueBalance {
  clave: string;
  etiqueta: string;
  cuentas: DetalleCuentaBalance[];
  total: number;
}

export interface BalanceGeneral {
  activoCorriente: BloqueBalance;
  activoNoCorriente: BloqueBalance;
  pasivoCorriente: BloqueBalance;
  pasivoNoCorriente: BloqueBalance;
  patrimonio: BloqueBalance;
  totalActivo: number;
  totalPasivo: number;
  totalPatrimonioAportado: number;
  resultadoEjercicio: number;
  totalPatrimonio: number;
  totalPasivoPatrimonio: number;
  diferencia: number;
  cuadrado: boolean;
  /** true cuando el resultado del ejercicio ya está neto de impuesto a la renta. */
  resultadoNetoDeImpuesto: boolean;
}

function bloque(clave: string, etiqueta: string, cuentas: DetalleCuentaBalance[]): BloqueBalance {
  return { clave, etiqueta, cuentas, total: sumar(cuentas.map((item) => item.monto)) };
}

/**
 * Balance General (Estado de Situación Financiera).
 * El resultado del ejercicio sale del Estado de Resultados y se suma al patrimonio,
 * porque las cuentas de ingreso y gasto se cierran contra el patrimonio.
 */
export function construirBalanceGeneral(caso: Caso): BalanceGeneral {
  const cuentasPorId = indicePorId(caso.cuentas);
  const saldos = new Map<string, number>();

  for (const asiento of caso.asientos) {
    for (const linea of asiento.lineas) {
      const cuenta = cuentasPorId.get(linea.cuentaId);
      if (!cuenta) continue;
      if (cuenta.tipo === 'INGRESO' || cuenta.tipo === 'GASTO') continue;
      const efecto =
        cuenta.tipo === 'ACTIVO' ? linea.debe - linea.haber : linea.haber - linea.debe;
      saldos.set(cuenta.id, redondear((saldos.get(cuenta.id) ?? 0) + efecto));
    }
  }

  const ordenadas = ordenarCuentas(caso.cuentas).filter((cuenta) => saldos.has(cuenta.id));

  const tomar = (tipo: Cuenta['tipo'], rubro?: string): DetalleCuentaBalance[] =>
    ordenadas
      .filter((cuenta) => cuenta.tipo === tipo && (rubro === undefined || rubroEfectivo(cuenta) === rubro))
      .map((cuenta) => ({ cuenta, monto: saldos.get(cuenta.id) ?? 0 }));

  const activoCorriente = bloque('activoCorriente', 'Activo corriente', tomar('ACTIVO', 'CORRIENTE'));
  const activoNoCorriente = bloque(
    'activoNoCorriente',
    'Activo no corriente',
    tomar('ACTIVO', 'NO_CORRIENTE'),
  );
  const pasivoCorriente = bloque('pasivoCorriente', 'Pasivo corriente', tomar('PASIVO', 'CORRIENTE'));
  const pasivoNoCorriente = bloque(
    'pasivoNoCorriente',
    'Pasivo no corriente',
    tomar('PASIVO', 'NO_CORRIENTE'),
  );
  const patrimonio = bloque('patrimonio', 'Patrimonio', tomar('PATRIMONIO'));

  const estado = construirEstadoResultados(caso);
  const resultadoNetoDeImpuesto = caso.empresa.impuestoAfectaPatrimonio === true;
  const resultadoEjercicio = resultadoNetoDeImpuesto
    ? estado.utilidadNeta
    : estado.resultadoAntesImpuesto;

  const totalActivo = redondear(activoCorriente.total + activoNoCorriente.total);
  const totalPasivo = redondear(pasivoCorriente.total + pasivoNoCorriente.total);
  const totalPatrimonio = redondear(patrimonio.total + resultadoEjercicio);
  const totalPasivoPatrimonio = redondear(totalPasivo + totalPatrimonio);

  return {
    activoCorriente,
    activoNoCorriente,
    pasivoCorriente,
    pasivoNoCorriente,
    patrimonio,
    totalActivo,
    totalPasivo,
    totalPatrimonioAportado: patrimonio.total,
    resultadoEjercicio,
    totalPatrimonio,
    totalPasivoPatrimonio,
    diferencia: redondear(totalActivo - totalPasivoPatrimonio),
    cuadrado: sonIguales(totalActivo, totalPasivoPatrimonio),
    resultadoNetoDeImpuesto,
  };
}
