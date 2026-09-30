/** Utilidades numéricas. Todo el dinero se redondea a 2 decimales. */

export const TOLERANCIA = 0.005;

export function redondear(valor: number, decimales = 2): number {
  if (!Number.isFinite(valor)) return 0;
  const factor = 10 ** decimales;
  return Math.round((valor + Number.EPSILON) * factor) / factor;
}

export function sonIguales(a: number, b: number, tolerancia = TOLERANCIA): boolean {
  return Math.abs(a - b) < tolerancia;
}

export function esCero(valor: number, tolerancia = TOLERANCIA): boolean {
  return Math.abs(valor) < tolerancia;
}

export function sumar(valores: number[]): number {
  return redondear(valores.reduce((total, valor) => total + valor, 0));
}

/** Convierte texto de formulario a número. Acepta coma decimal y separadores de miles. */
export function aNumero(texto: string | number | null | undefined): number {
  if (typeof texto === 'number') return Number.isFinite(texto) ? texto : 0;
  if (texto === null || texto === undefined) return 0;
  const limpio = String(texto).trim().replace(/\s/g, '').replace(/,/g, '');
  if (limpio === '') return 0;
  const valor = Number(limpio);
  return Number.isFinite(valor) ? valor : 0;
}
