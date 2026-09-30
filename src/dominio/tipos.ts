/** Tipos del dominio contable. Todo el sistema trabaja sobre estas estructuras. */

export type TipoCuenta = 'ACTIVO' | 'PASIVO' | 'PATRIMONIO' | 'INGRESO' | 'GASTO';

/** Clasificación usada por el Balance General. */
export type RubroBalance = 'CORRIENTE' | 'NO_CORRIENTE';

/** Clasificación usada por el Estado de Resultados. */
export type RubroResultado =
  | 'VENTAS'
  | 'DEVOLUCIONES_VENTAS'
  | 'DESCUENTOS_VENTAS'
  | 'COSTO_VENTAS'
  | 'GASTO_VENTAS'
  | 'GASTO_ADMINISTRACION'
  | 'INGRESO_FINANCIERO'
  | 'GASTO_FINANCIERO'
  | 'OTRO_INGRESO'
  | 'OTRO_GASTO';

export type Rubro = RubroBalance | RubroResultado;

export interface Cuenta {
  id: string;
  codigo: string;
  nombre: string;
  tipo: TipoCuenta;
  /** Opcional: afina dónde aparece la cuenta en los reportes. */
  rubro?: Rubro;
}

export interface LineaAsiento {
  id: string;
  cuentaId: string;
  debe: number;
  haber: number;
}

export interface Asiento {
  id: string;
  /** Correlativo visible (Asiento #1, #2...). Se recalcula al ordenar. */
  numero: number;
  /** Fecha en formato ISO corto: AAAA-MM-DD. */
  fecha: string;
  glosa: string;
  lineas: LineaAsiento[];
}

export interface Empresa {
  nombre: string;
  ruc: string;
  simboloMoneda: string;
  periodoInicio: string;
  periodoFin: string;
  /** Porcentaje de impuesto a la renta aplicado en el Estado de Resultados. */
  tasaImpuestoRenta: number;
  /**
   * Si es true, el Balance General resta el impuesto a la renta del resultado
   * del ejercicio. Por defecto false: el impuesto no se registra como asiento,
   * así que el patrimonio muestra la utilidad antes de impuestos.
   */
  impuestoAfectaPatrimonio: boolean;
}

export interface Caso {
  id: string;
  nombre: string;
  creadoEn: string;
  actualizadoEn: string;
  empresa: Empresa;
  cuentas: Cuenta[];
  asientos: Asiento[];
}

export interface EstadoPersistido {
  version: number;
  casoActivoId: string | null;
  casos: Caso[];
}
