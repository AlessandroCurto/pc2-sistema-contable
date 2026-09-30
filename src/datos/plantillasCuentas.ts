import type { Cuenta, Rubro, TipoCuenta } from '../dominio/tipos';

export interface DefinicionCuenta {
  codigo: string;
  nombre: string;
  tipo: TipoCuenta;
  rubro?: Rubro;
}

export interface PlantillaCuentas {
  id: string;
  nombre: string;
  descripcion: string;
  cuentas: DefinicionCuenta[];
}

/** Convierte definiciones en cuentas con id estable a partir del código. */
export function crearCuentas(definiciones: DefinicionCuenta[], prefijo = 'cta'): Cuenta[] {
  return definiciones.map((definicion) => ({
    id: `${prefijo}-${definicion.codigo}`,
    codigo: definicion.codigo,
    nombre: definicion.nombre,
    tipo: definicion.tipo,
    rubro: definicion.rubro,
  }));
}

const PCGE: DefinicionCuenta[] = [
  { codigo: '10', nombre: 'Efectivo y equivalentes de efectivo', tipo: 'ACTIVO', rubro: 'CORRIENTE' },
  { codigo: '12', nombre: 'Cuentas por cobrar comerciales', tipo: 'ACTIVO', rubro: 'CORRIENTE' },
  { codigo: '14', nombre: 'Cuentas por cobrar al personal y accionistas', tipo: 'ACTIVO', rubro: 'CORRIENTE' },
  { codigo: '20', nombre: 'Mercaderías', tipo: 'ACTIVO', rubro: 'CORRIENTE' },
  { codigo: '25', nombre: 'Materiales auxiliares, suministros y repuestos', tipo: 'ACTIVO', rubro: 'CORRIENTE' },
  { codigo: '33', nombre: 'Inmuebles, maquinaria y equipo', tipo: 'ACTIVO', rubro: 'NO_CORRIENTE' },
  { codigo: '34', nombre: 'Intangibles', tipo: 'ACTIVO', rubro: 'NO_CORRIENTE' },
  { codigo: '40', nombre: 'Tributos por pagar', tipo: 'PASIVO', rubro: 'CORRIENTE' },
  { codigo: '41', nombre: 'Remuneraciones por pagar', tipo: 'PASIVO', rubro: 'CORRIENTE' },
  { codigo: '42', nombre: 'Cuentas por pagar comerciales', tipo: 'PASIVO', rubro: 'CORRIENTE' },
  { codigo: '45', nombre: 'Obligaciones financieras', tipo: 'PASIVO', rubro: 'NO_CORRIENTE' },
  { codigo: '50', nombre: 'Capital', tipo: 'PATRIMONIO' },
  { codigo: '59', nombre: 'Resultados acumulados', tipo: 'PATRIMONIO' },
  { codigo: '60', nombre: 'Compras', tipo: 'GASTO', rubro: 'COSTO_VENTAS' },
  { codigo: '62', nombre: 'Gastos de personal', tipo: 'GASTO', rubro: 'GASTO_ADMINISTRACION' },
  { codigo: '63', nombre: 'Gastos de servicios prestados por terceros', tipo: 'GASTO', rubro: 'GASTO_ADMINISTRACION' },
  { codigo: '65', nombre: 'Otros gastos de gestión', tipo: 'GASTO', rubro: 'OTRO_GASTO' },
  { codigo: '67', nombre: 'Gastos financieros', tipo: 'GASTO', rubro: 'GASTO_FINANCIERO' },
  { codigo: '69', nombre: 'Costo de ventas', tipo: 'GASTO', rubro: 'COSTO_VENTAS' },
  { codigo: '70', nombre: 'Ventas', tipo: 'INGRESO', rubro: 'VENTAS' },
  { codigo: '74', nombre: 'Descuentos, rebajas y bonificaciones concedidos', tipo: 'INGRESO', rubro: 'DESCUENTOS_VENTAS' },
  { codigo: '75', nombre: 'Otros ingresos de gestión', tipo: 'INGRESO', rubro: 'OTRO_INGRESO' },
  { codigo: '77', nombre: 'Ingresos financieros', tipo: 'INGRESO', rubro: 'INGRESO_FINANCIERO' },
  { codigo: '94', nombre: 'Gastos de administración', tipo: 'GASTO', rubro: 'GASTO_ADMINISTRACION' },
  { codigo: '95', nombre: 'Gastos de ventas', tipo: 'GASTO', rubro: 'GASTO_VENTAS' },
];

