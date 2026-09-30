import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAlmacen } from '../almacen/almacen';
import { useAvisos } from '../componentes/Avisos';
import { Aviso, Boton, Campo, EstadoVacio, Tarjeta } from '../componentes/ui';
import { IconoBasura, IconoCheck, IconoMas } from '../componentes/Iconos';
import {
  ETIQUETA_TIPO,
  esNaturalezaDeudora,
  indicePorId,
  movimientoDesdeSigno,
  ordenarCuentas,
} from '../dominio/cuentas';
import { hayErrores, resumirAsiento, validarAsiento, type ErroresAsiento } from '../dominio/asientos';
import { aNumero, esCero, redondear } from '../dominio/numeros';
import { formatearMoneda, hoyISO } from '../dominio/formato';
import { nuevoId } from '../dominio/ids';
import type { LineaAsiento } from '../dominio/tipos';

interface LineaFormulario {
  id: string;
  cuentaId: string;
  debe: string;
  haber: string;
}

type Modo = 'debe-haber' | 'signo';

function lineaVacia(): LineaFormulario {
  return { id: nuevoId('lin'), cuentaId: '', debe: '', haber: '' };
}

function aLineas(lineas: LineaFormulario[]): LineaAsiento[] {
  return lineas.map((linea) => ({
    id: linea.id,
    cuentaId: linea.cuentaId,
    debe: aNumero(linea.debe),
    haber: aNumero(linea.haber),
  }));
}

