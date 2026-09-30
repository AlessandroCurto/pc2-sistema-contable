import type { Caso, Cuenta, RubroResultado } from './tipos';
import { ETIQUETA_RUBRO, indicePorId, ordenarCuentas, rubroEfectivo } from './cuentas';
import { redondear, sumar } from './numeros';

export interface DetalleCuentaResultado {
  cuenta: Cuenta;
  monto: number;
}

export interface SeccionResultado {
  rubro: RubroResultado;
  etiqueta: string;
  cuentas: DetalleCuentaResultado[];
  total: number;
}

export type ClaseFila = 'detalle' | 'subtotal' | 'total';

export interface FilaResultado {
  clave: string;
  etiqueta: string;
  monto: number;
  clase: ClaseFila;
  /** '-' cuando la línea resta en el reporte. Solo afecta la presentación. */
  signo?: '+' | '-';
}

export interface EstadoResultados {
  secciones: Record<RubroResultado, SeccionResultado>;
  filas: FilaResultado[];
  ventas: number;
  devoluciones: number;
  descuentos: number;
  ventasNetas: number;
  costoVentas: number;
  utilidadBruta: number;
  gastoVentas: number;
  gastoAdministracion: number;
  utilidadOperativa: number;
  ingresosFinancieros: number;
  gastosFinancieros: number;
  otrosIngresos: number;
  otrosGastos: number;
  resultadoAntesImpuesto: number;
  tasaImpuesto: number;
  impuesto: number;
  utilidadNeta: number;
  totalIngresos: number;
  totalGastos: number;
}

const RUBROS: RubroResultado[] = [
  'VENTAS',
  'DEVOLUCIONES_VENTAS',
  'DESCUENTOS_VENTAS',
  'COSTO_VENTAS',
  'GASTO_VENTAS',
  'GASTO_ADMINISTRACION',
  'INGRESO_FINANCIERO',
  'GASTO_FINANCIERO',
  'OTRO_INGRESO',
  'OTRO_GASTO',
];

/**
 * Saldo de una cuenta de resultados en positivo:
 * los ingresos acumulan en el Haber y los gastos en el Debe.
 */
function saldosDeResultado(caso: Caso): Map<string, number> {
  const cuentasPorId = indicePorId(caso.cuentas);
  const saldos = new Map<string, number>();
  for (const asiento of caso.asientos) {
    for (const linea of asiento.lineas) {
      const cuenta = cuentasPorId.get(linea.cuentaId);
      if (!cuenta) continue;
      if (cuenta.tipo !== 'INGRESO' && cuenta.tipo !== 'GASTO') continue;
      const efecto =
        cuenta.tipo === 'INGRESO' ? linea.haber - linea.debe : linea.debe - linea.haber;
      saldos.set(cuenta.id, redondear((saldos.get(cuenta.id) ?? 0) + efecto));
    }
  }
  return saldos;
}