const NUMERADO: DefinicionCuenta[] = [
  { codigo: '101', nombre: 'Caja', tipo: 'ACTIVO', rubro: 'CORRIENTE' },
  { codigo: '102', nombre: 'Banco', tipo: 'ACTIVO', rubro: 'CORRIENTE' },
  { codigo: '103', nombre: 'Clientes', tipo: 'ACTIVO', rubro: 'CORRIENTE' },
  { codigo: '104', nombre: 'Letras por Cobrar', tipo: 'ACTIVO', rubro: 'CORRIENTE' },
  { codigo: '105', nombre: 'Mercaderías', tipo: 'ACTIVO', rubro: 'CORRIENTE' },
  { codigo: '106', nombre: 'IGV Crédito Fiscal', tipo: 'ACTIVO', rubro: 'CORRIENTE' },
  { codigo: '107', nombre: 'Muebles y Enseres', tipo: 'ACTIVO', rubro: 'NO_CORRIENTE' },
  { codigo: '201', nombre: 'Proveedores', tipo: 'PASIVO', rubro: 'CORRIENTE' },
  { codigo: '202', nombre: 'Letras por Pagar', tipo: 'PASIVO', rubro: 'CORRIENTE' },
  { codigo: '203', nombre: 'IGV Débito Fiscal', tipo: 'PASIVO', rubro: 'CORRIENTE' },
  { codigo: '204', nombre: 'Préstamos Bancarios', tipo: 'PASIVO', rubro: 'NO_CORRIENTE' },
  { codigo: '301', nombre: 'Capital', tipo: 'PATRIMONIO' },
  { codigo: '302', nombre: 'Resultados Acumulados', tipo: 'PATRIMONIO' },
  { codigo: '401', nombre: 'Ventas', tipo: 'INGRESO', rubro: 'VENTAS' },
  { codigo: '402', nombre: 'Devoluciones sobre Ventas', tipo: 'INGRESO', rubro: 'DEVOLUCIONES_VENTAS' },
  { codigo: '403', nombre: 'Ingresos Financieros', tipo: 'INGRESO', rubro: 'INGRESO_FINANCIERO' },
  { codigo: '501', nombre: 'Gastos de Arriendo', tipo: 'GASTO', rubro: 'GASTO_ADMINISTRACION' },
  { codigo: '502', nombre: 'Costo de Ventas', tipo: 'GASTO', rubro: 'COSTO_VENTAS' },
  { codigo: '503', nombre: 'Gastos de Ventas', tipo: 'GASTO', rubro: 'GASTO_VENTAS' },
  { codigo: '504', nombre: 'Gastos Financieros', tipo: 'GASTO', rubro: 'GASTO_FINANCIERO' },
];

export const PLANTILLAS_CUENTAS: PlantillaCuentas[] = [
  {
    id: 'pcge',
    nombre: 'PCGE simplificado (Perú)',
    descripcion: 'Cuentas de dos dígitos: 10 Efectivo, 20 Mercaderías, 50 Capital, 70 Ventas…',
    cuentas: PCGE,
  },
  {
    id: 'numerado',
    nombre: 'Numeración por grupos (101, 201, 301…)',
    descripcion: 'Caja, Banco, Clientes, Proveedores, Capital, Ventas, Costo de ventas…',
    cuentas: NUMERADO,
  },
  {
    id: 'vacio',
    nombre: 'Plan de cuentas vacío',
    descripcion: 'Empieza sin cuentas y crea las tuyas desde el Plan de Cuentas.',
    cuentas: [],
  },
];

export function obtenerPlantilla(id: string): PlantillaCuentas {
  return PLANTILLAS_CUENTAS.find((plantilla) => plantilla.id === id) ?? PLANTILLAS_CUENTAS[0];
}
