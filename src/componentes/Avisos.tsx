import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';
import { IconoAlerta, IconoCheck, IconoCerrar } from './Iconos';
import type { TipoAviso } from './ui';

interface AvisoFlotante {
  id: number;
  tipo: TipoAviso;
  texto: string;
}

interface ValorAvisos {
  mostrar: (texto: string, tipo?: TipoAviso) => void;
  exito: (texto: string) => void;
  error: (texto: string) => void;
}

const ContextoAvisos = createContext<ValorAvisos | null>(null);

/** Avisos flotantes: confirman al usuario lo que acaba de ocurrir. */
export function ProveedorAvisos({ children }: { children: ReactNode }) {
  const [avisos, setAvisos] = useState<AvisoFlotante[]>([]);
  const contador = useRef(0);

  const cerrar = useCallback((id: number) => {
    setAvisos((actuales) => actuales.filter((aviso) => aviso.id !== id));
  }, []);

  const mostrar = useCallback(
    (texto: string, tipo: TipoAviso = 'info') => {
      contador.current += 1;
      const id = contador.current;
      setAvisos((actuales) => [...actuales, { id, tipo, texto }]);
      window.setTimeout(() => cerrar(id), tipo === 'error' ? 7000 : 4000);
    },
    [cerrar],
  );

  const valor = useMemo<ValorAvisos>(
    () => ({
      mostrar,
      exito: (texto: string) => mostrar(texto, 'exito'),
      error: (texto: string) => mostrar(texto, 'error'),
    }),
    [mostrar],
  );

  return (
    <ContextoAvisos.Provider value={valor}>
      {children}
      <div className="pila-avisos" aria-live="polite">
        {avisos.map((aviso) => (
          <div key={aviso.id} className={`aviso ${aviso.tipo}`}>
            {aviso.tipo === 'exito' ? <IconoCheck tamano={17} /> : <IconoAlerta tamano={17} />}
            <div style={{ flex: 1 }}>{aviso.texto}</div>
            <button
              type="button"
              className="boton discreto chico"
              aria-label="Cerrar aviso"
              onClick={() => cerrar(aviso.id)}
            >
              <IconoCerrar tamano={14} />
            </button>
          </div>
        ))}
      </div>
    </ContextoAvisos.Provider>
  );
}

export function useAvisos(): ValorAvisos {
  const valor = useContext(ContextoAvisos);
  if (!valor) throw new Error('useAvisos debe usarse dentro de ProveedorAvisos.');
  return valor;
}
