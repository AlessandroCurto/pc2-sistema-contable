import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useAlmacen } from '../almacen/almacen';
import { MENU } from '../componentes/navegacion';
import { Boton, EstadoVacio, Indicador, MarcaCuadre, Tarjeta } from '../componentes/ui';
import { construirBalanceComprobacion } from '../dominio/balanceComprobacion';
import { construirEstadoResultados } from '../dominio/estadoResultados';
import { construirBalanceGeneral } from '../dominio/balanceGeneral';
import { ordenarAsientos, resumirAsiento } from '../dominio/asientos';
import { formatearFecha, formatearMoneda } from '../dominio/formato';
import { IconoCasos } from '../componentes/Iconos';

const ACCESOS = [
  '/plan-de-cuentas',
  '/asientos',
  '/balance-comprobacion',
  '/estado-resultados',
  '/libro-diario',
  '/libro-mayor',
  '/balance-general',
  '/reporte',
];

export function Inicio() {
  const { casoActivo, casos, cargando } = useAlmacen();

  const resumen = useMemo(() => {
    if (!casoActivo) return null;
    return {
      balance: construirBalanceComprobacion(casoActivo),
      estado: construirEstadoResultados(casoActivo),
      general: construirBalanceGeneral(casoActivo),
      ultimos: ordenarAsientos(casoActivo.asientos).slice(-5).reverse(),
    };
  }, [casoActivo]);

  if (cargando) return null;

  if (!casoActivo) {
    return (
      <Tarjeta>
        <EstadoVacio
          titulo="Bienvenido a Contabilidad UNI"
          descripcion={
            casos.length === 0
              ? 'Crea un caso con la empresa del enunciado, registra sus asientos y el sistema arma el libro diario, el libro mayor, el balance de comprobación, el estado de resultados y el balance general.'
              : 'Tienes casos guardados, pero ninguno abierto. Abre uno desde la pantalla de Casos.'
          }
          accion={
            <Link to="/casos">
              <Boton icono={<IconoCasos tamano={16} />}>Ir a Casos</Boton>
            </Link>
          }
        />
      </Tarjeta>
    );
  }

  const simbolo = casoActivo.empresa.simboloMoneda;

  return (
    <>
      <Tarjeta
        titulo={casoActivo.empresa.nombre}
        subtitulo={
          casoActivo.empresa.periodoInicio && casoActivo.empresa.periodoFin
            ? `Período del ${formatearFecha(casoActivo.empresa.periodoInicio)} al ${formatearFecha(
                casoActivo.empresa.periodoFin,
              )}`
            : 'Define el período en Configuración para que aparezca en los reportes.'
        }
        acciones={
          <Link to="/casos">
            <Boton variante="secundario">Cambiar de caso</Boton>
          </Link>
        }
      >
        <div className="rejilla rejilla-4">
          <Indicador etiqueta="Cuentas" valor={casoActivo.cuentas.length} pie="en el plan de cuentas" />
          <Indicador etiqueta="Asientos" valor={casoActivo.asientos.length} pie="en el libro diario" />
          <Indicador
            etiqueta="Total movido"
            valor={formatearMoneda(resumen?.balance.totalDebe ?? 0, simbolo)}
            pie="suma del Debe"
          />
          <Indicador
            etiqueta="Utilidad neta"
            valor={formatearMoneda(resumen?.estado.utilidadNeta ?? 0, simbolo)}
            color={
              (resumen?.estado.utilidadNeta ?? 0) >= 0 ? 'var(--verde-600)' : 'var(--rojo-600)'
            }
            pie={`impuesto ${resumen?.estado.tasaImpuesto ?? 0}%`}
          />
        </div>

        {casoActivo.asientos.length > 0 && resumen && (
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 16 }}>
            <MarcaCuadre
              cuadrado={resumen.balance.cuadrado}
              textoOk="Balance de comprobación cuadrado."
              textoMal="Balance de comprobación descuadrado."
            />
            <MarcaCuadre
              cuadrado={resumen.general.cuadrado}
              textoOk="Ecuación contable verificada: Activo = Pasivo + Patrimonio."
              textoMal="La ecuación contable no cierra."
            />
          </div>
        )}
      </Tarjeta>

      <Tarjeta titulo="Acciones rápidas">
        <div className="rejilla-accesos">
          {ACCESOS.map((ruta) => {
            const entrada = MENU.find((item) => item.ruta === ruta);
            if (!entrada) return null;
            return (
              <Link key={ruta} to={ruta} className="acceso centrado">
                <span className="acceso-icono">{entrada.icono}</span>
                <span>
                  <strong>{entrada.etiqueta}</strong>
                  <span>{entrada.descripcion}</span>
                </span>
              </Link>
            );
          })}
        </div>
      </Tarjeta>

      <Tarjeta
        titulo="Últimos asientos registrados"
        acciones={
          <Link to="/libro-diario">
            <Boton chico variante="secundario">
              Ver libro diario
            </Boton>
          </Link>
        }
        sinEspacio
      >
        {!resumen || resumen.ultimos.length === 0 ? (
          <EstadoVacio
            titulo="Sin asientos todavía"
            descripcion="Registra el primer asiento para ver aquí el movimiento del caso."
            accion={
              <Link to="/asientos">
                <Boton>Registrar asiento</Boton>
              </Link>
            }
          />
        ) : (
          <div className="tabla-envoltorio">
            <table className="tabla">
              <thead>
                <tr>
                  <th style={{ width: 70 }}>N.º</th>
                  <th style={{ width: 120 }}>Fecha</th>
                  <th>Glosa</th>
                  <th className="numero" style={{ width: 90 }}>
                    Líneas
                  </th>
                  <th className="numero" style={{ width: 180 }}>
                    Importe
                  </th>
                </tr>
              </thead>
              <tbody>
                {resumen.ultimos.map((asiento) => (
                  <tr key={asiento.id}>
                    <td className="codigo">#{asiento.numero}</td>
                    <td>{formatearFecha(asiento.fecha)}</td>
                    <td>{asiento.glosa || <span className="atenuado">Sin glosa</span>}</td>
                    <td className="numero">{asiento.lineas.length}</td>
                    <td className="numero">
                      {formatearMoneda(resumirAsiento(asiento.lineas).totalDebe, simbolo)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Tarjeta>
    </>
  );
}
