import type { Asiento, Caso, Cuenta, Empresa, EstadoPersistido, LineaAsiento } from '../dominio/tipos';
import { TIPOS_CUENTA } from '../dominio/cuentas';
import { nuevoId } from '../dominio/ids';
import { redondear } from '../dominio/numeros';

export const CLAVE_ALMACEN = 'contasys:estado';
export const VERSION_ESTADO = 1;

export const EMPRESA_POR_DEFECTO: Empresa = {
  nombre: 'Mi Empresa S.A.C.',
  ruc: '',
  simboloMoneda: 'S/',
  periodoInicio: '',
  periodoFin: '',
  tasaImpuestoRenta: 29.5,
  impuestoAfectaPatrimonio: false,
};

function texto(valor: unknown, porDefecto = ''): string {
  return typeof valor === 'string' ? valor : porDefecto;
}

function numero(valor: unknown, porDefecto = 0): number {
  const convertido = typeof valor === 'number' ? valor : Number(valor);
  return Number.isFinite(convertido) ? convertido : porDefecto;
}

function esObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === 'object' && valor !== null && !Array.isArray(valor);
}

function saneaEmpresa(valor: unknown): Empresa {
  if (!esObjeto(valor)) return { ...EMPRESA_POR_DEFECTO };
  return {
    nombre: texto(valor.nombre, EMPRESA_POR_DEFECTO.nombre),
    ruc: texto(valor.ruc),
    simboloMoneda: texto(valor.simboloMoneda, 'S/') || 'S/',
    periodoInicio: texto(valor.periodoInicio),
    periodoFin: texto(valor.periodoFin),
    tasaImpuestoRenta: Math.max(0, numero(valor.tasaImpuestoRenta, 0)),
    impuestoAfectaPatrimonio: valor.impuestoAfectaPatrimonio === true,
  };
}

function saneaCuenta(valor: unknown): Cuenta | null {
  if (!esObjeto(valor)) return null;
  const codigo = texto(valor.codigo).trim();
  const nombre = texto(valor.nombre).trim();
  const tipo = texto(valor.tipo).toUpperCase();
  if (codigo === '' || nombre === '') return null;
  if (!TIPOS_CUENTA.includes(tipo as Cuenta['tipo'])) return null;
  const rubro = texto(valor.rubro).toUpperCase();
  return {
    id: texto(valor.id) || nuevoId('cta'),
    codigo,
    nombre,
    tipo: tipo as Cuenta['tipo'],
    rubro: rubro === '' ? undefined : (rubro as Cuenta['rubro']),
  };
}

function saneaLinea(valor: unknown, idsCuentas: Set<string>): LineaAsiento | null {
  if (!esObjeto(valor)) return null;
  const cuentaId = texto(valor.cuentaId);
  if (!idsCuentas.has(cuentaId)) return null;
  return {
    id: texto(valor.id) || nuevoId('lin'),
    cuentaId,
    debe: Math.max(0, redondear(numero(valor.debe))),
    haber: Math.max(0, redondear(numero(valor.haber))),
  };
}

function saneaAsiento(valor: unknown, idsCuentas: Set<string>, indice: number): Asiento | null {
  if (!esObjeto(valor)) return null;
  const lineasCrudas = Array.isArray(valor.lineas) ? valor.lineas : [];
  const lineas = lineasCrudas
    .map((linea) => saneaLinea(linea, idsCuentas))
    .filter((linea): linea is LineaAsiento => linea !== null);
  if (lineas.length === 0) return null;
  const fecha = texto(valor.fecha);
  return {
    id: texto(valor.id) || nuevoId('asi'),
    numero: Math.max(1, Math.trunc(numero(valor.numero, indice + 1))),
    fecha: /^\d{4}-\d{2}-\d{2}$/.test(fecha) ? fecha : '1970-01-01',
    glosa: texto(valor.glosa),
    lineas,
  };
}

/** Convierte datos desconocidos (localStorage o archivo importado) en un caso válido. */
export function saneaCaso(valor: unknown): Caso | null {
  if (!esObjeto(valor)) return null;
  const cuentasCrudas = Array.isArray(valor.cuentas) ? valor.cuentas : [];
  const cuentas = cuentasCrudas
    .map(saneaCuenta)
    .filter((cuenta): cuenta is Cuenta => cuenta !== null);
  const idsCuentas = new Set(cuentas.map((cuenta) => cuenta.id));
  const asientosCrudos = Array.isArray(valor.asientos) ? valor.asientos : [];
  const asientos = asientosCrudos
    .map((asiento, indice) => saneaAsiento(asiento, idsCuentas, indice))
    .filter((asiento): asiento is Asiento => asiento !== null);
  const ahora = new Date().toISOString();
  const empresa = saneaEmpresa(valor.empresa);

  return {
    id: texto(valor.id) || nuevoId('caso'),
    nombre: texto(valor.nombre).trim() || empresa.nombre || 'Caso sin nombre',
    creadoEn: texto(valor.creadoEn, ahora),
    actualizadoEn: texto(valor.actualizadoEn, ahora),
    empresa,
    cuentas,
    asientos,
  };
}

export function estadoVacio(): EstadoPersistido {
  return { version: VERSION_ESTADO, casoActivoId: null, casos: [] };
}

export function saneaEstado(valor: unknown): EstadoPersistido {
  if (!esObjeto(valor)) return estadoVacio();
  const casosCrudos = Array.isArray(valor.casos) ? valor.casos : [];
  const casos = casosCrudos.map(saneaCaso).filter((caso): caso is Caso => caso !== null);
  const casoActivoId = texto(valor.casoActivoId);
  return {
    version: VERSION_ESTADO,
    casos,
    casoActivoId: casos.some((caso) => caso.id === casoActivoId)
      ? casoActivoId
      : (casos[0]?.id ?? null),
  };
}

export function leerEstado(): EstadoPersistido {
  if (typeof window === 'undefined') return estadoVacio();
  try {
    const crudo = window.localStorage.getItem(CLAVE_ALMACEN);
    if (!crudo) return estadoVacio();
    return saneaEstado(JSON.parse(crudo));
  } catch {
    return estadoVacio();
  }
}

export function guardarEstado(estado: EstadoPersistido): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(CLAVE_ALMACEN, JSON.stringify(estado));
  } catch {
    // El navegador puede bloquear el almacenamiento (modo privado o sin espacio).
    // La app sigue funcionando en memoria durante la sesión.
  }
}

export function borrarEstado(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(CLAVE_ALMACEN);
  } catch {
    // Sin almacenamiento no hay nada que borrar.
  }
}
