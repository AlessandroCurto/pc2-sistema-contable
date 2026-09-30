import { useState } from 'react';
import { useAlmacen } from '../almacen/almacen';
import { useAvisos } from '../componentes/Avisos';
import { Aviso, Boton, Campo, Tarjeta } from '../componentes/ui';
import { IconoCorreo, IconoPdf } from '../componentes/Iconos';
import { SECCIONES, generarReportePdf, nombreReporte, type SeccionReporte } from '../servicios/pdf';
import { descargar } from '../servicios/archivos';

const CORREO_VALIDO = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export function ReportePdf() {
  const { casoActivo } = useAlmacen();
  const avisos = useAvisos();

  const [nombreEmpresa, setNombreEmpresa] = useState('');
  const [correo, setCorreo] = useState('');
  const [errorCorreo, setErrorCorreo] = useState('');
  const [secciones, setSecciones] = useState<SeccionReporte[]>(
    SECCIONES.map((seccion) => seccion.id),
  );
  const [generando, setGenerando] = useState(false);
  const [generado, setGenerado] = useState(false);

  if (!casoActivo) return null;

  function alternar(id: SeccionReporte) {
    setSecciones((actuales) =>
      actuales.includes(id) ? actuales.filter((item) => item !== id) : [...actuales, id],
    );
    setGenerado(false);
  }

  async function generar(): Promise<boolean> {
    if (!casoActivo) return false;
    if (secciones.length === 0) {
      avisos.error('Elige al menos un reporte para incluir en el PDF.');
      return false;
    }
    setGenerando(true);
    try {
      const blob = await generarReportePdf(casoActivo, {
        nombreEmpresa,
        secciones: SECCIONES.filter((seccion) => secciones.includes(seccion.id)).map(
          (seccion) => seccion.id,
        ),
      });
      descargar(nombreReporte(casoActivo), blob, 'application/pdf');
      setGenerado(true);
      avisos.exito('PDF generado y descargado.');
      return true;
    } catch (error) {
      avisos.error(
        error instanceof Error ? `No se pudo generar el PDF: ${error.message}` : 'No se pudo generar el PDF.',
      );
      return false;
    } finally {
      setGenerando(false);
    }
  }

  async function generarYEnviar() {
    if (!CORREO_VALIDO.test(correo.trim())) {
      setErrorCorreo('Escribe un correo electrónico válido.');
      return;
    }
    setErrorCorreo('');
    const ok = await generar();
    if (!ok || !casoActivo) return;
    const empresa = nombreEmpresa.trim() || casoActivo.empresa.nombre;
    const asunto = encodeURIComponent(`Reporte financiero - ${empresa}`);
    const cuerpo = encodeURIComponent(
      [
        `Adjunto el reporte financiero de ${empresa} generado con Contabilidad UNI.`,
        '',
        `Incluye: ${SECCIONES.filter((seccion) => secciones.includes(seccion.id))
          .map((seccion) => seccion.etiqueta)
          .join(', ')}.`,
        '',
        'El archivo PDF se acaba de descargar en esta computadora. Adjúntalo a este correo antes de enviarlo.',
      ].join('\n'),
    );
    window.location.href = `mailto:${correo.trim()}?subject=${asunto}&body=${cuerpo}`;
    avisos.mostrar('Se abrió tu programa de correo. Adjunta el PDF descargado.', 'info');
  }

  return (
    <>
      <Tarjeta
        titulo="Generar Reporte Completo"
        subtitulo="Reúne los reportes elegidos en un solo archivo PDF listo para imprimir o enviar."
      >
        <div className="fila-campos">
          <div style={{ gridColumn: 'span 2' }}>
            <Campo
              etiqueta="Nombre de la empresa en el PDF"
              ayuda={`Si lo dejas vacío se usa "${casoActivo.empresa.nombre}".`}
              htmlFor="empresa-pdf"
            >
              <input
                id="empresa-pdf"
                type="text"
                value={nombreEmpresa}
                placeholder={casoActivo.empresa.nombre}
                onChange={(evento) => setNombreEmpresa(evento.target.value)}
              />
            </Campo>
          </div>
        </div>

        <fieldset
          style={{
            border: '1px solid var(--gris-200)',
            borderRadius: 'var(--radio-chico)',
            padding: 14,
            marginTop: 16,
          }}
        >
          <legend style={{ fontSize: 12.5, fontWeight: 600, padding: '0 6px' }}>
            Reportes incluidos
          </legend>
          <div className="rejilla rejilla-3">
            {SECCIONES.map((seccion) => (
              <label key={seccion.id} className="casilla">
                <input
                  type="checkbox"
                  checked={secciones.includes(seccion.id)}
                  onChange={() => alternar(seccion.id)}
                />
                <span>{seccion.etiqueta}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="lista-acciones" style={{ marginTop: 16 }}>
          <Boton
            icono={<IconoPdf tamano={16} />}
            cargando={generando}
            onClick={() => void generar()}
          >
            {generando ? 'Generando PDF…' : 'Generar y descargar PDF'}
          </Boton>
        </div>

        {generando && (
          <div style={{ marginTop: 14 }}>
            <div className="barra-progreso">
              <div style={{ width: '70%' }} />
            </div>
            <p className="atenuado" style={{ fontSize: 12.5, marginTop: 6 }}>
              Armando las tablas del reporte…
            </p>
          </div>
        )}

        {generado && !generando && (
          <div style={{ marginTop: 14 }}>
            <Aviso tipo="exito">
              El PDF se descargó con el nombre <strong>{nombreReporte(casoActivo)}</strong>.
            </Aviso>
          </div>
        )}
      </Tarjeta>

      <Tarjeta
        titulo="Enviar por correo"
        subtitulo="Contabilidad UNI funciona sin servidor, así que el envío se hace desde tu propio programa de correo."
      >
        <div className="fila-campos">
          <div style={{ gridColumn: 'span 2' }}>
            <Campo etiqueta="Correo electrónico de destino" error={errorCorreo} htmlFor="correo">
              <input
                id="correo"
                type="email"
                value={correo}
                placeholder="ejemplo@gmail.com"
                className={errorCorreo ? 'con-error' : ''}
                onChange={(evento) => {
                  setCorreo(evento.target.value);
                  setErrorCorreo('');
                }}
              />
            </Campo>
          </div>
        </div>

        <div className="lista-acciones" style={{ marginTop: 14 }}>
          <Boton
            variante="secundario"
            icono={<IconoCorreo tamano={16} />}
            cargando={generando}
            onClick={() => void generarYEnviar()}
          >
            Generar y preparar el correo
          </Boton>
        </div>

        <div style={{ marginTop: 14 }}>
          <Aviso tipo="info">
            Se descarga el PDF y se abre tu programa de correo con el asunto y el mensaje ya escritos.
            Solo falta adjuntar el archivo descargado. Un envío automático necesitaría un servidor;
            esta aplicación se publica como página estática.
          </Aviso>
        </div>
      </Tarjeta>
    </>
  );
}
