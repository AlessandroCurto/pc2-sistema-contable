import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useAlmacen } from '../almacen/almacen';
import { useAvisos } from '../componentes/Avisos';
import { CabeceraReporte } from '../componentes/CabeceraReporte';
import { Boton, EstadoVacio, Tarjeta } from '../componentes/ui';
import { IconoDescargar, IconoMas } from '../componentes/Iconos';
import { construirLibroMayor } from '../dominio/libroMayor';
import { formatearFecha, formatearMoneda, formatearNumero } from '../dominio/formato';
import { exportarCsv, nombreDeArchivo } from '../servicios/archivos';

export function LibroMayor() {
  const almacen = useAlmacen();
  const avisos = useAvisos();
  const caso = almacen.casoActivo;
  const mayor = useMemo(() => (caso ? construirLibroMayor(caso) : null), [caso]);

  if (!caso || !mayor) return null;
  const simbolo = caso.empresa.simboloMoneda;

  function exportar() {
    if (!mayor) return;
    const filas: (string | number)[][] = [
      ['Grupo', 'Codigo', 'Cuenta', 'Fecha', 'Asiento', 'Glosa', 'Debe', 'Haber', 'Saldo'],
    ];
    for (const grupo of mayor.grupos) {
      for (const item of grupo.cuentas) {
        for (const movimiento of item.movimientos) {
          filas.push([
            grupo.etiqueta,
            item.cuenta.codigo,
            item.cuenta.nombre,
            movimiento.fecha,
            `#${movimiento.numero}`,
            movimiento.glosa,
            movimiento.debe ? formatearNumero(movimiento.debe) : '',
            movimiento.haber ? formatearNumero(movimiento.haber) : '',
            formatearNumero(movimiento.saldo),
          ]);
        }
        filas.push([
          grupo.etiqueta,
          item.cuenta.codigo,
          `TOTAL ${item.cuenta.nombre}`,
          '',
          '',
          `Saldo ${item.naturalezaSaldo.toLowerCase()}`,
          formatearNumero(item.totalDebe),
          formatearNumero(item.totalHaber),
          formatearNumero(item.saldo),
        ]);
      }
    }
    exportarCsv(nombreDeArchivo(`libro-mayor-${caso?.nombre ?? ''}`, 'csv'), filas);
    avisos.exito('Libro mayor exportado en CSV.');
  }

  return (
    <>
      <CabeceraReporte
        caso={caso}
        titulo="Libro Mayor"
        acciones={
          <Boton
            variante="secundario"
            icono={<IconoDescargar tamano={16} />}
            onClick={exportar}
            disabled={mayor.grupos.length === 0}
          >
            CSV
          </Boton>
        }
      />

      {mayor.grupos.length === 0 ? (
        <Tarjeta>
          <EstadoVacio
            titulo="No hay movimientos que mayorizar"
            descripcion="El libro mayor se arma con los asientos del libro diario."
            accion={
              <Link to="/asientos">
                <Boton icono={<IconoMas tamano={16} />}>Registrar asiento</Boton>
              </Link>
            }
          />
        </Tarjeta>
      ) : (
        mayor.grupos.map((grupo) => (
          <Tarjeta
            key={grupo.tipo}
            titulo={grupo.etiqueta.toUpperCase()}
            subtitulo={`${grupo.cuentas.length} cuentas con movimiento · Debe ${formatearMoneda(
              grupo.totalDebe,
              simbolo,
            )} · Haber ${formatearMoneda(grupo.totalHaber, simbolo)}`}
          >
            <div className="rejilla rejilla-2">
              {grupo.cuentas.map((item) => (
                <div key={item.cuenta.id} className="cuenta-t">
                  <div className="cuenta-t-cabecera">
                    <span className="codigo">{item.cuenta.codigo}</span>
                    <span>{item.cuenta.nombre}</span>
                    <span className={`etiqueta ${item.cuenta.tipo}`} style={{ marginLeft: 'auto' }}>
                      {item.naturalezaSaldo === 'DEUDOR' ? 'Saldo deudor' : 'Saldo acreedor'}
                    </span>
                  </div>
                  <div className="tabla-envoltorio">
                    <table className="tabla">
                      <thead>
                        <tr>
                          <th>Fecha</th>
                          <th>Ref.</th>
                          <th className="numero">Debe</th>
                          <th className="numero">Haber</th>
                          <th className="numero">Saldo</th>
                        </tr>
                      </thead>
                      <tbody>
                        {item.movimientos.map((movimiento, indice) => (
                          <tr key={`${item.cuenta.id}-${indice}`}>
                            <td>{formatearFecha(movimiento.fecha)}</td>
                            <td className="codigo">#{movimiento.numero}</td>
                            <td className="numero debe">
                              {movimiento.debe ? formatearNumero(movimiento.debe) : ''}
                            </td>
                            <td className="numero haber">
                              {movimiento.haber ? formatearNumero(movimiento.haber) : ''}
                            </td>
                            <td className="numero">{formatearNumero(movimiento.saldo)}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr>
                          <td colSpan={2}>Totales</td>
                          <td className="numero">{formatearNumero(item.totalDebe)}</td>
                          <td className="numero">{formatearNumero(item.totalHaber)}</td>
                          <td className="numero">{formatearNumero(item.saldo)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                  <div className="cuenta-t-pie">
                    <span>
                      {item.naturalezaSaldo === 'DEUDOR' ? 'SALDO DEUDOR' : 'SALDO ACREEDOR'}
                    </span>
                    <span>{formatearMoneda(item.saldo, simbolo)}</span>
                  </div>
                </div>
              ))}
            </div>
          </Tarjeta>
        ))
      )}
    </>
  );
}
