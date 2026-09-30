import type { Asiento, Caso, Cuenta } from '../dominio/tipos';
import { nuevoId } from '../dominio/ids';
import { crearCuentas, obtenerPlantilla } from './plantillasCuentas';

interface LineaDemo {
  codigo: string;
  debe?: number;
  haber?: number;
}

interface AsientoDemo {
  fecha: string;
  glosa: string;
  lineas: LineaDemo[];
}

export interface PlantillaCaso {
  id: string;
  nombre: string;
  descripcion: string;
  plantillaCuentas: string;
  empresa: Caso['empresa'];
  asientos: AsientoDemo[];
}

/**
 * Casos de ejemplo. Son solo datos: la lógica de los reportes no depende de ellos.
 * Sirven para comprobar el sistema y para las pruebas automáticas.
 */
export const PLANTILLAS_CASO: PlantillaCaso[] = [
  {
    id: 'cybertec',
    nombre: 'CYBERTEC S.A.',
    descripcion:
      'Constitución con aportes, compra de mercadería, venta al contado y ajuste del costo de ventas.',
    plantillaCuentas: 'pcge',
    empresa: {
      nombre: 'CYBERTEC S.A.',
      ruc: '20100000001',
      simboloMoneda: 'S/',
      periodoInicio: '2024-10-01',
      periodoFin: '2024-10-31',
      tasaImpuestoRenta: 0,
      impuestoAfectaPatrimonio: false,
    },
    asientos: [
      {
        fecha: '2024-10-01',
        glosa: 'Constitución de la empresa: aporte en efectivo y en equipos de cómputo',
        lineas: [
          { codigo: '10', debe: 20000 },
          { codigo: '33', debe: 30000 },
          { codigo: '50', haber: 50000 },
        ],
      },
      {
        fecha: '2024-10-10',
        glosa: 'Compra de mercadería por 20,000',
        lineas: [
          { codigo: '20', debe: 20000 },
          { codigo: '10', haber: 20000 },
        ],
      },
      {
        fecha: '2024-10-20',
        glosa: 'Venta al contado por 20,000',
        lineas: [
          { codigo: '10', debe: 20000 },
          { codigo: '70', haber: 20000 },
        ],
      },
      {
        fecha: '2024-10-30',
        glosa: 'Ajuste por costo de ventas; el inventario cierra en 10,000',
        lineas: [
          { codigo: '69', debe: 10000 },
          { codigo: '20', haber: 10000 },
        ],
      },
    ],
  },
  {
    id: 'metropolitana',
    nombre: 'Comercializadora Metropolitana',
    descripcion:
      'Saldos iniciales, compra con letras e IGV, venta mixta, arriendo, pagos y cobros de letras.',
    plantillaCuentas: 'numerado',
    empresa: {
      nombre: 'Comercializadora Metropolitana',
      ruc: '20100000002',
      simboloMoneda: 'S/',
      periodoInicio: '2023-06-01',
      periodoFin: '2023-06-30',
      tasaImpuestoRenta: 30,
      impuestoAfectaPatrimonio: false,
    },
    asientos: [
      {
        fecha: '2023-06-01',
        glosa: 'Apertura de saldos iniciales',
        lineas: [
          { codigo: '101', debe: 2500000 },
          { codigo: '102', debe: 3500000 },
          { codigo: '103', debe: 600000 },
          { codigo: '201', haber: 800000 },
          { codigo: '301', haber: 5800000 },
        ],
      },
      {
        fecha: '2023-06-01',
        glosa: 'Compra a Adelco Ltda. con 10 letras de cambio',
        lineas: [
          { codigo: '105', debe: 840336 },
          { codigo: '106', debe: 159664 },
          { codigo: '202', haber: 1000000 },
        ],
      },
      {
        fecha: '2023-06-02',
        glosa: 'Venta a Mario Cea Castro: 40% en efectivo y 60% en letras',
        lineas: [
          { codigo: '101', debe: 190400 },
          { codigo: '104', debe: 285600 },
          { codigo: '401', haber: 400000 },
          { codigo: '203', haber: 76000 },
        ],
      },
      {
        fecha: '2023-06-10',
        glosa: 'Pago del arriendo de oficina con cheque',
        lineas: [
          { codigo: '501', debe: 100000 },
          { codigo: '102', haber: 100000 },
        ],
      },
      {
        fecha: '2023-06-11',
        glosa: 'Pago del 50% de la deuda a proveedores con cheque',
        lineas: [
          { codigo: '201', debe: 400000 },
          { codigo: '102', haber: 400000 },
        ],
      },
      {
        fecha: '2023-06-15',
        glosa: 'Cobro de las letras 101 y 102 a Mario Cea Castro',
        lineas: [
          { codigo: '101', debe: 142800 },
          { codigo: '104', haber: 142800 },
        ],
      },
      {
        fecha: '2023-06-30',
        glosa: 'Pago de 3 letras a Adelco Ltda. con cheque',
        lineas: [
          { codigo: '202', debe: 300000 },
          { codigo: '102', haber: 300000 },
        ],
      },
      {
        fecha: '2023-06-30',
        glosa: 'Ajuste por costo de ventas; existencia final de mercaderías 690,360',
        lineas: [
          { codigo: '502', debe: 149976 },
          { codigo: '105', haber: 149976 },
        ],
      },
    ],
  },
];

/** Convierte una plantilla de caso en un caso nuevo, con identificadores propios. */
export function construirCasoDemo(plantilla: PlantillaCaso, ahora = new Date().toISOString()): Caso {
  const cuentas: Cuenta[] = crearCuentas(obtenerPlantilla(plantilla.plantillaCuentas).cuentas);
  const porCodigo = new Map(cuentas.map((cuenta) => [cuenta.codigo, cuenta.id]));

  const asientos: Asiento[] = plantilla.asientos.map((demo, indice) => ({
    id: nuevoId('asi'),
    numero: indice + 1,
    fecha: demo.fecha,
    glosa: demo.glosa,
    lineas: demo.lineas.map((linea) => {
      const cuentaId = porCodigo.get(linea.codigo);
      if (!cuentaId) {
        throw new Error(
          `El caso "${plantilla.nombre}" usa la cuenta ${linea.codigo}, que no existe en su plan de cuentas.`,
        );
      }
      return {
        id: nuevoId('lin'),
        cuentaId,
        debe: linea.debe ?? 0,
        haber: linea.haber ?? 0,
      };
    }),
  }));

  return {
    id: nuevoId('caso'),
    nombre: plantilla.nombre,
    creadoEn: ahora,
    actualizadoEn: ahora,
    empresa: { ...plantilla.empresa },
    cuentas,
    asientos,
  };
}

export function obtenerPlantillaCaso(id: string): PlantillaCaso | undefined {
  return PLANTILLAS_CASO.find((plantilla) => plantilla.id === id);
}
