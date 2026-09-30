import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAlmacen, type BorradorCaso } from '../almacen/almacen';
import { EMPRESA_POR_DEFECTO } from '../almacen/persistencia';
import { PLANTILLAS_CASO } from '../datos/casosDemo';
import { PLANTILLAS_CUENTAS } from '../datos/plantillasCuentas';
import { formatearFecha, formatearMoneda } from '../dominio/formato';
import { construirBalanceComprobacion } from '../dominio/balanceComprobacion';
import { Aviso, Boton, Campo, EstadoVacio, Modal, Tarjeta } from '../componentes/ui';
import {
  IconoBasura,
  IconoCasos,
  IconoCopiar,
  IconoDescargar,
  IconoMas,
  IconoSubir,
} from '../componentes/Iconos';
import { useAvisos } from '../componentes/Avisos';
import { exportarCasoJson, leerArchivoJson } from '../servicios/archivos';

const BORRADOR_INICIAL: BorradorCaso = {
  nombre: '',
  plantillaCuentas: 'numerado',
  empresa: {
    nombre: '',
    ruc: '',
    simboloMoneda: 'S/',
    periodoInicio: '',
    periodoFin: '',
    tasaImpuestoRenta: EMPRESA_POR_DEFECTO.tasaImpuestoRenta,
  },
};

