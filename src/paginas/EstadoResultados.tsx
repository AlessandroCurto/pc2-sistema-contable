import { Fragment, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useAlmacen } from '../almacen/almacen';
import { useAvisos } from '../componentes/Avisos';
import { CabeceraReporte } from '../componentes/CabeceraReporte';
import { Aviso, Boton, EstadoVacio, Indicador, Tarjeta } from '../componentes/ui';
import { IconoDescargar, IconoMas } from '../componentes/Iconos';
import { construirEstadoResultados } from '../dominio/estadoResultados';
import { formatearMoneda, formatearNumero } from '../dominio/formato';
import { esCero } from '../dominio/numeros';
import { exportarCsv, nombreDeArchivo } from '../servicios/archivos';

export function EstadoResultados() {
  const almacen = useAlmacen();
  const avisos = useAvisos();
  const caso = almacen.casoActivo;
  const estado = useMemo(() => (caso ? construirEstadoResultados(caso) : null), [caso]);

  if (!caso || !estado) return null;
  const simbolo = caso.empresa.simboloMoneda;

  const seccionesConDatos = Object.values(estado.secciones).filter(
    (seccion) => seccion.cuentas.length > 0,
  );
  const sinDatos = seccionesConDatos.length === 0;

  function exportar() {
    if (!estado) return;
    exportarCsv(nombreDeArchivo(`estado-resultados-${caso?.nombre ?? ''}`, 'csv'), [
      ['Concepto', `Importe (${caso?.empresa.simboloMoneda ?? ''})`],
      ...estado.filas.map((fila) => [
        `${fila.signo === '-' ? '(-) ' : ''}${fila.etiqueta}`,
        formatearNumero(fila.monto),
      ]),
    ]);
    avisos.exito('Estado de resultados exportado en CSV.');
  }

  return (
    <>
      <CabeceraReporte
        caso={caso}
        titulo="Estado de Resultados"
        acciones={
          <Boton
            variante="secundario"
            icono={<IconoDescargar tamano={16} />}
            onClick={exportar}
            disabled={sinDatos}
          >
            CSV
          </Boton>
        }
      />

      {sinDatos ? (
        <Tarjeta>
          <EstadoVacio
            titulo="No hay ingresos ni gastos registrados"
            descripcion="El estado de resultados usa las cuentas de tipo Ingreso y Gasto. Registra asientos que las muevan."
            accion={
              <Link to="/asientos">
                <Boton icono={<IconoMas tamano={16} />}>Registrar asiento</Boton>
              </Link>
            }
          />
        </Tarjeta>
      ) : (
        <>
          <div className="rejilla rejilla-4">
            <Indicador
              etiqueta="Ventas netas"
              valor={formatearMoneda(estado.ventasNetas, simbolo)}
            />
            <Indicador
              etiqueta="Utilidad bruta"
              valor={formatearMoneda(estado.utilidadBruta, simbolo)}
            />
            <Indicador
              etiqueta="Utilidad operativa"
              valor={formatearMoneda(estado.utilidadOperativa, simbolo)}
            />
            <Indicador
              etiqueta="Utilidad neta"
              valor={formatearMoneda(estado.utilidadNeta, simbolo)}
              color={estado.utilidadNeta >= 0 ? 'var(--verde-600)' : 'var(--rojo-600)'}
              pie={estado.utilidadNeta >= 0 ? 'Resultado positivo' : 'Pérdida del período'}
            />
          </div>

          <Tarjeta titulo="Estado de resultados por naturaleza" sinEspacio>
            <div className="tabla-envoltorio">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Concepto</th>
                    <th className="numero" style={{ width: 220 }}>
                      Importe ({simbolo})
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {estado.filas.map((fila) => {
                    if (fila.clase === 'detalle' && esCero(fila.monto)) return null;
                    const clase =
                      fila.clase === 'total'
                        ? 'fila-total'
                        : fila.clase === 'subtotal'
                          ? 'fila-subtotal'
                          : '';
                    return (
                      <tr key={fila.clave} className={clase}>
                        <td>
                          {fila.signo === '-' ? '(-) ' : ''}
                          {fila.etiqueta}
                        </td>
                        <td
                          className="numero"
                          style={fila.signo === '-' ? { color: 'var(--rojo-600)' } : undefined}
                        >
                          {fila.signo === '-' && !esCero(fila.monto)
                            ? `(${formatearNumero(fila.monto)})`
                            : formatearNumero(fila.monto)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Tarjeta>

          <Tarjeta
            titulo="Detalle por cuenta"
            subtitulo="Cada cuenta aparece en la línea que le corresponde según su clasificación."
            sinEspacio
          >
            <div className="tabla-envoltorio">
              <table className="tabla">
                <thead>
                  <tr>
                    <th style={{ width: 110 }}>Código</th>
                    <th>Cuenta</th>
                    <th className="numero" style={{ width: 200 }}>
                      Importe
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {seccionesConDatos.map((seccion) => (
                    <Fragment key={seccion.rubro}>
                      <tr className="fila-cabecera-grupo">
                        <td colSpan={3}>{seccion.etiqueta.toUpperCase()}</td>
                      </tr>
                      {seccion.cuentas.map((detalle) => (
                        <tr key={detalle.cuenta.id}>
                          <td className="codigo">{detalle.cuenta.codigo}</td>
                          <td>{detalle.cuenta.nombre}</td>
                          <td className="numero">{formatearNumero(detalle.monto)}</td>
                        </tr>
                      ))}
                      <tr className="fila-subtotal">
                        <td colSpan={2}>Total {seccion.etiqueta.toLowerCase()}</td>
                        <td className="numero">{formatearNumero(seccion.total)}</td>
                      </tr>
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </Tarjeta>

          <Aviso tipo="info">
            El impuesto a la renta se calcula con la tasa del caso ({estado.tasaImpuesto}%) sobre el
            resultado antes de impuestos, solo cuando este es positivo. Es un cálculo del reporte: no
            se registra como asiento. Puedes cambiar la tasa en Configuración.
          </Aviso>
        </>
      )}
    </>
  );
}
