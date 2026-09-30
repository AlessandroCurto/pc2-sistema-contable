import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type { Asiento, Caso, Cuenta, Empresa, EstadoPersistido, LineaAsiento } from '../dominio/tipos';
import { nuevoId } from '../dominio/ids';
import { normalizarLineas, renumerar, siguienteNumero } from '../dominio/asientos';
import { crearCuentas, obtenerPlantilla } from '../datos/plantillasCuentas';
import { construirCasoDemo, obtenerPlantillaCaso } from '../datos/casosDemo';
import {
  EMPRESA_POR_DEFECTO,
  borrarEstado,
  estadoVacio,
  guardarEstado,
  leerEstado,
  saneaCaso,
} from './persistencia';

export interface BorradorCuenta {
  codigo: string;
  nombre: string;
  tipo: Cuenta['tipo'];
  rubro?: Cuenta['rubro'];
}

export interface BorradorAsiento {
  id?: string;
  fecha: string;
  glosa: string;
  lineas: LineaAsiento[];
}

export interface BorradorCaso {
  nombre: string;
  plantillaCuentas: string;
  empresa: Partial<Empresa>;
}

export interface Resultado {
  ok: boolean;
  mensaje: string;
}

type Accion =
  | { tipo: 'HIDRATAR'; estado: EstadoPersistido }
  | { tipo: 'AGREGAR_CASO'; caso: Caso }
  | { tipo: 'REEMPLAZAR_CASO'; caso: Caso }
  | { tipo: 'ELIMINAR_CASO'; id: string }
  | { tipo: 'SELECCIONAR_CASO'; id: string }
  | { tipo: 'REINICIAR' };

function marcar(caso: Caso): Caso {
  return { ...caso, actualizadoEn: new Date().toISOString() };
}

function reducir(estado: EstadoPersistido, accion: Accion): EstadoPersistido {
  switch (accion.tipo) {
    case 'HIDRATAR':
      return accion.estado;
    case 'AGREGAR_CASO':
      return {
        ...estado,
        casos: [...estado.casos, accion.caso],
        casoActivoId: accion.caso.id,
      };
    case 'REEMPLAZAR_CASO':
      return {
        ...estado,
        casos: estado.casos.map((caso) => (caso.id === accion.caso.id ? accion.caso : caso)),
      };
    case 'ELIMINAR_CASO': {
      const casos = estado.casos.filter((caso) => caso.id !== accion.id);
      return {
        ...estado,
        casos,
        casoActivoId:
          estado.casoActivoId === accion.id ? (casos[0]?.id ?? null) : estado.casoActivoId,
      };
    }
    case 'SELECCIONAR_CASO':
      return { ...estado, casoActivoId: accion.id };
    case 'REINICIAR':
      return estadoVacio();
    default:
      return estado;
  }
}

export interface ValorAlmacen {
  cargando: boolean;
  casos: Caso[];
  casoActivo: Caso | null;
  crearCaso: (borrador: BorradorCaso) => string;
  cargarCasoDemo: (plantillaId: string) => string | null;
  duplicarCaso: (id: string) => string | null;
  renombrarCaso: (id: string, nombre: string) => void;
  eliminarCaso: (id: string) => void;
  seleccionarCaso: (id: string) => void;
  importarCaso: (datos: unknown) => Resultado;
  actualizarEmpresa: (cambios: Partial<Empresa>) => void;
  actualizarDatosCaso: (cambios: { nombre?: string; empresa?: Partial<Empresa> }) => void;
  agregarCuenta: (borrador: BorradorCuenta) => Cuenta | null;
  actualizarCuenta: (id: string, cambios: Partial<BorradorCuenta>) => void;
  eliminarCuenta: (id: string) => Resultado;
  agregarPlantillaCuentas: (plantillaId: string) => Resultado;
  guardarAsiento: (borrador: BorradorAsiento) => Resultado;
  eliminarAsiento: (id: string) => void;
  borrarAsientos: () => void;
  reiniciarTodo: () => void;
}

const ContextoAlmacen = createContext<ValorAlmacen | null>(null);