export function Casos() {
  const almacen = useAlmacen();
  const avisos = useAvisos();
  const navegar = useNavigate();
  const entradaArchivo = useRef<HTMLInputElement>(null);

  const [creando, setCreando] = useState(false);
  const [borrador, setBorrador] = useState<BorradorCaso>(BORRADOR_INICIAL);
  const [errorNombre, setErrorNombre] = useState('');
  const [porEliminar, setPorEliminar] = useState<string | null>(null);
  const [importando, setImportando] = useState(false);

  function abrirFormulario() {
    setBorrador(BORRADOR_INICIAL);
    setErrorNombre('');
    setCreando(true);
  }

  function guardarCaso() {
    const nombre = borrador.nombre.trim();
    if (nombre === '') {
      setErrorNombre('Escribe el nombre del caso o de la empresa.');
      return;
    }
    almacen.crearCaso({
      ...borrador,
      nombre,
      empresa: { ...borrador.empresa, nombre: borrador.empresa.nombre?.trim() || nombre },
    });
    setCreando(false);
    avisos.exito(`Caso "${nombre}" creado y abierto.`);
    navegar('/plan-de-cuentas');
  }

  function cargarDemo(id: string) {
    const creado = almacen.cargarCasoDemo(id);
    if (!creado) {
      avisos.error('No se encontró ese caso de ejemplo.');
      return;
    }
    avisos.exito('Caso de ejemplo cargado y abierto.');
    navegar('/libro-diario');
  }

  async function importar(archivo: File) {
    setImportando(true);
    try {
      const datos = await leerArchivoJson(archivo);
      const resultado = almacen.importarCaso(datos);
      if (resultado.ok) avisos.exito(resultado.mensaje);
      else avisos.error(resultado.mensaje);
    } catch (error) {
      avisos.error(error instanceof Error ? error.message : 'No se pudo importar el archivo.');
    } finally {
      setImportando(false);
      if (entradaArchivo.current) entradaArchivo.current.value = '';
    }
  }

  const casoAEliminar = almacen.casos.find((caso) => caso.id === porEliminar) ?? null;

  return (
    <>
      <Tarjeta
        titulo="Casos contables"
        subtitulo="Cada caso guarda su propia empresa, plan de cuentas y asientos."
        acciones={
          <>
            <Boton icono={<IconoMas tamano={16} />} onClick={abrirFormulario}>
              Nuevo caso
            </Boton>
            <Boton
              variante="secundario"
              icono={<IconoSubir tamano={16} />}
              cargando={importando}
              onClick={() => entradaArchivo.current?.click()}
            >
              Importar JSON
            </Boton>
            <input
              ref={entradaArchivo}
              type="file"
              accept="application/json,.json"
              style={{ display: 'none' }}
              onChange={(evento) => {
                const archivo = evento.target.files?.[0];
                if (archivo) void importar(archivo);
              }}
            />
          </>
        }
        sinEspacio
      >
        {almacen.casos.length === 0 ? (
          <EstadoVacio
            titulo="Todavía no hay casos"
            descripcion="Crea un caso vacío para cargar el enunciado que te den, o abre uno de los casos de ejemplo para ver el sistema funcionando."
            accion={
              <Boton icono={<IconoMas tamano={16} />} onClick={abrirFormulario}>
                Crear el primer caso
              </Boton>
            }
          />
        ) : (
          <div className="tabla-envoltorio">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Caso</th>
                  <th>Empresa</th>
                  <th className="numero">Cuentas</th>
                  <th className="numero">Asientos</th>
                  <th className="numero">Movimientos</th>
                  <th>Estado</th>
                  <th>Actualizado</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {almacen.casos.map((caso) => {
                  const balance = construirBalanceComprobacion(caso);
                  const activo = caso.id === almacen.casoActivo?.id;
                  return (
                    <tr key={caso.id} style={activo ? { background: 'var(--azul-50)' } : undefined}>
                      <td>
                        <strong>{caso.nombre}</strong>
                        {activo && (
                          <span className="etiqueta" style={{ marginLeft: 8 }}>
                            Abierto
                          </span>
                        )}
                      </td>
                      <td className="atenuado">{caso.empresa.nombre}</td>
                      <td className="numero">{caso.cuentas.length}</td>
                      <td className="numero">{caso.asientos.length}</td>
                      <td className="numero">
                        {formatearMoneda(balance.totalDebe, caso.empresa.simboloMoneda)}
                      </td>
                      <td>
                        {caso.asientos.length === 0 ? (
                          <span className="atenuado">Sin asientos</span>
                        ) : balance.cuadrado ? (
                          <span className="etiqueta INGRESO">Cuadrado</span>
                        ) : (
                          <span className="etiqueta PASIVO">Descuadrado</span>
                        )}
                      </td>
                      <td className="atenuado">{caso.actualizadoEn.slice(0, 10)}</td>
                      <td>
                        <div className="lista-acciones">
                          {!activo && (
                            <Boton
                              chico
                              variante="secundario"
                              onClick={() => {
                                almacen.seleccionarCaso(caso.id);
                                avisos.mostrar(`Caso "${caso.nombre}" abierto.`, 'info');
                              }}
                            >
                              Abrir
                            </Boton>
                          )}
                          <Boton
                            chico
                            variante="discreto"
                            title="Duplicar"
                            aria-label={`Duplicar ${caso.nombre}`}
                            onClick={() => {
                              almacen.duplicarCaso(caso.id);
                              avisos.exito('Caso duplicado.');
                            }}
                            icono={<IconoCopiar tamano={15} />}
                          />
                          <Boton
                            chico
                            variante="discreto"
                            title="Exportar JSON"
                            aria-label={`Exportar ${caso.nombre}`}
                            onClick={() => {
                              exportarCasoJson(caso);
                              avisos.exito('Archivo JSON descargado.');
                            }}
                            icono={<IconoDescargar tamano={15} />}
                          />
                          <Boton
                            chico
                            variante="discreto"
                            title="Eliminar"
                            aria-label={`Eliminar ${caso.nombre}`}
                            onClick={() => setPorEliminar(caso.id)}
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

      <Tarjeta
        titulo="Casos de ejemplo"
        subtitulo="Datos de prueba listos para revisar los reportes. No afectan a tus casos."
      >
        <div className="rejilla rejilla-2">
          {PLANTILLAS_CASO.map((plantilla) => (
            <div key={plantilla.id} className="acceso" style={{ alignItems: 'center' }}>
              <span className="acceso-icono">
                <IconoCasos />
              </span>
              <div style={{ flex: 1 }}>
                <strong>{plantilla.nombre}</strong>
                <span>{plantilla.descripcion}</span>
                <span className="atenuado">
                  {plantilla.asientos.length} asientos · período{' '}
                  {formatearFecha(plantilla.empresa.periodoInicio)} a{' '}
                  {formatearFecha(plantilla.empresa.periodoFin)}
                </span>
              </div>
              <Boton chico variante="secundario" onClick={() => cargarDemo(plantilla.id)}>
                Cargar
              </Boton>
            </div>
          ))}
        </div>
      </Tarjeta>

      {creando && (
        <Modal
          titulo="Nuevo caso contable"
          onCerrar={() => setCreando(false)}
          pie={
            <>
              <Boton variante="secundario" onClick={() => setCreando(false)}>
                Cancelar
              </Boton>
              <Boton onClick={guardarCaso}>Crear caso</Boton>
            </>
          }
        >
          <Campo
            etiqueta="Nombre del caso"
            error={errorNombre}
            ayuda="Por ejemplo: el nombre de la empresa del enunciado."
            htmlFor="nombre-caso"
          >
            <input
              id="nombre-caso"
              type="text"
              value={borrador.nombre}
              className={errorNombre ? 'con-error' : ''}
              onChange={(evento) => {
                setBorrador({ ...borrador, nombre: evento.target.value });
                setErrorNombre('');
              }}
              placeholder="Comercializadora del Sur S.A.C."
            />
          </Campo>

          <Campo etiqueta="Plan de cuentas inicial" htmlFor="plantilla-cuentas">
            <select
              id="plantilla-cuentas"
              value={borrador.plantillaCuentas}
              onChange={(evento) =>
                setBorrador({ ...borrador, plantillaCuentas: evento.target.value })
              }
            >
              {PLANTILLAS_CUENTAS.map((plantilla) => (
                <option key={plantilla.id} value={plantilla.id}>
                  {plantilla.nombre}
                </option>
              ))}
            </select>
            <span className="ayuda">
              {PLANTILLAS_CUENTAS.find((item) => item.id === borrador.plantillaCuentas)?.descripcion}
            </span>
          </Campo>

          <div className="fila-campos">
            <Campo etiqueta="RUC (opcional)" htmlFor="ruc">
              <input
                id="ruc"
                type="text"
                value={borrador.empresa.ruc ?? ''}
                onChange={(evento) =>
                  setBorrador({
                    ...borrador,
                    empresa: { ...borrador.empresa, ruc: evento.target.value },
                  })
                }
              />
            </Campo>
            <Campo etiqueta="Símbolo de moneda" htmlFor="moneda">
              <input
                id="moneda"
                type="text"
                value={borrador.empresa.simboloMoneda ?? 'S/'}
                onChange={(evento) =>
                  setBorrador({
                    ...borrador,
                    empresa: { ...borrador.empresa, simboloMoneda: evento.target.value },
                  })
                }
              />
            </Campo>
          </div>

          <div className="fila-campos">
            <Campo etiqueta="Inicio del período" htmlFor="inicio">
              <input
                id="inicio"
                type="date"
                value={borrador.empresa.periodoInicio ?? ''}
                onChange={(evento) =>
                  setBorrador({
                    ...borrador,
                    empresa: { ...borrador.empresa, periodoInicio: evento.target.value },
                  })
                }
              />
            </Campo>
            <Campo etiqueta="Fin del período" htmlFor="fin">
              <input
                id="fin"
                type="date"
                value={borrador.empresa.periodoFin ?? ''}
                onChange={(evento) =>
                  setBorrador({
                    ...borrador,
                    empresa: { ...borrador.empresa, periodoFin: evento.target.value },
                  })
                }
              />
            </Campo>
            <Campo etiqueta="Impuesto a la renta (%)" htmlFor="tasa">
              <input
                id="tasa"
                type="number"
                min={0}
                max={100}
                step={0.1}
                value={borrador.empresa.tasaImpuestoRenta ?? 0}
                onChange={(evento) =>
                  setBorrador({
                    ...borrador,
                    empresa: {
                      ...borrador.empresa,
                      tasaImpuestoRenta: Number(evento.target.value),
                    },
                  })
                }
              />
            </Campo>
          </div>

          <Aviso tipo="info">
            Todo esto se puede cambiar después en Configuración. El plan de cuentas también se edita
            cuenta por cuenta.
          </Aviso>
        </Modal>
      )}

      {casoAEliminar && (
        <Modal
          titulo="Eliminar caso"
          onCerrar={() => setPorEliminar(null)}
          pie={
            <>
              <Boton variante="secundario" onClick={() => setPorEliminar(null)}>
                Cancelar
              </Boton>
              <Boton
                variante="peligro"
                onClick={() => {
                  almacen.eliminarCaso(casoAEliminar.id);
                  setPorEliminar(null);
                  avisos.mostrar('Caso eliminado.', 'advertencia');
                }}
              >
                Eliminar definitivamente
              </Boton>
            </>
          }
        >
          <Aviso tipo="advertencia">
            Se va a eliminar <strong>{casoAEliminar.nombre}</strong> con sus{' '}
            {casoAEliminar.cuentas.length} cuentas y {casoAEliminar.asientos.length} asientos. Esta
            acción no se puede deshacer.
          </Aviso>
          <p className="atenuado" style={{ fontSize: 13 }}>
            Si quieres conservarlo, exporta primero el archivo JSON.
          </p>
        </Modal>
      )}
    </>
  );
}
