import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useAlmacen } from '../almacen/almacen';
import { useAvisos } from '../componentes/Avisos';
import { CabeceraReporte } from '../componentes/CabeceraReporte';
import { Boton, EstadoVacio, MarcaCuadre, Tarjeta } from '../componentes/ui';
import { IconoDescargar, IconoMas } from '../componentes/Iconos';
import { construirBalanceComprobacion } from '../dominio/balanceComprobacion';
import { ETIQUETA_TIPO } from '../dominio/cuentas';
import { formatearMoneda, formatearNumero } from '../dominio/formato';
import { exportarCsv, nombreDeArchivo } from '../servicios/archivos';

export function BalanceComprobacion() {
  const almacen = useAlmacen();
  const avisos = useAvisos();
  const caso = almacen.casoActivo;
  const balance = useMemo(() => (caso ? construirBalanceComprobacion(caso) : null), [caso]);

  if (!caso || !balance) return null;
  const simbolo = caso.empresa.simboloMoneda;

  function exportar() {
    if (!balance) return;
    exportarCsv(nombreDeArchivo(`balance-comprobacion-${caso?.nombre ?? ''}`, 'csv'), [
      ['Codigo', 'Cuenta', 'Grupo', 'Suma Debe', 'Suma Haber', 'Saldo Deudor', 'Saldo Acreedor'],
      ...balance.filas.map((fila) => [
        fila.cuenta.codigo,
        fila.cuenta.nombre,
        ETIQUETA_TIPO[fila.cuenta.tipo],
        formatearNumero(fila.sumaDebe),
        formatearNumero(fila.sumaHaber),
        fila.saldoDeudor ? formatearNumero(fila.saldoDeudor) : '',
        fila.saldoAcreedor ? formatearNumero(fila.saldoAcreedor) : '',
      ]),
      [
        '',
        'TOTALES',
        '',
        formatearNumero(balance.totalDebe),
        formatearNumero(balance.totalHaber),
        formatearNumero(balance.totalDeudor),
        formatearNumero(balance.totalAcreedor),
      ],
    ]);
    avisos.exito('Balance de comprobación exportado en CSV.');
  }

  return (
    <>
      <CabeceraReporte
        caso={caso}
        titulo="Balance de Comprobación"
        acciones={
          <Boton
            variante="secundario"
            icono={<IconoDescargar tamano={16} />}
            onClick={exportar}
            disabled={balance.filas.length === 0}
          >
            CSV
          </Boton>
        }
      />

      {balance.filas.length === 0 ? (
        <Tarjeta>
          <EstadoVacio
            titulo="No hay saldos que comprobar"
            descripcion="El balance de comprobación resume las sumas y los saldos de cada cuenta con movimiento."
            accion={
              <Link to="/asientos">
                <Boton icono={<IconoMas tamano={16} />}>Registrar asiento</Boton>
              </Link>
            }
          />
        </Tarjeta>
      ) : (
        <>
          <Tarjeta
            titulo="Sumas y saldos"
            subtitulo="Verificación del cuadre entre los totales del Debe y del Haber."
            sinEspacio
          >
            <div className="tabla-envoltorio">
              <table className="tabla">
                <thead>
                  <tr>
                    <th rowSpan={2} style={{ width: 100 }}>
                      Código
                    </th>
                    <th rowSpan={2}>Cuenta</th>
                    <th rowSpan={2} style={{ width: 120 }}>
                      Grupo
                    </th>
                    <th colSpan={2} style={{ textAlign: 'center' }}>
                      Sumas
                    </th>
                    <th colSpan={2} style={{ textAlign: 'center' }}>
                      Saldos
                    </th>
                  </tr>
                  <tr>
                    <th className="numero">Debe</th>
                    <th className="numero">Haber</th>
                    <th className="numero">Deudor</th>
                    <th className="numero">Acreedor</th>
                  </tr>
                </thead>
                <tbody>
                  {balance.filas.map((fila) => (
                    <tr key={fila.cuenta.id}>
                      <td className="codigo">{fila.cuenta.codigo}</td>
                      <td>{fila.cuenta.nombre}</td>
                      <td>
                        <span className={`etiqueta ${fila.cuenta.tipo}`}>
                          {ETIQUETA_TIPO[fila.cuenta.tipo]}
                        </span>
                      </td>
                      <td className="numero">{formatearNumero(fila.sumaDebe)}</td>
                      <td className="numero">{formatearNumero(fila.sumaHaber)}</td>
                      <td className="numero debe">
                        {fila.saldoDeudor ? formatearNumero(fila.saldoDeudor) : ''}
                      </td>
                      <td className="numero haber">
                        {fila.saldoAcreedor ? formatearNumero(fila.saldoAcreedor) : ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <td colSpan={3}>TOTALES</td>
                    <td className="numero">{formatearMoneda(balance.totalDebe, simbolo)}</td>
                    <td className="numero">{formatearMoneda(balance.totalHaber, simbolo)}</td>
                    <td className="numero">{formatearMoneda(balance.totalDeudor, simbolo)}</td>
                    <td className="numero">{formatearMoneda(balance.totalAcreedor, simbolo)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </Tarjeta>

          <MarcaCuadre
            cuadrado={balance.cuadrado}
            textoOk={`Balance cuadrado: los totales del Debe (${formatearMoneda(
              balance.totalDebe,
              simbolo,
            )}) y del Haber coinciden, igual que los saldos deudor y acreedor.`}
            textoMal={`Balance descuadrado: diferencia de ${formatearMoneda(
              Math.abs(balance.diferenciaSumas || balance.diferenciaSaldos),
              simbolo,
            )}. Revisa los asientos del libro diario.`}
          />
        </>
      )}
    </>
  );
}
