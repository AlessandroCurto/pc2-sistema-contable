import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAlmacen } from '../almacen/almacen';
import { useAvisos } from '../componentes/Avisos';
import { CabeceraReporte } from '../componentes/CabeceraReporte';
import { Aviso, Boton, Campo, EstadoVacio, MarcaCuadre, Modal, Tarjeta } from '../componentes/ui';
import { IconoBasura, IconoDescargar, IconoLapiz, IconoMas } from '../componentes/Iconos';
import { construirLibroDiario, type FiltroDiario } from '../dominio/libroDiario';
import { ETIQUETA_TIPO, ordenarCuentas } from '../dominio/cuentas';
import { formatearFecha, formatearMoneda, formatearNumero } from '../dominio/formato';
import { sonIguales } from '../dominio/numeros';
import { exportarCsv, nombreDeArchivo } from '../servicios/archivos';

export function LibroDiario() {
  const almacen = useAlmacen();
  const avisos = useAvisos();
  const navegar = useNavigate();
  const caso = almacen.casoActivo;
  const [filtro, setFiltro] = useState<FiltroDiario>({});
  const [porEliminar, setPorEliminar] = useState<string | null>(null);

  const cuentas = useMemo(() => ordenarCuentas(caso?.cuentas ?? []), [caso?.cuentas]);
  const diario = useMemo(
    () => (caso ? construirLibroDiario(caso, filtro) : null),
    [caso, filtro],
  );

  if (!caso || !diario) return null;
  const simbolo = caso.empresa.simboloMoneda;
  const hayFiltro = Boolean(filtro.desde || filtro.hasta || filtro.cuentaId || filtro.texto);

  function exportar() {
    if (!diario) return;
    exportarCsv(nombreDeArchivo(`libro-diario-${caso?.nombre ?? ''}`, 'csv'), [
      ['N', 'Fecha', 'Glosa', 'Codigo', 'Cuenta', 'Grupo', 'Debe', 'Haber'],
      ...diario.filas.map((fila) => [
        fila.numero,
        fila.fecha,
        fila.glosa,
        fila.cuenta?.codigo ?? '',
        fila.cuenta?.nombre ?? '',
        fila.tipo ? ETIQUETA_TIPO[fila.tipo] : '',
        fila.debe ? formatearNumero(fila.debe) : '',
        fila.haber ? formatearNumero(fila.haber) : '',
      ]),
    ]);
    avisos.exito('Libro diario exportado en CSV.');
  }

  const asientoAEliminar = caso.asientos.find((asiento) => asiento.id === porEliminar) ?? null;

  return (
    <>
      <CabeceraReporte
        caso={caso}
        titulo="Libro Diario"
        acciones={
          <>
            <Boton
              variante="secundario"
              icono={<IconoMas tamano={16} />}
              onClick={() => navegar('/asientos')}
            >
              Nuevo asiento
            </Boton>
            <Boton
              variante="secundario"
              icono={<IconoDescargar tamano={16} />}
              onClick={exportar}
              disabled={diario.filas.length === 0}
            >
              CSV
            </Boton>
          </>
        }
      />

      <Tarjeta className="no-imprimir">
        <div className="filtros">
          <Campo etiqueta="Desde" htmlFor="desde">
            <input
              id="desde"
              type="date"
              value={filtro.desde ?? ''}
              onChange={(evento) => setFiltro({ ...filtro, desde: evento.target.value })}
            />
          </Campo>
          <Campo etiqueta="Hasta" htmlFor="hasta">
            <input
              id="hasta"
              type="date"
              value={filtro.hasta ?? ''}
              onChange={(evento) => setFiltro({ ...filtro, hasta: evento.target.value })}
            />
          </Campo>
          <Campo etiqueta="Cuenta" htmlFor="cuenta">
            <select
              id="cuenta"
              value={filtro.cuentaId ?? ''}
              onChange={(evento) => setFiltro({ ...filtro, cuentaId: evento.target.value })}
            >
              <option value="">Todas las cuentas</option>
              {cuentas.map((cuenta) => (
                <option key={cuenta.id} value={cuenta.id}>
                  {cuenta.codigo} — {cuenta.nombre}
                </option>
              ))}
            </select>
          </Campo>
          <Campo etiqueta="Buscar en glosa" htmlFor="texto">
            <input
              id="texto"
              type="text"
              placeholder="Texto o número de asiento"
              value={filtro.texto ?? ''}
              onChange={(evento) => setFiltro({ ...filtro, texto: evento.target.value })}
            />
          </Campo>
          <Boton variante="secundario" disabled={!hayFiltro} onClick={() => setFiltro({})}>
            Quitar filtros
          </Boton>
        </div>
      </Tarjeta>

      {caso.asientos.length === 0 ? (
        <Tarjeta>
          <EstadoVacio
            titulo="Todavía no hay asientos"
            descripcion="Registra el primer asiento del caso y aparecerá aquí en orden cronológico."
            accion={
              <Link to="/asientos">
                <Boton icono={<IconoMas tamano={16} />}>Registrar asiento</Boton>
              </Link>
            }
          />
        </Tarjeta>
      ) : diario.asientos.length === 0 ? (
        <Tarjeta>
          <EstadoVacio
            titulo="Ningún asiento coincide con los filtros"
            descripcion="Cambia el rango de fechas, la cuenta o el texto buscado."
            accion={
              <Boton variante="secundario" onClick={() => setFiltro({})}>
                Quitar filtros
              </Boton>
            }
          />
        </Tarjeta>
      ) : (
        <>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
            <MarcaCuadre
              cuadrado={sonIguales(diario.totalDebe, diario.totalHaber)}
              textoOk={`Los ${diario.asientos.length} asientos mostrados cuadran en ${formatearMoneda(diario.totalDebe, simbolo)}.`}
              textoMal="Hay asientos descuadrados en el libro diario."
            />
          </div>

          {diario.asientos.map((item) => (
            <Tarjeta
              key={item.asiento.id}
              titulo={`Asiento #${item.asiento.numero}`}
              subtitulo={`${formatearFecha(item.asiento.fecha)}${item.asiento.glosa ? ` · ${item.asiento.glosa}` : ''}`}
              acciones={
                <>
                  <Boton
                    chico
                    variante="secundario"
                    icono={<IconoLapiz tamano={15} />}
                    onClick={() => navegar(`/asientos/${item.asiento.id}`)}
                  >
                    Editar
                  </Boton>
                  <Boton
                    chico
                    variante="secundario"
                    icono={<IconoBasura tamano={15} />}
                    onClick={() => setPorEliminar(item.asiento.id)}
                  >
                    Eliminar
                  </Boton>
                </>
              }
              sinEspacio
            >
              <div className="tabla-envoltorio">
                <table className="tabla">
                  <thead>
                    <tr>
                      <th style={{ width: 110 }}>Código</th>
                      <th>Cuenta</th>
                      <th style={{ width: 130 }}>Grupo</th>
                      <th className="numero" style={{ width: 160 }}>
                        Debe
                      </th>
                      <th className="numero" style={{ width: 160 }}>
                        Haber
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {item.filas.map((fila, indice) => (
                      <tr key={`${item.asiento.id}-${indice}`}>
                        <td className="codigo">{fila.cuenta?.codigo ?? '—'}</td>
                        <td>{fila.cuenta?.nombre ?? 'Cuenta eliminada'}</td>
                        <td>
                          {fila.tipo ? (
                            <span className={`etiqueta ${fila.tipo}`}>{ETIQUETA_TIPO[fila.tipo]}</span>
                          ) : (
                            <span className="atenuado">—</span>
                          )}
                        </td>
                        <td className="numero debe">
                          {fila.debe ? formatearMoneda(fila.debe, simbolo) : ''}
                        </td>
                        <td className="numero haber">
                          {fila.haber ? formatearMoneda(fila.haber, simbolo) : ''}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td colSpan={3}>Totales del asiento</td>
                      <td className="numero">{formatearMoneda(item.totalDebe, simbolo)}</td>
                      <td className="numero">{formatearMoneda(item.totalHaber, simbolo)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
              {!item.cuadrado && (
                <div style={{ padding: 14 }}>
                  <Aviso tipo="error">Este asiento no cuadra. Edítalo para corregirlo.</Aviso>
                </div>
              )}
            </Tarjeta>
          ))}

          <Tarjeta titulo="Resumen del libro diario">
            <div className="tabla-envoltorio">
              <table className="tabla">
                <tbody>
                  <tr className="fila-total">
                    <td>Asientos mostrados</td>
                    <td className="numero">{diario.asientos.length}</td>
                  </tr>
                  <tr className="fila-total">
                    <td>Total Debe</td>
                    <td className="numero">{formatearMoneda(diario.totalDebe, simbolo)}</td>
                  </tr>
                  <tr className="fila-total">
                    <td>Total Haber</td>
                    <td className="numero">{formatearMoneda(diario.totalHaber, simbolo)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </Tarjeta>
        </>
      )}

      {asientoAEliminar && (
        <Modal
          titulo={`Eliminar asiento #${asientoAEliminar.numero}`}
          onCerrar={() => setPorEliminar(null)}
          pie={
            <>
              <Boton variante="secundario" onClick={() => setPorEliminar(null)}>
                Cancelar
              </Boton>
              <Boton
                variante="peligro"
                onClick={() => {
                  almacen.eliminarAsiento(asientoAEliminar.id);
                  setPorEliminar(null);
                  avisos.mostrar('Asiento eliminado. Los correlativos se reordenaron.', 'advertencia');
                }}
              >
                Eliminar
              </Boton>
            </>
          }
        >
          <Aviso tipo="advertencia">
            Se eliminará el asiento del {formatearFecha(asientoAEliminar.fecha)}
            {asientoAEliminar.glosa ? ` (${asientoAEliminar.glosa})` : ''} y todos sus movimientos.
          </Aviso>
        </Modal>
      )}
    </>
  );
}
