import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { IconoAlerta, IconoCheck } from './Iconos';

/* ---------- Tarjeta ---------- */

export function Tarjeta({
  titulo,
  subtitulo,
  acciones,
  children,
  sinEspacio = false,
  className = '',
}: {
  titulo?: ReactNode;
  subtitulo?: ReactNode;
  acciones?: ReactNode;
  children?: ReactNode;
  sinEspacio?: boolean;
  className?: string;
}) {
  return (
    <section className={`tarjeta ${className}`.trim()}>
      {(titulo || acciones) && (
        <header className="tarjeta-cabecera">
          <div>
            {titulo && <h2>{titulo}</h2>}
            {subtitulo && <div className="subtitulo">{subtitulo}</div>}
          </div>
          {acciones && <div className="acciones no-imprimir">{acciones}</div>}
        </header>
      )}
      {children !== undefined && (
        <div className={`tarjeta-cuerpo${sinEspacio ? ' sin-espacio' : ''}`}>{children}</div>
      )}
    </section>
  );
}

/* ---------- Botón ---------- */

type VarianteBoton = 'primario' | 'secundario' | 'peligro' | 'discreto';

export function Boton({
  variante = 'primario',
  chico = false,
  ancho = false,
  cargando = false,
  icono,
  children,
  className = '',
  disabled,
  ...resto
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variante?: VarianteBoton;
  chico?: boolean;
  ancho?: boolean;
  cargando?: boolean;
  icono?: ReactNode;
}) {
  const clases = [
    'boton',
    variante === 'primario' ? '' : variante,
    chico ? 'chico' : '',
    ancho ? 'ancho' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');
  return (
    <button type="button" className={clases} disabled={disabled || cargando} {...resto}>
      {cargando ? <span className="girador mini" /> : icono}
      {children}
    </button>
  );
}

/* ---------- Campo de formulario ---------- */

export function Campo({
  etiqueta,
  error,
  ayuda,
  children,
  htmlFor,
}: {
  etiqueta: string;
  error?: string;
  ayuda?: string;
  children: ReactNode;
  htmlFor?: string;
}) {
  return (
    <div className="campo">
      <label htmlFor={htmlFor}>{etiqueta}</label>
      {children}
      {ayuda && !error && <span className="ayuda">{ayuda}</span>}
      {error && <span className="error">{error}</span>}
    </div>
  );
}

/* ---------- Aviso en línea ---------- */

export type TipoAviso = 'exito' | 'error' | 'advertencia' | 'info';

export function Aviso({ tipo = 'info', children }: { tipo?: TipoAviso; children: ReactNode }) {
  return (
    <div className={`aviso ${tipo}`} role={tipo === 'error' ? 'alert' : 'status'}>
      {tipo === 'exito' ? <IconoCheck tamano={17} /> : <IconoAlerta tamano={17} />}
      <div>{children}</div>
    </div>
  );
}

/* ---------- Estados ---------- */

export function Cargando({ texto = 'Cargando…' }: { texto?: string }) {
  return (
    <div className="cargando" role="status">
      <span className="girador" />
      <span>{texto}</span>
    </div>
  );
}

export function EsqueletoTabla({ filas = 5, columnas = 4 }: { filas?: number; columnas?: number }) {
  return (
    <div style={{ display: 'grid', gap: 10, padding: 18 }} aria-hidden="true">
      {Array.from({ length: filas }).map((_, fila) => (
        <div key={fila} style={{ display: 'grid', gap: 10, gridTemplateColumns: `repeat(${columnas}, 1fr)` }}>
          {Array.from({ length: columnas }).map((__, columna) => (
            <div key={columna} className="esqueleto" />
          ))}
        </div>
      ))}
    </div>
  );
}

export function EstadoVacio({
  titulo,
  descripcion,
  accion,
}: {
  titulo: string;
  descripcion?: string;
  accion?: ReactNode;
}) {
  return (
    <div className="estado-vacio">
      <h3>{titulo}</h3>
      {descripcion && <p>{descripcion}</p>}
      {accion}
    </div>
  );
}

/* ---------- Ventana modal ---------- */

export function Modal({
  titulo,
  children,
  pie,
  onCerrar,
}: {
  titulo: string;
  children: ReactNode;
  pie?: ReactNode;
  onCerrar: () => void;
}) {
  return (
    <div
      className="fondo-modal no-imprimir"
      role="dialog"
      aria-modal="true"
      aria-label={titulo}
      onClick={(evento) => {
        if (evento.target === evento.currentTarget) onCerrar();
      }}
    >
      <div className="modal">
        <header className="modal-cabecera">
          <h2>{titulo}</h2>
        </header>
        <div className="modal-cuerpo">{children}</div>
        {pie && <footer className="modal-pie">{pie}</footer>}
      </div>
    </div>
  );
}

/* ---------- Indicador ---------- */

export function Indicador({
  etiqueta,
  valor,
  pie,
  color,
}: {
  etiqueta: string;
  valor: ReactNode;
  pie?: ReactNode;
  color?: string;
}) {
  return (
    <div className="indicador">
      <div className="etiqueta">{etiqueta}</div>
      <div className="valor" style={color ? { color } : undefined}>
        {valor}
      </div>
      {pie && <div className="pie">{pie}</div>}
    </div>
  );
}

/* ---------- Marca de cuadre ---------- */

export function MarcaCuadre({ cuadrado, textoOk, textoMal }: { cuadrado: boolean; textoOk: string; textoMal: string }) {
  return (
    <div className={`marca-cuadre ${cuadrado ? 'ok' : 'mal'}`} role="status">
      {cuadrado ? <IconoCheck tamano={18} /> : <IconoAlerta tamano={18} />}
      <span>{cuadrado ? textoOk : textoMal}</span>
    </div>
  );
}
