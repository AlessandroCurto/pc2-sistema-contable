import { useEffect, useState, type ReactNode } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { useAlmacen } from '../almacen/almacen';
import { GRUPOS_MENU, MENU, entradaDeRuta } from './navegacion';
import { IconoCerrar, IconoMenu } from './Iconos';
import { Boton, Cargando, EstadoVacio, Tarjeta } from './ui';

function MenuLateral({ abierto, cerrar }: { abierto: boolean; cerrar: () => void }) {
  const { casoActivo } = useAlmacen();
  return (
    <aside className={`menu-lateral no-imprimir${abierto ? ' abierto' : ''}`}>
      <div className="menu-marca">
        <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden="true">
          <rect width="32" height="32" rx="7" fill="#0a0a0a" />
          <path d="M8 22V10h4v12zM14 22V14h4v8zM20 22v-6h4v6z" fill="#f2c200" />
        </svg>
        <div>
          <strong>Contabilidad UNI</strong>
          <span>Sistema Contable</span>
        </div>
      </div>

      <div className="menu-caso">
        Caso abierto
        <strong>{casoActivo ? casoActivo.nombre : 'Ninguno'}</strong>
      </div>

      {GRUPOS_MENU.map((grupo) => {
        const entradas = MENU.filter((entrada) => entrada.grupo === grupo);
        if (entradas.length === 0) return null;
        return (
          <nav key={grupo}>
            <div className="menu-grupo">{grupo}</div>
            {entradas.map((entrada) => (
              <NavLink
                key={entrada.ruta}
                to={entrada.ruta}
                end={entrada.ruta === '/'}
                className={({ isActive }) => `menu-enlace${isActive ? ' activo' : ''}`}
                onClick={cerrar}
              >
                {entrada.icono}
                {entrada.etiqueta}
              </NavLink>
            ))}
          </nav>
        );
      })}

      <div className="menu-pie">
        Contabilidad UNI — Sistema Contable
        <br />
        Los datos se guardan en este navegador.
      </div>
    </aside>
  );
}

export function Layout() {
  const { cargando } = useAlmacen();
  const ubicacion = useLocation();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const entrada = entradaDeRuta(ubicacion.pathname);

  useEffect(() => {
    setMenuAbierto(false);
    window.scrollTo({ top: 0 });
  }, [ubicacion.pathname]);

  return (
    <div className="aplicacion">
      <MenuLateral abierto={menuAbierto} cerrar={() => setMenuAbierto(false)} />
      <div
        className={`velo${menuAbierto ? ' visible' : ''}`}
        onClick={() => setMenuAbierto(false)}
        aria-hidden="true"
      />
      <div className="contenido">
        <header className="barra-superior">
          <button
            type="button"
            className="boton-menu"
            aria-label={menuAbierto ? 'Cerrar menú' : 'Abrir menú'}
            onClick={() => setMenuAbierto((valor) => !valor)}
          >
            {menuAbierto ? <IconoCerrar /> : <IconoMenu />}
          </button>
          <div>
            <h1>{entrada?.etiqueta ?? 'Contabilidad UNI'}</h1>
            <div className="subtitulo">{entrada?.descripcion ?? 'Sistema contable'}</div>
          </div>
        </header>
        <main className="pagina">
          {cargando ? <Cargando texto="Abriendo Contabilidad UNI…" /> : <Outlet />}
        </main>
      </div>
    </div>
  );
}

/** Envuelve las pantallas que necesitan un caso abierto. */
export function RequiereCaso({ children }: { children: ReactNode }) {
  const { casoActivo, cargando } = useAlmacen();
  if (cargando) return <Cargando />;
  if (!casoActivo) {
    return (
      <Tarjeta>
        <EstadoVacio
          titulo="Todavía no hay un caso abierto"
          descripcion="Un caso reúne la empresa, su plan de cuentas y sus asientos. Crea uno nuevo o carga un caso de ejemplo para empezar."
          accion={
            <Link to="/casos">
              <Boton>Ir a Casos</Boton>
            </Link>
          }
        />
      </Tarjeta>
    );
  }
  return <>{children}</>;
}
