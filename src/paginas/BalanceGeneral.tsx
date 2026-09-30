import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useAlmacen } from '../almacen/almacen';
import { useAvisos } from '../componentes/Avisos';
import { CabeceraReporte } from '../componentes/CabeceraReporte';
import { Aviso, Boton, EstadoVacio, MarcaCuadre, Tarjeta } from '../componentes/ui';
import { IconoDescargar, IconoMas } from '../componentes/Iconos';
import { construirBalanceGeneral, type BloqueBalance } from '../dominio/balanceGeneral';
import { formatearMoneda, formatearNumero } from '../dominio/formato';
import { exportarCsv, nombreDeArchivo } from '../servicios/archivos';

function TablaBloque({
  bloque,
  simbolo,
  extra,
}: {
  bloque: BloqueBalance;
  simbolo: string;
  extra?: { etiqueta: string; monto: number };
}) {
  if (bloque.cuentas.length === 0 && !extra) return null;
  return (
    <div className="tabla-envoltorio">
      <table className="tabla">
        <tbody>
          {bloque.cuentas.map((detalle) => (
            <tr key={detalle.cuenta.id}>
              <td className="codigo" style={{ width: 90 }}>
                {detalle.cuenta.codigo}
              </td>
              <td>{detalle.cuenta.nombre}</td>
              <td className="numero" style={{ width: 170 }}>
                {formatearNumero(detalle.monto)}
              </td>
            </tr>
          ))}
          {extra && (
            <tr>
              <td className="codigo" />
              <td>{extra.etiqueta}</td>
              <td className="numero">{formatearNumero(extra.monto)}</td>
            </tr>
          )}
          <tr className="fila-total">
            <td colSpan={2}>Total {bloque.etiqueta.toLowerCase()}</td>
            <td className="numero">
              {formatearMoneda(bloque.total + (extra?.monto ?? 0), simbolo)}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export function BalanceGeneral() {
  const almacen = useAlmacen();
  const avisos = useAvisos();
  const caso = almacen.casoActivo;
  const general = useMemo(() => (caso ? construirBalanceGeneral(caso) : null), [caso]);

  if (!caso || !general) return null;
  const simbolo = caso.empresa.simboloMoneda;

  const vacio =
    general.activoCorriente.cuentas.length === 0 &&
    general.activoNoCorriente.cuentas.length === 0 &&
    general.pasivoCorriente.cuentas.length === 0 &&
    general.pasivoNoCorriente.cuentas.length === 0 &&
    general.patrimonio.cuentas.length === 0;

  function exportar() {
    if (!general) return;
    const filas: (string | number)[][] = [['Seccion', 'Codigo', 'Cuenta', 'Importe']];
    const bloques = [
      general.activoCorriente,
      general.activoNoCorriente,
      general.pasivoCorriente,
      general.pasivoNoCorriente,
      general.patrimonio,
    ];
    for (const bloque of bloques) {
      for (const detalle of bloque.cuentas) {
        filas.push([
          bloque.etiqueta,
          detalle.cuenta.codigo,
          detalle.cuenta.nombre,
          formatearNumero(detalle.monto),
        ]);
      }
    }
    filas.push(['Patrimonio', '', 'Resultado del ejercicio', formatearNumero(general.resultadoEjercicio)]);
    filas.push(['', '', 'TOTAL ACTIVO', formatearNumero(general.totalActivo)]);
    filas.push(['', '', 'TOTAL PASIVO', formatearNumero(general.totalPasivo)]);
    filas.push(['', '', 'TOTAL PATRIMONIO', formatearNumero(general.totalPatrimonio)]);
    filas.push([
      '',
      '',
      'TOTAL PASIVO + PATRIMONIO',
      formatearNumero(general.totalPasivoPatrimonio),
    ]);
    exportarCsv(nombreDeArchivo(`balance-general-${caso?.nombre ?? ''}`, 'csv'), filas);
    avisos.exito('Balance general exportado en CSV.');
  }

  return (
    <>
      <CabeceraReporte
        caso={caso}
        titulo="Balance General"
        acciones={
          <Boton
            variante="secundario"
            icono={<IconoDescargar tamano={16} />}
            onClick={exportar}
            disabled={vacio}
          >
            CSV
          </Boton>
        }
      />

      {vacio ? (
        <Tarjeta>
          <EstadoVacio
            titulo="No hay saldos de balance"
            descripcion="El balance general muestra las cuentas de activo, pasivo y patrimonio con movimiento."
            accion={
              <Link to="/asientos">
                <Boton icono={<IconoMas tamano={16} />}>Registrar asiento</Boton>
              </Link>
            }
          />
        </Tarjeta>
      ) : (
        <>
          <div className="rejilla rejilla-2">
            <section className="tarjeta">
              <div className="bloque-titulo">Activo</div>
              <TablaBloque bloque={general.activoCorriente} simbolo={simbolo} />
              <TablaBloque bloque={general.activoNoCorriente} simbolo={simbolo} />
              <div className="cuenta-t-pie">
                <span>TOTAL ACTIVO</span>
                <span>{formatearMoneda(general.totalActivo, simbolo)}</span>
              </div>
            </section>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <section className="tarjeta">
                <div className="bloque-titulo pasivo">Pasivo</div>
                {general.pasivoCorriente.cuentas.length === 0 &&
                general.pasivoNoCorriente.cuentas.length === 0 ? (
                  <div style={{ padding: 16 }} className="atenuado">
                    La empresa no tiene pasivos registrados.
                  </div>
                ) : (
                  <>
                    <TablaBloque bloque={general.pasivoCorriente} simbolo={simbolo} />
                    <TablaBloque bloque={general.pasivoNoCorriente} simbolo={simbolo} />
                  </>
                )}
                <div className="cuenta-t-pie">
                  <span>TOTAL PASIVO</span>
                  <span>{formatearMoneda(general.totalPasivo, simbolo)}</span>
                </div>
              </section>

              <section className="tarjeta">
                <div className="bloque-titulo patrimonio">Patrimonio</div>
                <TablaBloque
                  bloque={general.patrimonio}
                  simbolo={simbolo}
                  extra={{
                    etiqueta: general.resultadoNetoDeImpuesto
                      ? 'Resultado del ejercicio (neto de impuesto)'
                      : 'Resultado del ejercicio (antes de impuesto)',
                    monto: general.resultadoEjercicio,
                  }}
                />
              </section>

              <section className="tarjeta">
                <div className="cuenta-t-pie" style={{ background: 'var(--azul-900)', color: '#fff' }}>
                  <span>TOTAL PASIVO + PATRIMONIO</span>
                  <span>{formatearMoneda(general.totalPasivoPatrimonio, simbolo)}</span>
                </div>
              </section>
            </div>
          </div>

          <Tarjeta titulo="Comprobación de la ecuación contable">
            <div className="ecuacion">
              <strong>Total Activo = Total Pasivo + Total Patrimonio</strong>
              <div>
                {formatearMoneda(general.totalActivo, simbolo)} ={' '}
                {formatearMoneda(general.totalPasivo, simbolo)} +{' '}
                {formatearMoneda(general.totalPatrimonio, simbolo)}
              </div>
              <div style={{ marginTop: 10 }}>
                {formatearMoneda(general.totalActivo, simbolo)} ={' '}
                {formatearMoneda(general.totalPasivoPatrimonio, simbolo)}
              </div>
            </div>
            <MarcaCuadre
              cuadrado={general.cuadrado}
              textoOk="Sí cumple: el balance general está correctamente estructurado."
              textoMal={`No cumple: hay una diferencia de ${formatearMoneda(
                Math.abs(general.diferencia),
                simbolo,
              )}.`}
            />
          </Tarjeta>

          {!general.cuadrado && general.resultadoNetoDeImpuesto && (
            <Aviso tipo="advertencia">
              El patrimonio está descontando el impuesto a la renta, pero ese impuesto no se registró
              como asiento. Por eso la ecuación no cierra. Desactiva la opción en Configuración o
              registra el asiento del impuesto.
            </Aviso>
          )}

          <Aviso tipo="info">
            El resultado del ejercicio ({formatearMoneda(general.resultadoEjercicio, simbolo)}) viene
            del Estado de Resultados y se suma al patrimonio, porque las cuentas de ingreso y gasto se
            cierran contra el patrimonio.
          </Aviso>
        </>
      )}
    </>
  );
}
