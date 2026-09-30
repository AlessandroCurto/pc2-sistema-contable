import type { ReactNode } from 'react';
import {
  IconoAjustes,
  IconoAsiento,
  IconoBalanceGeneral,
  IconoBalanza,
  IconoCasos,
  IconoDiario,
  IconoInicio,
  IconoMayor,
  IconoPdf,
  IconoPlan,
  IconoResultados,
} from './Iconos';

export interface EntradaMenu {
  ruta: string;
  etiqueta: string;
  descripcion: string;
  icono: ReactNode;
  grupo: 'Principal' | 'Operaciones' | 'Reportes' | 'Descargas' | 'Sistema';
  /** true cuando la pantalla necesita un caso abierto. */
  requiereCaso: boolean;
}

export const MENU: EntradaMenu[] = [
  {
    ruta: '/',
    etiqueta: 'Inicio',
    descripcion: 'Resumen del caso abierto y accesos rápidos',
    icono: <IconoInicio />,
    grupo: 'Principal',
    requiereCaso: false,
  },
  {
    ruta: '/casos',
    etiqueta: 'Casos',
    descripcion: 'Crear, abrir, importar y exportar casos contables',
    icono: <IconoCasos />,
    grupo: 'Principal',
    requiereCaso: false,
  },
  {
    ruta: '/plan-de-cuentas',
    etiqueta: 'Plan de Cuentas',
    descripcion: 'Gestionar el catálogo de cuentas contables y su clasificación',
    icono: <IconoPlan />,
    grupo: 'Operaciones',
    requiereCaso: true,
  },
  {
    ruta: '/asientos',
    etiqueta: 'Registrar Asiento',
    descripcion: 'Crear un nuevo asiento contable con sus movimientos al Debe y al Haber',
    icono: <IconoAsiento />,
    grupo: 'Operaciones',
    requiereCaso: true,
  },
  {
    ruta: '/libro-diario',
    etiqueta: 'Libro Diario',
    descripcion: 'Consultar todos los asientos registrados ordenados por fecha',
    icono: <IconoDiario />,
    grupo: 'Reportes',
    requiereCaso: true,
  },
  {
    ruta: '/libro-mayor',
    etiqueta: 'Libro Mayor',
    descripcion: 'Ver los movimientos y saldos agrupados por cada cuenta contable',
    icono: <IconoMayor />,
    grupo: 'Reportes',
    requiereCaso: true,
  },
  {
    ruta: '/balance-comprobacion',
    etiqueta: 'Balance de Comprobación',
    descripcion: 'Verificar que los totales del Debe y del Haber estén cuadrados',
    icono: <IconoBalanza />,
    grupo: 'Reportes',
    requiereCaso: true,
  },
  {
    ruta: '/estado-resultados',
    etiqueta: 'Estado de Resultados',
    descripcion: 'Calcular la utilidad o pérdida del período',
    icono: <IconoResultados />,
    grupo: 'Reportes',
    requiereCaso: true,
  },
  {
    ruta: '/balance-general',
    etiqueta: 'Balance General',
    descripcion: 'Verificar la ecuación contable: Activo = Pasivo + Patrimonio',
    icono: <IconoBalanceGeneral />,
    grupo: 'Reportes',
    requiereCaso: true,
  },
  {
    ruta: '/reporte',
    etiqueta: 'Generar PDF / Enviar',
    descripcion: 'Reunir todos los reportes en un solo archivo PDF',
    icono: <IconoPdf />,
    grupo: 'Descargas',
    requiereCaso: true,
  },
  {
    ruta: '/configuracion',
    etiqueta: 'Configuración',
    descripcion: 'Datos de la empresa, período e impuesto a la renta',
    icono: <IconoAjustes />,
    grupo: 'Sistema',
    requiereCaso: true,
  },
];

export const GRUPOS_MENU: EntradaMenu['grupo'][] = [
  'Principal',
  'Operaciones',
  'Reportes',
  'Descargas',
  'Sistema',
];

export function entradaDeRuta(ruta: string): EntradaMenu | undefined {
  if (ruta === '/') return MENU[0];
  return MENU.find((entrada) => entrada.ruta !== '/' && ruta.startsWith(entrada.ruta));
}
