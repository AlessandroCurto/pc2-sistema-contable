import type { Asiento, Cuenta, LineaAsiento } from './tipos';
import { redondear, sonIguales, sumar, esCero } from './numeros';

export interface ErroresAsiento {
  fecha?: string;
  glosa?: string;
  lineas?: string;
  cuadre?: string;
  porLinea: Record<string, string>;
}

export interface ResumenAsiento {
  totalDebe: number;
  totalHaber: number;
  diferencia: number;
  cuadrado: boolean;
}

export function resumirAsiento(lineas: LineaAsiento[]): ResumenAsiento {
  const totalDebe = sumar(lineas.map((linea) => redondear(linea.debe)));
  const totalHaber = sumar(lineas.map((linea) => redondear(linea.haber)));
  return {
    totalDebe,
    totalHaber,
    diferencia: redondear(totalDebe - totalHaber),
    cuadrado: sonIguales(totalDebe, totalHaber) && !esCero(totalDebe),
  };
}

export function hayErrores(errores: ErroresAsiento): boolean {
  return Boolean(
    errores.fecha ||
      errores.glosa ||
      errores.lineas ||
      errores.cuadre ||
      Object.keys(errores.porLinea).length > 0,
  );
}

/**
 * Regla central del sistema: un asiento solo se guarda si el Debe iguala al Haber.
 * Además cada línea necesita una cuenta existente y un único importe positivo.
 */
export function validarAsiento(
  borrador: { fecha: string; glosa: string; lineas: LineaAsiento[] },
  cuentas: Cuenta[],
): ErroresAsiento {
  const errores: ErroresAsiento = { porLinea: {} };
  const idsCuentas = new Set(cuentas.map((cuenta) => cuenta.id));

  if (!/^\d{4}-\d{2}-\d{2}$/.test(borrador.fecha)) {
    errores.fecha = 'Elige una fecha válida.';
  }
  if (borrador.glosa.trim().length > 140) {
    errores.glosa = 'La glosa admite hasta 140 caracteres.';
  }

  const lineasConDatos = borrador.lineas.filter(
    (linea) => linea.cuentaId !== '' || !esCero(linea.debe) || !esCero(linea.haber),
  );

  if (lineasConDatos.length < 2) {
    errores.lineas = 'Un asiento necesita al menos dos líneas con cuenta e importe.';
  }

  for (const linea of lineasConDatos) {
    if (linea.cuentaId === '' || !idsCuentas.has(linea.cuentaId)) {
      errores.porLinea[linea.id] = 'Elige una cuenta del plan de cuentas.';
      continue;
    }
    const debe = redondear(linea.debe);
    const haber = redondear(linea.haber);
    if (debe < 0 || haber < 0) {
      errores.porLinea[linea.id] = 'Los importes no pueden ser negativos.';
      continue;
    }
    if (!esCero(debe) && !esCero(haber)) {
      errores.porLinea[linea.id] = 'Escribe el importe en el Debe o en el Haber, no en ambos.';
      continue;
    }
    if (esCero(debe) && esCero(haber)) {
      errores.porLinea[linea.id] = 'Escribe un importe mayor que cero.';
    }
  }

  const resumen = resumirAsiento(lineasConDatos);
  if (!errores.lineas && Object.keys(errores.porLinea).length === 0) {
    if (esCero(resumen.totalDebe) && esCero(resumen.totalHaber)) {
      errores.cuadre = 'El asiento no tiene importes.';
    } else if (!resumen.cuadrado) {
      errores.cuadre = `El asiento no cuadra. Diferencia de ${redondear(
        Math.abs(resumen.diferencia),
      ).toFixed(2)}.`;
    }
  }

  return errores;
}

/** Quita líneas vacías y redondea importes antes de guardar. */
export function normalizarLineas(lineas: LineaAsiento[]): LineaAsiento[] {
  return lineas
    .filter((linea) => linea.cuentaId !== '' && (!esCero(linea.debe) || !esCero(linea.haber)))
    .map((linea) => ({
      id: linea.id,
      cuentaId: linea.cuentaId,
      debe: redondear(linea.debe),
      haber: redondear(linea.haber),
    }));
}

/** Orden cronológico; a igual fecha manda el correlativo. */
export function compararAsientos(a: Asiento, b: Asiento): number {
  if (a.fecha !== b.fecha) return a.fecha < b.fecha ? -1 : 1;
  return a.numero - b.numero;
}

export function ordenarAsientos(asientos: Asiento[]): Asiento[] {
  return [...asientos].sort(compararAsientos);
}

/** Reasigna los correlativos 1..n respetando el orden cronológico. */
export function renumerar(asientos: Asiento[]): Asiento[] {
  return ordenarAsientos(asientos).map((asiento, indice) => ({ ...asiento, numero: indice + 1 }));
}

export function siguienteNumero(asientos: Asiento[]): number {
  return asientos.reduce((mayor, asiento) => Math.max(mayor, asiento.numero), 0) + 1;
}

export function totalAsiento(asiento: Asiento): number {
  return resumirAsiento(asiento.lineas).totalDebe;
}
