import { describe, expect, it } from 'vitest';
import {
  construirBalanceComprobacion,
  construirBalanceGeneral,
  construirEstadoResultados,
  construirLibroDiario,
  construirLibroMayor,
  movimientoDesdeSigno,
  redondear,
  resumirAsiento,
  validarAsiento,
} from '../src/dominio';
import type { Caso } from '../src/dominio';
import { PLANTILLAS_CASO, construirCasoDemo, obtenerPlantillaCaso } from '../src/datos/casosDemo';

function caso(id: string): Caso {
  const plantilla = obtenerPlantillaCaso(id);
  if (!plantilla) throw new Error('Falta el caso de ejemplo ' + id);
  return construirCasoDemo(plantilla, '2024-01-01T00:00:00.000Z');
}

describe('casos de ejemplo', () => {
  it('todos los asientos de todos los casos cuadran', () => {
    for (const plantilla of PLANTILLAS_CASO) {
      const demo = construirCasoDemo(plantilla);
      for (const asiento of demo.asientos) {
        const resumen = resumirAsiento(asiento.lineas);
        expect(resumen.cuadrado, plantilla.nombre + ' asiento ' + asiento.numero).toBe(true);
      }
    }
  });

  it('el balance de comprobacion cuadra en todos los casos', () => {
    for (const plantilla of PLANTILLAS_CASO) {
      const balance = construirBalanceComprobacion(construirCasoDemo(plantilla));
      expect(balance.cuadrado, plantilla.nombre).toBe(true);
    }
  });

  it('el balance general cuadra en todos los casos', () => {
    for (const plantilla of PLANTILLAS_CASO) {
      const general = construirBalanceGeneral(construirCasoDemo(plantilla));
      expect(general.cuadrado, plantilla.nombre).toBe(true);
    }
  });
});

describe('CYBERTEC S.A.', () => {
  const demo = caso('cybertec');

  it('el libro diario ordena los asientos por fecha', () => {
    const diario = construirLibroDiario(demo);
    expect(diario.asientos.map((item) => item.asiento.fecha)).toEqual([
      '2024-10-01',
      '2024-10-10',
      '2024-10-20',
      '2024-10-30',
    ]);
    expect(diario.totalDebe).toBe(diario.totalHaber);
  });

  it('el libro mayor deja el efectivo en 20,000 y la mercaderia en 10,000', () => {
    const mayor = construirLibroMayor(demo);
    const activos = mayor.grupos.find((grupo) => grupo.tipo === 'ACTIVO');
    const efectivo = activos?.cuentas.find((item) => item.cuenta.codigo === '10');
    const mercaderia = activos?.cuentas.find((item) => item.cuenta.codigo === '20');
    expect(efectivo?.saldo).toBe(20000);
    expect(efectivo?.naturalezaSaldo).toBe('DEUDOR');
    expect(mercaderia?.saldo).toBe(10000);
  });

  it('el balance de comprobacion suma 100,000 en cada columna', () => {
    const balance = construirBalanceComprobacion(demo);
    expect(balance.totalDebe).toBe(100000);
    expect(balance.totalHaber).toBe(100000);
    expect(balance.cuadrado).toBe(true);
  });

  it('el estado de resultados da 10,000 de utilidad neta', () => {
    const estado = construirEstadoResultados(demo);
    expect(estado.ventas).toBe(20000);
    expect(estado.costoVentas).toBe(10000);
    expect(estado.utilidadBruta).toBe(10000);
    expect(estado.utilidadNeta).toBe(10000);
  });

  it('el balance general cuadra en 60,000', () => {
    const general = construirBalanceGeneral(demo);
    expect(general.totalActivo).toBe(60000);
    expect(general.totalPasivo).toBe(0);
    expect(general.totalPatrimonio).toBe(60000);
    expect(general.cuadrado).toBe(true);
  });
});

describe('Comercializadora Metropolitana', () => {
  const demo = caso('metropolitana');

  it('reproduce el balance de comprobacion de 9,168,776.00', () => {
    const balance = construirBalanceComprobacion(demo);
    expect(balance.totalDebe).toBe(9168776);
    expect(balance.totalHaber).toBe(9168776);
    expect(balance.totalDeudor).toBe(7376000);
    expect(balance.totalAcreedor).toBe(7376000);
    expect(balance.cuadrado).toBe(true);
  });

  it('reproduce el estado de resultados con 30% de impuesto', () => {
    const estado = construirEstadoResultados(demo);
    expect(estado.ventas).toBe(400000);
    expect(estado.costoVentas).toBe(149976);
    expect(estado.utilidadBruta).toBe(250024);
    expect(estado.utilidadOperativa).toBe(150024);
    expect(estado.impuesto).toBe(45007.2);
    expect(estado.utilidadNeta).toBe(105016.8);
  });

  it('reproduce el balance general de 7,126,024.00', () => {
    const general = construirBalanceGeneral(demo);
    expect(general.totalActivo).toBe(7126024);
    expect(general.totalPasivo).toBe(1176000);
    expect(general.totalPatrimonioAportado).toBe(5800000);
    expect(general.resultadoEjercicio).toBe(150024);
    expect(general.totalPatrimonio).toBe(5950024);
    expect(general.cuadrado).toBe(true);
  });

  it('descuenta el impuesto del patrimonio cuando se activa la opcion', () => {
    const conImpuesto: Caso = {
      ...demo,
      empresa: { ...demo.empresa, impuestoAfectaPatrimonio: true },
    };
    const general = construirBalanceGeneral(conImpuesto);
    expect(general.resultadoEjercicio).toBe(105016.8);
    expect(general.cuadrado).toBe(false);
  });

  it('el saldo de mercaderias cierra en 690,360', () => {
    const mayor = construirLibroMayor(demo);
    const activos = mayor.grupos.find((grupo) => grupo.tipo === 'ACTIVO');
    const mercaderias = activos?.cuentas.find((item) => item.cuenta.codigo === '105');
    expect(mercaderias?.saldo).toBe(690360);
  });
});

