import { useEffect, useState } from 'react';
import { useAlmacen } from '../almacen/almacen';
import { useAvisos } from '../componentes/Avisos';
import { Aviso, Boton, Campo, Modal, Tarjeta } from '../componentes/ui';
import { IconoCheck, IconoDescargar } from '../componentes/Iconos';
import type { Empresa } from '../dominio/tipos';
import { exportarCasoJson } from '../servicios/archivos';

export function Configuracion() {
  const almacen = useAlmacen();
  const avisos = useAvisos();
  const caso = almacen.casoActivo;

  const [nombreCaso, setNombreCaso] = useState('');
  const [empresa, setEmpresa] = useState<Empresa | null>(null);
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [confirmarBorrado, setConfirmarBorrado] = useState(false);
  const [confirmarReinicio, setConfirmarReinicio] = useState(false);

  useEffect(() => {
    if (!caso) return;
    setNombreCaso(caso.nombre);
    setEmpresa({ ...caso.empresa });
    setErrores({});
  }, [caso]);

  if (!caso || !empresa) return null;

  function cambiar<Clave extends keyof Empresa>(clave: Clave, valor: Empresa[Clave]) {
    setEmpresa((actual) => (actual ? { ...actual, [clave]: valor } : actual));
  }

  function guardar() {
    if (!empresa) return;
    const encontrados: Record<string, string> = {};
    if (nombreCaso.trim() === '') encontrados.nombreCaso = 'Escribe el nombre del caso.';
    if (empresa.nombre.trim() === '') encontrados.nombre = 'Escribe el nombre de la empresa.';
    if (empresa.simboloMoneda.trim() === '') encontrados.moneda = 'Escribe el símbolo de la moneda.';
    if (empresa.tasaImpuestoRenta < 0 || empresa.tasaImpuestoRenta > 100) {
      encontrados.tasa = 'La tasa debe estar entre 0 y 100.';
    }
    if (
      empresa.periodoInicio &&
      empresa.periodoFin &&
      empresa.periodoInicio > empresa.periodoFin
    ) {
      encontrados.periodo = 'El inicio del período no puede ser posterior al fin.';
    }
    setErrores(encontrados);
    if (Object.keys(encontrados).length > 0) {
      avisos.error('Revisa los datos marcados.');
      return;
    }

    almacen.renombrarCaso(caso!.id, nombreCaso);
    almacen.actualizarEmpresa(empresa);
    avisos.exito('Configuración guardada.');
  }

  return (
    <>
      <Tarjeta
        titulo="Datos de la empresa"
        subtitulo="Aparecen en la cabecera de todos los reportes y del PDF."
        acciones={
          <Boton icono={<IconoCheck tamano={16} />} onClick={guardar}>
            Guardar cambios
          </Boton>
        }
      >
        <div className="fila-campos">
          <Campo etiqueta="Nombre del caso" error={errores.nombreCaso} htmlFor="nombre-caso">
            <input
              id="nombre-caso"
              type="text"
              value={nombreCaso}
              className={errores.nombreCaso ? 'con-error' : ''}
              onChange={(evento) => setNombreCaso(evento.target.value)}
            />
          </Campo>
          <Campo etiqueta="Razón social" error={errores.nombre} htmlFor="nombre-empresa">
            <input
              id="nombre-empresa"
              type="text"
              value={empresa.nombre}
              className={errores.nombre ? 'con-error' : ''}
              onChange={(evento) => cambiar('nombre', evento.target.value)}
            />
          </Campo>
          <Campo etiqueta="RUC" htmlFor="ruc">
            <input
              id="ruc"
              type="text"
              value={empresa.ruc}
              onChange={(evento) => cambiar('ruc', evento.target.value)}
            />
          </Campo>
        </div>

        <div className="fila-campos" style={{ marginTop: 14 }}>
          <Campo etiqueta="Inicio del período" error={errores.periodo} htmlFor="inicio">
            <input
              id="inicio"
              type="date"
              value={empresa.periodoInicio}
              onChange={(evento) => cambiar('periodoInicio', evento.target.value)}
            />
          </Campo>
          <Campo etiqueta="Fin del período" htmlFor="fin">
            <input
              id="fin"
              type="date"
              value={empresa.periodoFin}
              onChange={(evento) => cambiar('periodoFin', evento.target.value)}
            />
          </Campo>
          <Campo etiqueta="Símbolo de moneda" error={errores.moneda} htmlFor="moneda">
            <input
              id="moneda"
              type="text"
              maxLength={5}
              value={empresa.simboloMoneda}
              className={errores.moneda ? 'con-error' : ''}
              onChange={(evento) => cambiar('simboloMoneda', evento.target.value)}
            />
          </Campo>
          <Campo
            etiqueta="Impuesto a la renta (%)"
            error={errores.tasa}
            ayuda="Se aplica solo en el Estado de Resultados."
            htmlFor="tasa"
          >
            <input
              id="tasa"
              type="number"
              min={0}
              max={100}
              step={0.1}
              value={empresa.tasaImpuestoRenta}
              className={errores.tasa ? 'con-error' : ''}
              onChange={(evento) => cambiar('tasaImpuestoRenta', Number(evento.target.value))}
            />
          </Campo>
        </div>

        <label className="casilla" style={{ marginTop: 16 }}>
          <input
            type="checkbox"
            checked={empresa.impuestoAfectaPatrimonio}
            onChange={(evento) => cambiar('impuestoAfectaPatrimonio', evento.target.checked)}
          />
          <span>
            Descontar el impuesto a la renta del resultado que se suma al patrimonio en el Balance
            General.
            <br />
            <span className="atenuado" style={{ fontSize: 12.5 }}>
              Déjalo desactivado si el impuesto no se registra como asiento: así la ecuación contable
              sigue cerrando.
            </span>
          </span>
        </label>
      </Tarjeta>

      <Tarjeta
        titulo="Datos del caso"
        subtitulo="Los datos se guardan en este navegador. Exporta el caso para llevarlo a otra computadora."
      >
        <div className="lista-acciones">
          <Boton
            variante="secundario"
            icono={<IconoDescargar tamano={16} />}
            onClick={() => {
              exportarCasoJson(caso);
              avisos.exito('Caso exportado en JSON.');
            }}
          >
            Exportar este caso
          </Boton>
          <Boton
            variante="secundario"
            disabled={caso.asientos.length === 0}
            onClick={() => setConfirmarBorrado(true)}
          >
            Borrar todos los asientos
          </Boton>
          <Boton variante="peligro" onClick={() => setConfirmarReinicio(true)}>
            Borrar todos los datos del navegador
          </Boton>
        </div>
      </Tarjeta>

      {confirmarBorrado && (
        <Modal
          titulo="Borrar los asientos del caso"
          onCerrar={() => setConfirmarBorrado(false)}
          pie={
            <>
              <Boton variante="secundario" onClick={() => setConfirmarBorrado(false)}>
                Cancelar
              </Boton>
              <Boton
                variante="peligro"
                onClick={() => {
                  almacen.borrarAsientos();
                  setConfirmarBorrado(false);
                  avisos.mostrar('Se borraron los asientos del caso.', 'advertencia');
                }}
              >
                Borrar asientos
              </Boton>
            </>
          }
        >
          <Aviso tipo="advertencia">
            Se eliminarán los {caso.asientos.length} asientos de "{caso.nombre}". El plan de cuentas
            se conserva.
          </Aviso>
        </Modal>
      )}

      {confirmarReinicio && (
        <Modal
          titulo="Borrar todos los datos"
          onCerrar={() => setConfirmarReinicio(false)}
          pie={
            <>
              <Boton variante="secundario" onClick={() => setConfirmarReinicio(false)}>
                Cancelar
              </Boton>
              <Boton
                variante="peligro"
                onClick={() => {
                  almacen.reiniciarTodo();
                  setConfirmarReinicio(false);
                  avisos.mostrar('Se borraron todos los casos de este navegador.', 'advertencia');
                }}
              >
                Borrar todo
              </Boton>
            </>
          }
        >
          <Aviso tipo="error">
            Se eliminarán los {almacen.casos.length} casos guardados en este navegador. Exporta antes
            lo que quieras conservar.
          </Aviso>
        </Modal>
      )}
    </>
  );
}