export function RegistrarAsiento() {
  const almacen = useAlmacen();
  const avisos = useAvisos();
  const navegar = useNavigate();
  const { id } = useParams();
  const caso = almacen.casoActivo;

  const asientoEnEdicion = useMemo(
    () => caso?.asientos.find((asiento) => asiento.id === id) ?? null,
    [caso?.asientos, id],
  );

  const [modo, setModo] = useState<Modo>('debe-haber');
  const [fecha, setFecha] = useState(hoyISO());
  const [glosa, setGlosa] = useState('');
  const [lineas, setLineas] = useState<LineaFormulario[]>([lineaVacia(), lineaVacia()]);
  const [errores, setErrores] = useState<ErroresAsiento>({ porLinea: {} });
  const [guardando, setGuardando] = useState(false);
  const [tocado, setTocado] = useState(false);

  useEffect(() => {
    if (asientoEnEdicion) {
      setFecha(asientoEnEdicion.fecha);
      setGlosa(asientoEnEdicion.glosa);
      setLineas(
        asientoEnEdicion.lineas.map((linea) => ({
          id: linea.id,
          cuentaId: linea.cuentaId,
          debe: esCero(linea.debe) ? '' : String(linea.debe),
          haber: esCero(linea.haber) ? '' : String(linea.haber),
        })),
      );
      setErrores({ porLinea: {} });
      setTocado(false);
    }
  }, [asientoEnEdicion]);

  useEffect(() => {
    if (id && caso && !asientoEnEdicion) navegar('/asientos', { replace: true });
  }, [asientoEnEdicion, caso, id, navegar]);

  const cuentas = useMemo(() => ordenarCuentas(caso?.cuentas ?? []), [caso?.cuentas]);
  const porId = useMemo(() => indicePorId(cuentas), [cuentas]);
  const resumen = resumirAsiento(aLineas(lineas));

  function actualizarLinea(idLinea: string, cambios: Partial<LineaFormulario>) {
    setTocado(true);
    setLineas((actuales) =>
      actuales.map((linea) => (linea.id === idLinea ? { ...linea, ...cambios } : linea)),
    );
  }

  function cambiarImporte(idLinea: string, columna: 'debe' | 'haber', valor: string) {
    // Un importe va en el Debe o en el Haber, nunca en los dos a la vez.
    actualizarLinea(idLinea, {
      [columna]: valor,
      [columna === 'debe' ? 'haber' : 'debe']: '',
    } as Partial<LineaFormulario>);
  }

  function cambiarPorSigno(idLinea: string, signo: '+' | '-', montoTexto: string) {
    const linea = lineas.find((item) => item.id === idLinea);
    if (!linea) return;
    const cuenta = porId.get(linea.cuentaId);
    if (!cuenta) {
      actualizarLinea(idLinea, { debe: montoTexto, haber: '' });
      return;
    }
    const monto = aNumero(montoTexto);
    const movimiento = movimientoDesdeSigno(cuenta.tipo, signo, monto);
    actualizarLinea(idLinea, {
      debe: esCero(movimiento.debe) ? '' : montoTexto,
      haber: esCero(movimiento.haber) ? '' : montoTexto,
    });
  }

  function signoDeLinea(linea: LineaFormulario): '+' | '-' {
    const cuenta = porId.get(linea.cuentaId);
    const enDebe = !esCero(aNumero(linea.debe));
    const enHaber = !esCero(aNumero(linea.haber));
    if (!cuenta || (!enDebe && !enHaber)) return '+';
    const deudora = esNaturalezaDeudora(cuenta.tipo);
    if (enDebe) return deudora ? '+' : '-';
    return deudora ? '-' : '+';
  }

  function montoDeLinea(linea: LineaFormulario): string {
    return linea.debe !== '' ? linea.debe : linea.haber;
  }

  function agregarLinea() {
    setLineas((actuales) => [...actuales, lineaVacia()]);
  }

  function quitarLinea(idLinea: string) {
    setLineas((actuales) =>
      actuales.length <= 2 ? actuales : actuales.filter((linea) => linea.id !== idLinea),
    );
    setTocado(true);
  }

  function limpiar() {
    setFecha(asientoEnEdicion?.fecha ?? hoyISO());
    setGlosa('');
    setLineas([lineaVacia(), lineaVacia()]);
    setErrores({ porLinea: {} });
    setTocado(false);
  }

  function guardar() {
    const encontrados = validarAsiento(
      { fecha, glosa, lineas: aLineas(lineas) },
      caso?.cuentas ?? [],
    );
    setErrores(encontrados);
    setTocado(true);
    if (hayErrores(encontrados)) {
      avisos.error('Revisa el asiento: hay datos por corregir.');
      return;
    }

    setGuardando(true);
    // Pequeña espera para que el usuario vea el estado de guardado.
    window.setTimeout(() => {
      const resultado = almacen.guardarAsiento({
        id: asientoEnEdicion?.id,
        fecha,
        glosa,
        lineas: aLineas(lineas),
      });
      setGuardando(false);
      if (!resultado.ok) {
        avisos.error(resultado.mensaje);
        return;
      }
      avisos.exito(resultado.mensaje);
      if (asientoEnEdicion) navegar('/libro-diario');
      else limpiar();
    }, 180);
  }

  if (cuentas.length === 0) {
    return (
      <Tarjeta>
        <EstadoVacio
          titulo="Primero necesitas cuentas"
          descripcion="Un asiento se arma con cuentas del plan de cuentas. Crea al menos dos antes de registrar movimientos."
          accion={
            <Link to="/plan-de-cuentas">
              <Boton>Ir al Plan de Cuentas</Boton>
            </Link>
          }
        />
      </Tarjeta>
    );
  }

  const simbolo = caso?.empresa.simboloMoneda ?? 'S/';
  const mostrarErrores = tocado;

  return (
    <>
      <Tarjeta
        titulo={asientoEnEdicion ? `Editar asiento #${asientoEnEdicion.numero}` : 'Registrar asiento contable'}
        subtitulo="El asiento solo se guarda si el total del Debe iguala al total del Haber."
        acciones={
          <div className="lista-acciones">
            <Boton
              chico
              variante={modo === 'debe-haber' ? 'primario' : 'secundario'}
              onClick={() => setModo('debe-haber')}
            >
              Modo Debe / Haber
            </Boton>
            <Boton
              chico
              variante={modo === 'signo' ? 'primario' : 'secundario'}
              onClick={() => setModo('signo')}
            >
              Modo signo (+ / −)
            </Boton>
          </div>
        }
      >
        <div className="fila-campos">
          <Campo etiqueta="Fecha" error={mostrarErrores ? errores.fecha : undefined} htmlFor="fecha">
            <input
              id="fecha"
              type="date"
              value={fecha}
              className={mostrarErrores && errores.fecha ? 'con-error' : ''}
              onChange={(evento) => {
                setFecha(evento.target.value);
                setTocado(true);
              }}
            />
          </Campo>
          <div style={{ gridColumn: 'span 2' }}>
            <Campo
              etiqueta="Glosa o descripción"
              error={mostrarErrores ? errores.glosa : undefined}
              ayuda="Ejemplo: compra de mercadería al crédito."
              htmlFor="glosa"
            >
              <input
                id="glosa"
                type="text"
                value={glosa}
                maxLength={140}
                onChange={(evento) => {
                  setGlosa(evento.target.value);
                  setTocado(true);
                }}
              />
            </Campo>
          </div>
        </div>

        {modo === 'signo' && (
          <div style={{ marginTop: 14 }}>
            <Aviso tipo="info">
              En el modo signo, <strong>+</strong> aumenta la cuenta y <strong>−</strong> la
              disminuye. El sistema decide solo si el movimiento va al Debe o al Haber según el tipo
              de cuenta.
            </Aviso>
          </div>
        )}
      </Tarjeta>

      <Tarjeta
        titulo="Movimientos del asiento"
        acciones={
          <Boton chico variante="secundario" icono={<IconoMas tamano={15} />} onClick={agregarLinea}>
            Agregar línea
          </Boton>
        }
        sinEspacio
      >
        <div className="tabla-envoltorio">
          <table className="tabla">
            <thead>
              <tr>
                <th style={{ minWidth: 260 }}>Cuenta</th>
                <th style={{ width: 110 }}>Tipo</th>
                {modo === 'debe-haber' ? (
                  <>
                    <th className="numero" style={{ width: 150 }}>
                      Debe
                    </th>
                    <th className="numero" style={{ width: 150 }}>
                      Haber
                    </th>
                  </>
                ) : (
                  <>
                    <th style={{ width: 130 }}>Signo</th>
                    <th className="numero" style={{ width: 150 }}>
                      Monto
                    </th>
                  </>
                )}
                <th style={{ width: 52 }} />
              </tr>
            </thead>
            <tbody>
              {lineas.map((linea) => {
                const cuenta = porId.get(linea.cuentaId);
                const error = mostrarErrores ? errores.porLinea[linea.id] : undefined;
                return (
                  <tr key={linea.id}>
                    <td>
                      <select
                        aria-label="Cuenta"
                        value={linea.cuentaId}
                        className={error ? 'con-error' : ''}
                        onChange={(evento) =>
                          actualizarLinea(linea.id, { cuentaId: evento.target.value })
                        }
                      >
                        <option value="">Selecciona una cuenta…</option>
                        {cuentas.map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.codigo} — {item.nombre}
                          </option>
                        ))}
                      </select>
                      {error && <span className="error">{error}</span>}
                    </td>
                    <td>
                      {cuenta ? (
                        <span className={`etiqueta ${cuenta.tipo}`}>{ETIQUETA_TIPO[cuenta.tipo]}</span>
                      ) : (
                        <span className="atenuado">—</span>
                      )}
                    </td>
                    {modo === 'debe-haber' ? (
                      <>
                        <td>
                          <input
                            aria-label="Importe al Debe"
                            type="number"
                            min={0}
                            step="0.01"
                            value={linea.debe}
                            onChange={(evento) =>
                              cambiarImporte(linea.id, 'debe', evento.target.value)
                            }
                          />
                        </td>
                        <td>
                          <input
                            aria-label="Importe al Haber"
                            type="number"
                            min={0}
                            step="0.01"
                            value={linea.haber}
                            onChange={(evento) =>
                              cambiarImporte(linea.id, 'haber', evento.target.value)
                            }
                          />
                        </td>
                      </>
                    ) : (
                      <>
                        <td>
                          <div className="lista-acciones">
                            <Boton
                              chico
                              variante={signoDeLinea(linea) === '+' ? 'primario' : 'secundario'}
                              aria-label="Aumenta la cuenta"
                              onClick={() => cambiarPorSigno(linea.id, '+', montoDeLinea(linea))}
                            >
                              +
                            </Boton>
                            <Boton
                              chico
                              variante={signoDeLinea(linea) === '-' ? 'peligro' : 'secundario'}
                              aria-label="Disminuye la cuenta"
                              onClick={() => cambiarPorSigno(linea.id, '-', montoDeLinea(linea))}
                            >
                              −
                            </Boton>
                          </div>
                        </td>
                        <td>
                          <input
                            aria-label="Monto"
                            type="number"
                            min={0}
                            step="0.01"
                            value={montoDeLinea(linea)}
                            onChange={(evento) =>
                              cambiarPorSigno(linea.id, signoDeLinea(linea), evento.target.value)
                            }
                          />
                        </td>
                      </>
                    )}
                    <td>
                      <Boton
                        chico
                        variante="discreto"
                        aria-label="Quitar línea"
                        title={lineas.length <= 2 ? 'Un asiento necesita dos líneas' : 'Quitar línea'}
                        disabled={lineas.length <= 2}
                        onClick={() => quitarLinea(linea.id)}
                        icono={<IconoBasura tamano={15} />}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={2}>Totales</td>
                {modo === 'debe-haber' ? (
                  <>
                    <td className="numero debe">{formatearMoneda(resumen.totalDebe, simbolo)}</td>
                    <td className="numero haber">{formatearMoneda(resumen.totalHaber, simbolo)}</td>
                  </>
                ) : (
                  <>
                    <td className="atenuado">
                      Debe {formatearMoneda(resumen.totalDebe, simbolo)}
                    </td>
                    <td className="numero">{formatearMoneda(resumen.totalHaber, simbolo)}</td>
                  </>
                )}
                <td />
              </tr>
            </tfoot>
          </table>
        </div>
      </Tarjeta>

      <Tarjeta>
        <div
          style={{
            display: 'flex',
            gap: 14,
            alignItems: 'center',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
          }}
        >
          <div className={`marca-cuadre ${resumen.cuadrado ? 'ok' : 'mal'}`}>
            <IconoCheck tamano={18} />
            {resumen.cuadrado ? (
              <span>El asiento cuadra: Debe = Haber = {formatearMoneda(resumen.totalDebe, simbolo)}</span>
            ) : (
              <span>
                Diferencia de {formatearMoneda(Math.abs(resumen.diferencia), simbolo)} entre Debe y
                Haber
              </span>
            )}
          </div>
          <div className="lista-acciones">
            <Boton variante="secundario" onClick={limpiar}>
              Limpiar
            </Boton>
            {asientoEnEdicion && (
              <Boton variante="secundario" onClick={() => navegar('/libro-diario')}>
                Cancelar edición
              </Boton>
            )}
            <Boton onClick={guardar} cargando={guardando} icono={<IconoCheck tamano={16} />}>
              {asientoEnEdicion ? 'Guardar cambios' : 'Registrar asiento'}
            </Boton>
          </div>
        </div>

        {mostrarErrores && (errores.cuadre || errores.lineas) && (
          <div style={{ marginTop: 14 }}>
            <Aviso tipo="error">{errores.cuadre ?? errores.lineas}</Aviso>
          </div>
        )}

        {redondear(resumen.totalDebe) > 0 && resumen.cuadrado && !mostrarErrores && (
          <div style={{ marginTop: 14 }}>
            <Aviso tipo="exito">Listo para registrar.</Aviso>
          </div>
        )}
      </Tarjeta>
    </>
  );
}