describe('validacion de asientos', () => {
  const demo = caso('cybertec');
  const efectivo = demo.cuentas.find((cuenta) => cuenta.codigo === '10');
  const capital = demo.cuentas.find((cuenta) => cuenta.codigo === '50');
  const idEfectivo = efectivo ? efectivo.id : '';
  const idCapital = capital ? capital.id : '';

  it('acepta un asiento cuadrado', () => {
    const errores = validarAsiento(
      {
        fecha: '2024-11-01',
        glosa: 'Aporte adicional',
        lineas: [
          { id: 'l1', cuentaId: idEfectivo, debe: 500, haber: 0 },
          { id: 'l2', cuentaId: idCapital, debe: 0, haber: 500 },
        ],
      },
      demo.cuentas,
    );
    expect(errores.cuadre).toBeUndefined();
    expect(errores.lineas).toBeUndefined();
    expect(Object.keys(errores.porLinea)).toHaveLength(0);
  });

  it('rechaza un asiento descuadrado y dice la diferencia', () => {
    const errores = validarAsiento(
      {
        fecha: '2024-11-01',
        glosa: '',
        lineas: [
          { id: 'l1', cuentaId: idEfectivo, debe: 500, haber: 0 },
          { id: 'l2', cuentaId: idCapital, debe: 0, haber: 300 },
        ],
      },
      demo.cuentas,
    );
    expect(errores.cuadre).toContain('200.00');
  });

  it('rechaza una linea con importe en Debe y en Haber a la vez', () => {
    const errores = validarAsiento(
      {
        fecha: '2024-11-01',
        glosa: '',
        lineas: [
          { id: 'l1', cuentaId: idEfectivo, debe: 500, haber: 500 },
          { id: 'l2', cuentaId: idCapital, debe: 0, haber: 500 },
        ],
      },
      demo.cuentas,
    );
    expect(errores.porLinea.l1).toBeTruthy();
  });

  it('rechaza una cuenta que no existe', () => {
    const errores = validarAsiento(
      {
        fecha: '2024-11-01',
        glosa: '',
        lineas: [
          { id: 'l1', cuentaId: 'inexistente', debe: 500, haber: 0 },
          { id: 'l2', cuentaId: idCapital, debe: 0, haber: 500 },
        ],
      },
      demo.cuentas,
    );
    expect(errores.porLinea.l1).toBeTruthy();
  });

  it('rechaza una fecha invalida', () => {
    const errores = validarAsiento({ fecha: '', glosa: '', lineas: [] }, demo.cuentas);
    expect(errores.fecha).toBeTruthy();
  });
});

describe('modo simple con signo', () => {
  it('un mas aumenta la cuenta segun su naturaleza', () => {
    expect(movimientoDesdeSigno('ACTIVO', '+', 100)).toEqual({ debe: 100, haber: 0 });
    expect(movimientoDesdeSigno('GASTO', '+', 100)).toEqual({ debe: 100, haber: 0 });
    expect(movimientoDesdeSigno('PATRIMONIO', '+', 100)).toEqual({ debe: 0, haber: 100 });
    expect(movimientoDesdeSigno('INGRESO', '+', 100)).toEqual({ debe: 0, haber: 100 });
    expect(movimientoDesdeSigno('PASIVO', '+', 100)).toEqual({ debe: 0, haber: 100 });
  });

  it('un menos invierte el lado', () => {
    expect(movimientoDesdeSigno('ACTIVO', '-', 100)).toEqual({ debe: 0, haber: 100 });
    expect(movimientoDesdeSigno('PASIVO', '-', 100)).toEqual({ debe: 100, haber: 0 });
  });
});

describe('redondeo', () => {
  it('trabaja con dos decimales', () => {
    expect(redondear(0.1 + 0.2)).toBe(0.3);
    expect(redondear(150024 * 0.3)).toBe(45007.2);
  });
});