export function construirEstadoResultados(caso: Caso): EstadoResultados {
  const saldos = saldosDeResultado(caso);
  const cuentasOrdenadas = ordenarCuentas(caso.cuentas);

  const secciones = RUBROS.reduce((acumulador, rubro) => {
    const cuentas = cuentasOrdenadas
      .filter((cuenta) => saldos.has(cuenta.id) && rubroEfectivo(cuenta) === rubro)
      .map<DetalleCuentaResultado>((cuenta) => ({
        cuenta,
        monto: saldos.get(cuenta.id) ?? 0,
      }));
    acumulador[rubro] = {
      rubro,
      etiqueta: ETIQUETA_RUBRO[rubro],
      cuentas,
      total: sumar(cuentas.map((item) => item.monto)),
    };
    return acumulador;
  }, {} as Record<RubroResultado, SeccionResultado>);

  const ventas = secciones.VENTAS.total;
  const devoluciones = secciones.DEVOLUCIONES_VENTAS.total;
  const descuentos = secciones.DESCUENTOS_VENTAS.total;
  const ventasNetas = redondear(ventas - devoluciones - descuentos);
  const costoVentas = secciones.COSTO_VENTAS.total;
  const utilidadBruta = redondear(ventasNetas - costoVentas);
  const gastoVentas = secciones.GASTO_VENTAS.total;
  const gastoAdministracion = secciones.GASTO_ADMINISTRACION.total;
  const utilidadOperativa = redondear(utilidadBruta - gastoVentas - gastoAdministracion);
  const ingresosFinancieros = secciones.INGRESO_FINANCIERO.total;
  const gastosFinancieros = secciones.GASTO_FINANCIERO.total;
  const otrosIngresos = secciones.OTRO_INGRESO.total;
  const otrosGastos = secciones.OTRO_GASTO.total;
  const resultadoAntesImpuesto = redondear(
    utilidadOperativa + ingresosFinancieros - gastosFinancieros + otrosIngresos - otrosGastos,
  );

  const tasaImpuesto = Math.max(0, caso.empresa.tasaImpuestoRenta ?? 0);
  const impuesto = resultadoAntesImpuesto > 0
    ? redondear((resultadoAntesImpuesto * tasaImpuesto) / 100)
    : 0;
  const utilidadNeta = redondear(resultadoAntesImpuesto - impuesto);

  const filas: FilaResultado[] = [
    { clave: 'ventas', etiqueta: 'Ventas', monto: ventas, clase: 'detalle' },
    {
      clave: 'devoluciones',
      etiqueta: 'Devoluciones sobre ventas',
      monto: devoluciones,
      clase: 'detalle',
      signo: '-',
    },
    {
      clave: 'descuentos',
      etiqueta: 'Descuentos sobre ventas',
      monto: descuentos,
      clase: 'detalle',
      signo: '-',
    },
    { clave: 'ventasNetas', etiqueta: 'Ventas netas', monto: ventasNetas, clase: 'subtotal' },
    {
      clave: 'costoVentas',
      etiqueta: 'Costo de ventas',
      monto: costoVentas,
      clase: 'detalle',
      signo: '-',
    },
    { clave: 'utilidadBruta', etiqueta: 'Utilidad bruta', monto: utilidadBruta, clase: 'subtotal' },
    {
      clave: 'gastoVentas',
      etiqueta: 'Gastos de ventas',
      monto: gastoVentas,
      clase: 'detalle',
      signo: '-',
    },
    {
      clave: 'gastoAdministracion',
      etiqueta: 'Gastos de administración',
      monto: gastoAdministracion,
      clase: 'detalle',
      signo: '-',
    },
    {
      clave: 'utilidadOperativa',
      etiqueta: 'Utilidad operativa',
      monto: utilidadOperativa,
      clase: 'subtotal',
    },
    {
      clave: 'ingresosFinancieros',
      etiqueta: 'Ingresos financieros',
      monto: ingresosFinancieros,
      clase: 'detalle',
    },
    {
      clave: 'gastosFinancieros',
      etiqueta: 'Gastos financieros',
      monto: gastosFinancieros,
      clase: 'detalle',
      signo: '-',
    },
    { clave: 'otrosIngresos', etiqueta: 'Otros ingresos', monto: otrosIngresos, clase: 'detalle' },
    {
      clave: 'otrosGastos',
      etiqueta: 'Otros gastos',
      monto: otrosGastos,
      clase: 'detalle',
      signo: '-',
    },
    {
      clave: 'resultadoAntesImpuesto',
      etiqueta: 'Resultado antes del impuesto a la renta',
      monto: resultadoAntesImpuesto,
      clase: 'subtotal',
    },
    {
      clave: 'impuesto',
      etiqueta: `Impuesto a la renta (${redondear(tasaImpuesto)}%)`,
      monto: impuesto,
      clase: 'detalle',
      signo: '-',
    },
    { clave: 'utilidadNeta', etiqueta: 'Utilidad neta', monto: utilidadNeta, clase: 'total' },
  ];

  const totalIngresos = sumar([
    ventas,
    ingresosFinancieros,
    otrosIngresos,
    -devoluciones,
    -descuentos,
  ]);
  const totalGastos = sumar([
    costoVentas,
    gastoVentas,
    gastoAdministracion,
    gastosFinancieros,
    otrosGastos,
  ]);

  return {
    secciones,
    filas,
    ventas,
    devoluciones,
    descuentos,
    ventasNetas,
    costoVentas,
    utilidadBruta,
    gastoVentas,
    gastoAdministracion,
    utilidadOperativa,
    ingresosFinancieros,
    gastosFinancieros,
    otrosIngresos,
    otrosGastos,
    resultadoAntesImpuesto,
    tasaImpuesto,
    impuesto,
    utilidadNeta,
    totalIngresos,
    totalGastos,
  };
}