export function ProveedorAlmacen({ children }: { children: ReactNode }) {
  const [estado, despachar] = useReducer(reducir, estadoVacio());
  const [cargando, setCargando] = useState(true);
  const hidratado = useRef(false);

  useEffect(() => {
    const guardado = leerEstado();
    despachar({ tipo: 'HIDRATAR', estado: guardado });
    hidratado.current = true;
    setCargando(false);
  }, []);

  useEffect(() => {
    if (!hidratado.current) return;
    guardarEstado(estado);
  }, [estado]);

  const casoActivo = useMemo(
    () => estado.casos.find((caso) => caso.id === estado.casoActivoId) ?? null,
    [estado.casos, estado.casoActivoId],
  );

  const actualizarCasoActivo = useCallback(
    (transformar: (caso: Caso) => Caso) => {
      if (!casoActivo) return;
      despachar({ tipo: 'REEMPLAZAR_CASO', caso: marcar(transformar(casoActivo)) });
    },
    [casoActivo],
  );

  const crearCaso = useCallback((borrador: BorradorCaso) => {
    const ahora = new Date().toISOString();
    const plantilla = obtenerPlantilla(borrador.plantillaCuentas);
    const nombre = borrador.nombre.trim() || 'Caso sin nombre';
    const caso: Caso = {
      id: nuevoId('caso'),
      nombre,
      creadoEn: ahora,
      actualizadoEn: ahora,
      empresa: { ...EMPRESA_POR_DEFECTO, nombre, ...borrador.empresa },
      cuentas: crearCuentas(plantilla.cuentas, nuevoId('plan')),
      asientos: [],
    };
    despachar({ tipo: 'AGREGAR_CASO', caso });
    return caso.id;
  }, []);

  const cargarCasoDemo = useCallback((plantillaId: string) => {
    const plantilla = obtenerPlantillaCaso(plantillaId);
    if (!plantilla) return null;
    const caso = construirCasoDemo(plantilla);
    despachar({ tipo: 'AGREGAR_CASO', caso });
    return caso.id;
  }, []);

  const duplicarCaso = useCallback(
    (id: string) => {
      const original = estado.casos.find((caso) => caso.id === id);
      if (!original) return null;
      const copia = saneaCaso({
        ...structuredClone(original),
        id: nuevoId('caso'),
        nombre: `${original.nombre} (copia)`,
      });
      if (!copia) return null;
      despachar({ tipo: 'AGREGAR_CASO', caso: copia });
      return copia.id;
    },
    [estado.casos],
  );

  const renombrarCaso = useCallback(
    (id: string, nombre: string) => {
      const original = estado.casos.find((caso) => caso.id === id);
      if (!original) return;
      despachar({
        tipo: 'REEMPLAZAR_CASO',
        caso: marcar({ ...original, nombre: nombre.trim() || original.nombre }),
      });
    },
    [estado.casos],
  );

  const eliminarCaso = useCallback((id: string) => {
    despachar({ tipo: 'ELIMINAR_CASO', id });
  }, []);

  const seleccionarCaso = useCallback((id: string) => {
    despachar({ tipo: 'SELECCIONAR_CASO', id });
  }, []);

  const importarCaso = useCallback((datos: unknown) => {
    const caso = saneaCaso(datos);
    if (!caso) {
      return { ok: false, mensaje: 'El archivo no tiene la estructura de un caso de Contabilidad UNI.' };
    }
    if (caso.cuentas.length === 0) {
      return { ok: false, mensaje: 'El archivo no trae ninguna cuenta válida.' };
    }
    const importado: Caso = { ...caso, id: nuevoId('caso') };
    despachar({ tipo: 'AGREGAR_CASO', caso: importado });
    return {
      ok: true,
      mensaje: `Se importó "${importado.nombre}" con ${importado.cuentas.length} cuentas y ${importado.asientos.length} asientos.`,
    };
  }, []);

  const actualizarEmpresa = useCallback(
    (cambios: Partial<Empresa>) => {
      actualizarCasoActivo((caso) => ({ ...caso, empresa: { ...caso.empresa, ...cambios } }));
    },
    [actualizarCasoActivo],
  );

  const actualizarDatosCaso = useCallback(
    (cambios: { nombre?: string; empresa?: Partial<Empresa> }) => {
      // Un solo despacho: dos seguidos partirian del mismo caso y el segundo
      // pisaria al primero.
      actualizarCasoActivo((caso) => ({
        ...caso,
        nombre: cambios.nombre?.trim() || caso.nombre,
        empresa: { ...caso.empresa, ...cambios.empresa },
      }));
    },
    [actualizarCasoActivo],
  );

  const agregarCuenta = useCallback(
    (borrador: BorradorCuenta) => {
      if (!casoActivo) return null;
      const cuenta: Cuenta = {
        id: nuevoId('cta'),
        codigo: borrador.codigo.trim(),
        nombre: borrador.nombre.trim(),
        tipo: borrador.tipo,
        rubro: borrador.rubro,
      };
      actualizarCasoActivo((caso) => ({ ...caso, cuentas: [...caso.cuentas, cuenta] }));
      return cuenta;
    },
    [actualizarCasoActivo, casoActivo],
  );

  const actualizarCuenta = useCallback(
    (id: string, cambios: Partial<BorradorCuenta>) => {
      actualizarCasoActivo((caso) => ({
        ...caso,
        cuentas: caso.cuentas.map((cuenta) =>
          cuenta.id === id
            ? {
                ...cuenta,
                ...cambios,
                codigo: (cambios.codigo ?? cuenta.codigo).trim(),
                nombre: (cambios.nombre ?? cuenta.nombre).trim(),
              }
            : cuenta,
        ),
      }));
    },
    [actualizarCasoActivo],
  );

  const eliminarCuenta = useCallback(
    (id: string): Resultado => {
      if (!casoActivo) return { ok: false, mensaje: 'No hay un caso abierto.' };
      const usada = casoActivo.asientos.some((asiento) =>
        asiento.lineas.some((linea) => linea.cuentaId === id),
      );
      if (usada) {
        return {
          ok: false,
          mensaje: 'No se puede eliminar: la cuenta tiene movimientos registrados.',
        };
      }
      actualizarCasoActivo((caso) => ({
        ...caso,
        cuentas: caso.cuentas.filter((cuenta) => cuenta.id !== id),
      }));
      return { ok: true, mensaje: 'Cuenta eliminada.' };
    },
    [actualizarCasoActivo, casoActivo],
  );

  const agregarPlantillaCuentas = useCallback(
    (plantillaId: string): Resultado => {
      if (!casoActivo) return { ok: false, mensaje: 'No hay un caso abierto.' };
      const plantilla = obtenerPlantilla(plantillaId);
      const codigosActuales = new Set(
        casoActivo.cuentas.map((cuenta) => cuenta.codigo.toUpperCase()),
      );
      const nuevas = plantilla.cuentas
        .filter((definicion) => !codigosActuales.has(definicion.codigo.toUpperCase()))
        .map<Cuenta>((definicion) => ({
          id: nuevoId('cta'),
          codigo: definicion.codigo,
          nombre: definicion.nombre,
          tipo: definicion.tipo,
          rubro: definicion.rubro,
        }));
      if (nuevas.length === 0) {
        return { ok: false, mensaje: 'El caso ya tiene todas las cuentas de esa plantilla.' };
      }
      actualizarCasoActivo((caso) => ({ ...caso, cuentas: [...caso.cuentas, ...nuevas] }));
      return { ok: true, mensaje: `Se agregaron ${nuevas.length} cuentas.` };
    },
    [actualizarCasoActivo, casoActivo],
  );

  const guardarAsiento = useCallback(
    (borrador: BorradorAsiento): Resultado => {
      if (!casoActivo) return { ok: false, mensaje: 'No hay un caso abierto.' };
      const lineas = normalizarLineas(borrador.lineas);
      if (lineas.length < 2) {
        return { ok: false, mensaje: 'El asiento necesita al menos dos líneas.' };
      }
      const esEdicion = Boolean(
        borrador.id && casoActivo.asientos.some((asiento) => asiento.id === borrador.id),
      );
      actualizarCasoActivo((caso) => {
        const anterior = caso.asientos.find((asiento) => asiento.id === borrador.id);
        const asiento: Asiento = {
          id: borrador.id ?? nuevoId('asi'),
          numero: anterior?.numero ?? siguienteNumero(caso.asientos),
          fecha: borrador.fecha,
          glosa: borrador.glosa.trim(),
          lineas,
        };
        const asientos = anterior
          ? caso.asientos.map((item) => (item.id === asiento.id ? asiento : item))
          : [...caso.asientos, asiento];
        return { ...caso, asientos: renumerar(asientos) };
      });
      return {
        ok: true,
        mensaje: esEdicion ? 'Asiento actualizado.' : 'Asiento registrado.',
      };
    },
    [actualizarCasoActivo, casoActivo],
  );

  const eliminarAsiento = useCallback(
    (id: string) => {
      actualizarCasoActivo((caso) => ({
        ...caso,
        asientos: renumerar(caso.asientos.filter((asiento) => asiento.id !== id)),
      }));
    },
    [actualizarCasoActivo],
  );

  const borrarAsientos = useCallback(() => {
    actualizarCasoActivo((caso) => ({ ...caso, asientos: [] }));
  }, [actualizarCasoActivo]);

  const reiniciarTodo = useCallback(() => {
    borrarEstado();
    despachar({ tipo: 'REINICIAR' });
  }, []);

  const valor = useMemo<ValorAlmacen>(
    () => ({
      cargando,
      casos: estado.casos,
      casoActivo,
      crearCaso,
      cargarCasoDemo,
      duplicarCaso,
      renombrarCaso,
      eliminarCaso,
      seleccionarCaso,
      importarCaso,
      actualizarEmpresa,
      actualizarDatosCaso,
      agregarCuenta,
      actualizarCuenta,
      eliminarCuenta,
      agregarPlantillaCuentas,
      guardarAsiento,
      eliminarAsiento,
      borrarAsientos,
      reiniciarTodo,
    }),
    [
      cargando,
      estado.casos,
      casoActivo,
      crearCaso,
      cargarCasoDemo,
      duplicarCaso,
      renombrarCaso,
      eliminarCaso,
      seleccionarCaso,
      importarCaso,
      actualizarEmpresa,
      actualizarDatosCaso,
      agregarCuenta,
      actualizarCuenta,
      eliminarCuenta,
      agregarPlantillaCuentas,
      guardarAsiento,
      eliminarAsiento,
      borrarAsientos,
      reiniciarTodo,
    ],
  );

  return <ContextoAlmacen.Provider value={valor}>{children}</ContextoAlmacen.Provider>;
}

export function useAlmacen(): ValorAlmacen {
  const valor = useContext(ContextoAlmacen);
  if (!valor) throw new Error('useAlmacen debe usarse dentro de ProveedorAlmacen.');
  return valor;
}

/** Atajo para las pantallas que solo funcionan con un caso abierto. */
export function useCasoActivo(): Caso | null {
  return useAlmacen().casoActivo;
}
