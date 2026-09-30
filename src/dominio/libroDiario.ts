import type { Asiento, Caso, Cuenta, TipoCuenta } from './tipos';
import { indicePorId } from './cuentas';
import { ordenarAsientos, resumirAsiento } from './asientos';
import { sumar } from './numeros';

export interface FiltroDiario {
  desde?: string;
  hasta?: string;
  cuentaId?: string;
  texto?: string;
}

export interface FilaDiario {
  asientoId: string;
  numero: number;
  fecha: string;
  glosa: string;
  cuenta: Cuenta | undefined;
  tipo: TipoCuenta | undefined;
  debe: number;
  haber: number;
}

export interface AsientoDiario {
  asiento: Asiento;
  filas: FilaDiario[];
  totalDebe: number;
  totalHaber: number;
  cuadrado: boolean;
}

export interface LibroDiario {
  asientos: AsientoDiario[];
  filas: FilaDiario[];
  totalDebe: number;
  totalHaber: number;
}

function cumpleFiltro(asiento: Asiento, filtro: FiltroDiario, cuentas: Map<string, Cuenta>): boolean {
  if (filtro.desde && asiento.fecha < filtro.desde) return false;
  if (filtro.hasta && asiento.fecha > filtro.hasta) return false;
  if (filtro.cuentaId && !asiento.lineas.some((linea) => linea.cuentaId === filtro.cuentaId)) {
    return false;
  }
  const texto = filtro.texto?.trim().toLowerCase();
  if (texto) {
    const enGlosa = asiento.glosa.toLowerCase().includes(texto);
    const enNumero = String(asiento.numero) === texto;
    const enCuentas = asiento.lineas.some((linea) => {
      const cuenta = cuentas.get(linea.cuentaId);
      if (!cuenta) return false;
      return (
        cuenta.nombre.toLowerCase().includes(texto) || cuenta.codigo.toLowerCase().includes(texto)
      );
    });
    if (!enGlosa && !enNumero && !enCuentas) return false;
  }
  return true;
}

/** Libro Diario: los asientos en orden cronológico, con sus líneas. */
export function construirLibroDiario(caso: Caso, filtro: FiltroDiario = {}): LibroDiario {
  const cuentas = indicePorId(caso.cuentas);
  const asientos = ordenarAsientos(caso.asientos).filter((asiento) =>
    cumpleFiltro(asiento, filtro, cuentas),
  );

  const detalle: AsientoDiario[] = asientos.map((asiento) => {
    const filas: FilaDiario[] = asiento.lineas.map((linea) => {
      const cuenta = cuentas.get(linea.cuentaId);
      return {
        asientoId: asiento.id,
        numero: asiento.numero,
        fecha: asiento.fecha,
        glosa: asiento.glosa,
        cuenta,
        tipo: cuenta?.tipo,
        debe: linea.debe,
        haber: linea.haber,
      };
    });
    const resumen = resumirAsiento(asiento.lineas);
    return {
      asiento,
      filas,
      totalDebe: resumen.totalDebe,
      totalHaber: resumen.totalHaber,
      cuadrado: resumen.cuadrado,
    };
  });

  const filas = detalle.flatMap((item) => item.filas);
  return {
    asientos: detalle,
    filas,
    totalDebe: sumar(filas.map((fila) => fila.debe)),
    totalHaber: sumar(filas.map((fila) => fila.haber)),
  };
}
