import type { Cuenta, Rubro, RubroBalance, RubroResultado, TipoCuenta } from './tipos';

export const TIPOS_CUENTA: TipoCuenta[] = ['ACTIVO', 'PASIVO', 'PATRIMONIO', 'INGRESO', 'GASTO'];

export const ETIQUETA_TIPO: Record<TipoCuenta, string> = {
  ACTIVO: 'Activo',
  PASIVO: 'Pasivo',
  PATRIMONIO: 'Patrimonio',
  INGRESO: 'Ingreso',
  GASTO: 'Gasto',
};

export const ETIQUETA_RUBRO: Record<Rubro, string> = {
  CORRIENTE: 'Corriente',
  NO_CORRIENTE: 'No corriente',
  VENTAS: 'Ventas',
  DEVOLUCIONES_VENTAS: 'Devoluciones sobre ventas',
  DESCUENTOS_VENTAS: 'Descuentos sobre ventas',
  COSTO_VENTAS: 'Costo de ventas',
  GASTO_VENTAS: 'Gasto de ventas',
  GASTO_ADMINISTRACION: 'Gasto de administración',
  INGRESO_FINANCIERO: 'Ingreso financiero',
  GASTO_FINANCIERO: 'Gasto financiero',
  OTRO_INGRESO: 'Otro ingreso',
  OTRO_GASTO: 'Otro gasto',
};

const RUBROS_BALANCE: RubroBalance[] = ['CORRIENTE', 'NO_CORRIENTE'];

const RUBROS_INGRESO: RubroResultado[] = [
  'VENTAS',
  'DEVOLUCIONES_VENTAS',
  'DESCUENTOS_VENTAS',
  'INGRESO_FINANCIERO',
  'OTRO_INGRESO',
];

const RUBROS_GASTO: RubroResultado[] = [
  'COSTO_VENTAS',
  'GASTO_VENTAS',
  'GASTO_ADMINISTRACION',
  'GASTO_FINANCIERO',
  'OTRO_GASTO',
];

/** Rubros válidos para cada tipo de cuenta. El patrimonio no usa rubro. */
export function rubrosPermitidos(tipo: TipoCuenta): Rubro[] {
  if (tipo === 'ACTIVO' || tipo === 'PASIVO') return RUBROS_BALANCE;
  if (tipo === 'INGRESO') return RUBROS_INGRESO;
  if (tipo === 'GASTO') return RUBROS_GASTO;
  return [];
}

/** Rubro que se asume cuando la cuenta no declara uno. */
export function rubroPorDefecto(tipo: TipoCuenta): Rubro | undefined {
  switch (tipo) {
    case 'ACTIVO':
    case 'PASIVO':
      return 'CORRIENTE';
    case 'INGRESO':
      return 'VENTAS';
    case 'GASTO':
      return 'GASTO_ADMINISTRACION';
    default:
      return undefined;
  }
}

export function rubroEfectivo(cuenta: Cuenta): Rubro | undefined {
  const permitidos = rubrosPermitidos(cuenta.tipo);
  if (cuenta.rubro && permitidos.includes(cuenta.rubro)) return cuenta.rubro;
  return rubroPorDefecto(cuenta.tipo);
}

/** Naturaleza del saldo: las cuentas de activo y gasto son deudoras. */
export function esNaturalezaDeudora(tipo: TipoCuenta): boolean {
  return tipo === 'ACTIVO' || tipo === 'GASTO';
}

/**
 * Modo simple de registro (signo + / -), tal como aparece en las diapositivas.
 * Un "+" aumenta la cuenta: va al Debe si su naturaleza es deudora, al Haber si no.
 */
export function movimientoDesdeSigno(
  tipo: TipoCuenta,
  signo: '+' | '-',
  monto: number,
): { debe: number; haber: number } {
  const aumenta = signo === '+';
  const alDebe = esNaturalezaDeudora(tipo) ? aumenta : !aumenta;
  return alDebe ? { debe: monto, haber: 0 } : { debe: 0, haber: monto };
}

export function etiquetaCuenta(cuenta: Cuenta | undefined): string {
  if (!cuenta) return 'Cuenta desconocida';
  return `${cuenta.codigo} — ${cuenta.nombre}`;
}

/** Orden estable por código: numérico cuando se puede, alfabético si no. */
export function compararCuentas(a: Cuenta, b: Cuenta): number {
  const numeroA = Number(a.codigo);
  const numeroB = Number(b.codigo);
  if (Number.isFinite(numeroA) && Number.isFinite(numeroB) && numeroA !== numeroB) {
    return numeroA - numeroB;
  }
  const porCodigo = a.codigo.localeCompare(b.codigo, 'es', { numeric: true });
  if (porCodigo !== 0) return porCodigo;
  return a.nombre.localeCompare(b.nombre, 'es');
}

export function ordenarCuentas(cuentas: Cuenta[]): Cuenta[] {
  return [...cuentas].sort(compararCuentas);
}

export function indicePorId(cuentas: Cuenta[]): Map<string, Cuenta> {
  return new Map(cuentas.map((cuenta) => [cuenta.id, cuenta]));
}

export interface ErroresCuenta {
  codigo?: string;
  nombre?: string;
  tipo?: string;
}

/** Valida una cuenta antes de guardarla. Devuelve un objeto vacío si todo está bien. */
export function validarCuenta(
  borrador: { codigo: string; nombre: string; tipo: TipoCuenta },
  cuentasExistentes: Cuenta[],
  idEnEdicion?: string,
): ErroresCuenta {
  const errores: ErroresCuenta = {};
  const codigo = borrador.codigo.trim();
  const nombre = borrador.nombre.trim();

  if (codigo === '') errores.codigo = 'Escribe el código de la cuenta.';
  else if (codigo.length > 12) errores.codigo = 'El código admite hasta 12 caracteres.';
  else if (!/^[A-Za-z0-9.-]+$/.test(codigo)) {
    errores.codigo = 'Usa solo letras, números, punto o guion.';
  } else if (
    cuentasExistentes.some(
      (cuenta) => cuenta.id !== idEnEdicion && cuenta.codigo.toUpperCase() === codigo.toUpperCase(),
    )
  ) {
    errores.codigo = 'Ya existe una cuenta con ese código.';
  }

  if (nombre === '') errores.nombre = 'Escribe el nombre de la cuenta.';
  else if (nombre.length > 80) errores.nombre = 'El nombre admite hasta 80 caracteres.';

  if (!TIPOS_CUENTA.includes(borrador.tipo)) errores.tipo = 'Elige un tipo de cuenta.';

  return errores;
}
