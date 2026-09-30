import { useMemo, useState } from 'react';
import { useAlmacen, type BorradorCuenta } from '../almacen/almacen';
import { PLANTILLAS_CUENTAS } from '../datos/plantillasCuentas';
import {
  ETIQUETA_RUBRO,
  ETIQUETA_TIPO,
  TIPOS_CUENTA,
  ordenarCuentas,
  rubroEfectivo,
  rubrosPermitidos,
  validarCuenta,
  type ErroresCuenta,
} from '../dominio/cuentas';
import type { Cuenta, TipoCuenta } from '../dominio/tipos';
import { Aviso, Boton, Campo, EstadoVacio, Modal, Tarjeta } from '../componentes/ui';
import { IconoBasura, IconoDescargar, IconoLapiz, IconoMas } from '../componentes/Iconos';
import { useAvisos } from '../componentes/Avisos';
import { exportarCsv, nombreDeArchivo } from '../servicios/archivos';

const BORRADOR_VACIO: BorradorCuenta = { codigo: '', nombre: '', tipo: 'ACTIVO', rubro: 'CORRIENTE' };

const SIN_CUENTAS: Cuenta[] = [];

export function PlanCuentas() {
  const almacen = useAlmacen();
  const avisos = useAvisos();
  const caso = almacen.casoActivo;

  const [busqueda, setBusqueda] = useState('');
  const [filtroTipo, setFiltroTipo] = useState<'TODOS' | TipoCuenta>('TODOS');
  const [editando, setEditando] = useState<Cuenta | null>(null);
  const [creando, setCreando] = useState(false);
  const [borrador, setBorrador] = useState<BorradorCuenta>(BORRADOR_VACIO);
  const [errores, setErrores] = useState<ErroresCuenta>({});
  const [porEliminar, setPorEliminar] = useState<Cuenta | null>(null);
  const [plantillaElegida, setPlantillaElegida] = useState(PLANTILLAS_CUENTAS[0].id);

  const cuentas = caso?.cuentas ?? SIN_CUENTAS;

  const movimientosPorCuenta = useMemo(() => {
    const conteo = new Map<string, number>();
    for (const asiento of caso?.asientos ?? []) {
      for (const linea of asiento.lineas) {
        conteo.set(linea.cuentaId, (conteo.get(linea.cuentaId) ?? 0) + 1);
      }
    }
    return conteo;
  }, [caso?.asientos]);

  const visibles = useMemo(() => {
    const texto = busqueda.trim().toLowerCase();
    return ordenarCuentas(cuentas).filter((cuenta) => {
      if (filtroTipo !== 'TODOS' && cuenta.tipo !== filtroTipo) return false;
      if (texto === '') return true;
      return (
        cuenta.codigo.toLowerCase().includes(texto) || cuenta.nombre.toLowerCase().includes(texto)
      );
    });
  }, [busqueda, cuentas, filtroTipo]);

  function abrirNueva() {
    setBorrador(BORRADOR_VACIO);
    setErrores({});
    setEditando(null);
    setCreando(true);
  }

  function abrirEdicion(cuenta: Cuenta) {
    setBorrador({
      codigo: cuenta.codigo,
      nombre: cuenta.nombre,
      tipo: cuenta.tipo,
      rubro: rubroEfectivo(cuenta),
    });
    setErrores({});
    setEditando(cuenta);
    setCreando(true);
  }

  function guardar() {
    const encontrados = validarCuenta(borrador, cuentas, editando?.id);
    setErrores(encontrados);
    if (Object.keys(encontrados).length > 0) return;

    if (editando) {
      almacen.actualizarCuenta(editando.id, borrador);
      avisos.exito(`Cuenta ${borrador.codigo} actualizada.`);
    } else {
      almacen.agregarCuenta(borrador);
      avisos.exito(`Cuenta ${borrador.codigo} creada.`);
    }
    setCreando(false);
  }

  function eliminar(cuenta: Cuenta) {
    const resultado = almacen.eliminarCuenta(cuenta.id);
    if (resultado.ok) avisos.exito(resultado.mensaje);
    else avisos.error(resultado.mensaje);
    setPorEliminar(null);
  }

  function agregarPlantilla() {
    const resultado = almacen.agregarPlantillaCuentas(plantillaElegida);
    if (resultado.ok) avisos.exito(resultado.mensaje);
    else avisos.mostrar(resultado.mensaje, 'advertencia');
  }

  function exportar() {
    exportarCsv(nombreDeArchivo(`plan-cuentas-${caso?.nombre ?? ''}`, 'csv'), [
      ['Codigo', 'Nombre', 'Tipo', 'Clasificacion', 'Movimientos'],
      ...ordenarCuentas(cuentas).map((cuenta) => [
        cuenta.codigo,
        cuenta.nombre,
        ETIQUETA_TIPO[cuenta.tipo],
        ETIQUETA_RUBRO[rubroEfectivo(cuenta) ?? 'CORRIENTE'] ?? '',
        movimientosPorCuenta.get(cuenta.id) ?? 0,
      ]),
    ]);
    avisos.exito('Plan de cuentas exportado en CSV.');
  }

  const permitidos = rubrosPermitidos(borrador.tipo);

  return (
    <>
      <Tarjeta
        titulo="Plan de cuentas"
        subtitulo={`${cuentas.length} cuentas en el caso "${caso?.nombre ?? ''}". Debes crear las cuentas antes de registrar asientos.`}
        acciones={
          <>
            <Boton icono={<IconoMas tamano={16} />} onClick={abrirNueva}>
              Nueva cuenta
            </Boton>
            <Boton
              variante="secundario"
              icono={<IconoDescargar tamano={16} />}
              onClick={exportar}
              disabled={cuentas.length === 0}
            >
              Exportar CSV
            </Boton>
          </>
        }
      >
        <div className="filtros">
          <Campo etiqueta="Buscar" htmlFor="buscar-cuenta">
            <input
              id="buscar-cuenta"
              type="text"
              placeholder="Código o nombre"
              value={busqueda}
              onChange={(evento) => setBusqueda(evento.target.value)}
            />
          </Campo>
          <Campo etiqueta="Tipo" htmlFor="filtro-tipo">
            <select
              id="filtro-tipo"
              value={filtroTipo}
              onChange={(evento) => setFiltroTipo(evento.target.value as 'TODOS' | TipoCuenta)}
            >
              <option value="TODOS">Todos los tipos</option>
              {TIPOS_CUENTA.map((tipo) => (
                <option key={tipo} value={tipo}>
                  {ETIQUETA_TIPO[tipo]}
                </option>
              ))}
            </select>
          </Campo>
          <Campo etiqueta="Agregar cuentas de una plantilla" htmlFor="plantilla">
            <select
              id="plantilla"
              value={plantillaElegida}
              onChange={(evento) => setPlantillaElegida(evento.target.value)}
            >
              {PLANTILLAS_CUENTAS.map((plantilla) => (
                <option key={plantilla.id} value={plantilla.id}>
                  {plantilla.nombre}
                </option>
              ))}
            </select>
          </Campo>
          <Boton variante="secundario" onClick={agregarPlantilla}>
            Agregar las que falten
          </Boton>
        </div>
      </Tarjeta>

      <Tarjeta sinEspacio>
        {cuentas.length === 0 ? (
          <EstadoVacio
            titulo="Este caso no tiene cuentas"
            descripcion="Crea las cuentas una por una o agrega una plantilla completa y luego ajústala."
            accion={
              <Boton icono={<IconoMas tamano={16} />} onClick={abrirNueva}>
                Crear la primera cuenta
              </Boton>
            }
          />
        ) : visibles.length === 0 ? (
          <EstadoVacio
            titulo="Ninguna cuenta coincide con la búsqueda"
            descripcion="Prueba con otro código, otro nombre o quita el filtro por tipo."
          />
        ) : (
          <div className="tabla-envoltorio">
            <table className="tabla">
              <thead>
                <tr>
                  <th style={{ width: 110 }}>Código</th>
                  <th>Nombre de la cuenta</th>
                  <th style={{ width: 130 }}>Tipo</th>
                  <th>Clasificación en reportes</th>
                  <th className="numero" style={{ width: 120 }}>
                    Movimientos
                  </th>
                  <th style={{ width: 110 }} />
                </tr>
              </thead>
              <tbody>
                {visibles.map((cuenta) => {
                  const usos = movimientosPorCuenta.get(cuenta.id) ?? 0;
                  const rubro = rubroEfectivo(cuenta);
                  return (
                    <tr key={cuenta.id}>
                      <td className="codigo">{cuenta.codigo}</td>
                      <td>{cuenta.nombre}</td>
                      <td>
                        <span className={`etiqueta ${cuenta.tipo}`}>
                          {ETIQUETA_TIPO[cuenta.tipo]}
                        </span>
                      </td>
                      <td className="atenuado">{rubro ? ETIQUETA_RUBRO[rubro] : '—'}</td>
                      <td className="numero">{usos}</td>
                      <td>
                        <div className="lista-acciones">
                          <Boton
                            chico
                            variante="discreto"
                            title="Editar"
                            aria-label={`Editar ${cuenta.codigo}`}
                            onClick={() => abrirEdicion(cuenta)}
                            icono={<IconoLapiz tamano={15} />}
                          />
                          <Boton
                            chico
                            variante="discreto"
                            title={usos > 0 ? 'Tiene movimientos' : 'Eliminar'}
                            aria-label={`Eliminar ${cuenta.codigo}`}
                            disabled={usos > 0}
                            onClick={() => setPorEliminar(cuenta)}
                            icono={<IconoBasura tamano={15} />}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Tarjeta>

      {creando && (
        <Modal
          titulo={editando ? `Editar cuenta ${editando.codigo}` : 'Nueva cuenta'}
          onCerrar={() => setCreando(false)}
          pie={
            <>
              <Boton variante="secundario" onClick={() => setCreando(false)}>
                Cancelar
              </Boton>
              <Boton onClick={guardar}>{editando ? 'Guardar cambios' : 'Crear cuenta'}</Boton>
            </>
          }
        >
          <div className="fila-campos">
            <Campo etiqueta="Código" error={errores.codigo} htmlFor="codigo-cuenta">
              <input
                id="codigo-cuenta"
                type="text"
                value={borrador.codigo}
                className={errores.codigo ? 'con-error' : ''}
                placeholder="101"
                onChange={(evento) => setBorrador({ ...borrador, codigo: evento.target.value })}
              />
            </Campo>
            <Campo etiqueta="Tipo de cuenta" error={errores.tipo} htmlFor="tipo-cuenta">
              <select
                id="tipo-cuenta"
                value={borrador.tipo}
                onChange={(evento) => {
                  const tipo = evento.target.value as TipoCuenta;
                  setBorrador({ ...borrador, tipo, rubro: rubrosPermitidos(tipo)[0] });
                }}
              >
                {TIPOS_CUENTA.map((tipo) => (
                  <option key={tipo} value={tipo}>
                    {ETIQUETA_TIPO[tipo]}
                  </option>
                ))}
              </select>
            </Campo>
          </div>

          <Campo etiqueta="Nombre de la cuenta" error={errores.nombre} htmlFor="nombre-cuenta">
            <input
              id="nombre-cuenta"
              type="text"
              value={borrador.nombre}
              className={errores.nombre ? 'con-error' : ''}
              placeholder="Caja"
              onChange={(evento) => setBorrador({ ...borrador, nombre: evento.target.value })}
            />
          </Campo>

          {permitidos.length > 0 && (
            <Campo
              etiqueta="Clasificación en los reportes"
              ayuda={
                borrador.tipo === 'ACTIVO' || borrador.tipo === 'PASIVO'
                  ? 'Define dónde aparece en el Balance General.'
                  : 'Define en qué línea del Estado de Resultados se suma.'
              }
              htmlFor="rubro-cuenta"
            >
              <select
                id="rubro-cuenta"
                value={borrador.rubro ?? permitidos[0]}
                onChange={(evento) =>
                  setBorrador({ ...borrador, rubro: evento.target.value as Cuenta['rubro'] })
                }
              >
                {permitidos.map((rubro) => (
                  <option key={rubro} value={rubro}>
                    {ETIQUETA_RUBRO[rubro]}
                  </option>
                ))}
              </select>
            </Campo>
          )}

          <Aviso tipo="info">
            Las cuentas de <strong>activo</strong> y <strong>gasto</strong> aumentan por el Debe. Las
            de <strong>pasivo</strong>, <strong>patrimonio</strong> e <strong>ingreso</strong>{' '}
            aumentan por el Haber.
          </Aviso>
        </Modal>
      )}

      {porEliminar && (
        <Modal
          titulo="Eliminar cuenta"
          onCerrar={() => setPorEliminar(null)}
          pie={
            <>
              <Boton variante="secundario" onClick={() => setPorEliminar(null)}>
                Cancelar
              </Boton>
              <Boton variante="peligro" onClick={() => eliminar(porEliminar)}>
                Eliminar
              </Boton>
            </>
          }
        >
          <Aviso tipo="advertencia">
            Se eliminará la cuenta <strong>{porEliminar.codigo}</strong> — {porEliminar.nombre}.
          </Aviso>
        </Modal>
      )}
    </>
  );
}
