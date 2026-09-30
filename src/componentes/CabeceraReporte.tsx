import type { ReactNode } from 'react';
import type { Caso } from '../dominio/tipos';
import { formatearFecha } from '../dominio/formato';
import { Boton } from './ui';
import { IconoImprimir } from './Iconos';

export function CabeceraReporte({
  caso,
  titulo,
  acciones,
}: {
  caso: Caso;
  titulo: string;
  acciones?: ReactNode;
}) {
  const periodo =
    caso.empresa.periodoInicio && caso.empresa.periodoFin
      ? `Del ${formatearFecha(caso.empresa.periodoInicio)} al ${formatearFecha(caso.empresa.periodoFin)}`
      : 'Período no definido';

  return (
    <header className="cabecera-reporte">
      <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 220 }}>
          <h2>{titulo}</h2>
          <div className="datos">
            <span>{caso.empresa.nombre}</span>
            {caso.empresa.ruc && <span>RUC {caso.empresa.ruc}</span>}
            <span>{periodo}</span>
            <span>Expresado en {caso.empresa.simboloMoneda}</span>
          </div>
        </div>
        <div className="lista-acciones no-imprimir">
          {acciones}
          <Boton
            variante="secundario"
            icono={<IconoImprimir tamano={16} />}
            onClick={() => window.print()}
          >
            Imprimir
          </Boton>
        </div>
      </div>
    </header>
  );
}
