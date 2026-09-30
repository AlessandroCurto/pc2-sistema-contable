import type { Caso } from '../dominio/tipos';
import { construirLibroDiario } from '../dominio/libroDiario';
import { construirLibroMayor } from '../dominio/libroMayor';
import { construirBalanceComprobacion } from '../dominio/balanceComprobacion';
import { construirEstadoResultados } from '../dominio/estadoResultados';
import { construirBalanceGeneral } from '../dominio/balanceGeneral';
import { formatearFecha, formatearNumero } from '../dominio/formato';
import { esCero } from '../dominio/numeros';
import { nombreDeArchivo } from './archivos';

export type SeccionReporte =
  | 'libroDiario'
  | 'libroMayor'
  | 'balanceComprobacion'
  | 'estadoResultados'
  | 'balanceGeneral';

export const SECCIONES: { id: SeccionReporte; etiqueta: string }[] = [
  { id: 'libroDiario', etiqueta: 'Libro Diario' },
  { id: 'libroMayor', etiqueta: 'Libro Mayor' },
  { id: 'balanceComprobacion', etiqueta: 'Balance de Comprobación' },
  { id: 'estadoResultados', etiqueta: 'Estado de Resultados' },
  { id: 'balanceGeneral', etiqueta: 'Balance General' },
];

export interface OpcionesReporte {
  nombreEmpresa?: string;
  secciones: SeccionReporte[];
}

const NEGRO: [number, number, number] = [17, 17, 17];
const GRIS: [number, number, number] = [241, 244, 248];
const AMARILLO: [number, number, number] = [242, 194, 0];

/**
 * Arma el reporte completo en PDF. jsPDF se carga solo cuando hace falta,
 * para que la app abra rápido.
 */
export async function generarReportePdf(caso: Caso, opciones: OpcionesReporte): Promise<Blob> {
  const [{ jsPDF }, autoTableModulo] = await Promise.all([import('jspdf'), import('jspdf-autotable')]);
  const autoTable = autoTableModulo.default;

  const documento = new jsPDF({ orientation: 'portrait', unit: 'pt', format: 'a4' });
  const anchoPagina = documento.internal.pageSize.getWidth();
  const empresa = (opciones.nombreEmpresa ?? '').trim() || caso.empresa.nombre;
  const simbolo = caso.empresa.simboloMoneda;
  const periodo =
    caso.empresa.periodoInicio && caso.empresa.periodoFin
      ? `Del ${formatearFecha(caso.empresa.periodoInicio)} al ${formatearFecha(caso.empresa.periodoFin)}`
      : 'Período no definido';

  let cursor = 0;

  function titulo(texto: string) {
    if (cursor > 0) documento.addPage();
    documento.setFillColor(...NEGRO);
    documento.rect(0, 0, anchoPagina, 58, 'F');
    documento.setTextColor(255, 255, 255);
    documento.setFontSize(15);
    documento.text(texto, 40, 27);
    documento.setFontSize(9);
    documento.text(`${empresa} · ${periodo} · Importes en ${simbolo}`, 40, 44);
    documento.setTextColor(20, 24, 31);
    cursor = 80;
  }

  function tabla(cabeza: string[][], cuerpo: (string | number)[][], anchos?: Record<number, number>) {
    autoTable(documento, {
      head: cabeza,
      body: cuerpo,
      startY: cursor,
      margin: { left: 40, right: 40 },
      styles: { fontSize: 8.5, cellPadding: 4, overflow: 'linebreak' },
      headStyles: { fillColor: NEGRO, textColor: AMARILLO, fontSize: 8.5 },
      alternateRowStyles: { fillColor: GRIS },
      columnStyles: anchos
        ? Object.fromEntries(
            Object.entries(anchos).map(([indice, ancho]) => [indice, { cellWidth: ancho }]),
          )
        : undefined,
      didDrawPage: (datos) => {
        cursor = datos.cursor?.y ?? cursor;
      },
    });
    const conAuto = documento as unknown as { lastAutoTable?: { finalY: number } };
    cursor = (conAuto.lastAutoTable?.finalY ?? cursor) + 22;
  }

  // Portada
  documento.setFillColor(...NEGRO);
  documento.rect(0, 0, anchoPagina, 200, 'F');
  documento.setTextColor(255, 255, 255);
  documento.setFontSize(26);
  documento.text('Reporte Financiero Completo', 40, 96);
  documento.setFontSize(13);
  documento.text(empresa, 40, 124);
  documento.setFontSize(10);
  documento.text(caso.empresa.ruc ? `RUC ${caso.empresa.ruc}` : 'Sin RUC registrado', 40, 144);
  documento.text(periodo, 40, 160);
  documento.setTextColor(20, 24, 31);
  documento.setFontSize(10);
  documento.text(
    `Generado el ${formatearFecha(new Date().toISOString().slice(0, 10))} con Contabilidad UNI.`,
    40,
    240,
  );
  documento.text(
    `Contenido: ${SECCIONES.filter((seccion) => opciones.secciones.includes(seccion.id))
      .map((seccion) => seccion.etiqueta)
      .join(', ')}.`,
    40,
    258,
    { maxWidth: anchoPagina - 80 },
  );
  cursor = 300;

  if (opciones.secciones.includes('libroDiario')) {
    const diario = construirLibroDiario(caso);
    titulo('Libro Diario');
    const cuerpo: (string | number)[][] = [];
    for (const item of diario.asientos) {
      for (const [indice, fila] of item.filas.entries()) {
        cuerpo.push([
          indice === 0 ? `#${item.asiento.numero}` : '',
          indice === 0 ? formatearFecha(item.asiento.fecha) : '',
          `${fila.cuenta?.codigo ?? ''} ${fila.cuenta?.nombre ?? ''}`.trim(),
          indice === 0 ? item.asiento.glosa : '',
          fila.debe ? formatearNumero(fila.debe) : '',
          fila.haber ? formatearNumero(fila.haber) : '',
        ]);
      }
      cuerpo.push([
        '',
        '',
        'Totales del asiento',
        '',
        formatearNumero(item.totalDebe),
        formatearNumero(item.totalHaber),
      ]);
    }
    cuerpo.push([
      '',
      '',
      'TOTAL GENERAL',
      '',
      formatearNumero(diario.totalDebe),
      formatearNumero(diario.totalHaber),
    ]);
    tabla([['N.º', 'Fecha', 'Cuenta', 'Glosa', 'Debe', 'Haber']], cuerpo, {
      0: 34,
      1: 58,
      4: 70,
      5: 70,
    });
  }

  if (opciones.secciones.includes('libroMayor')) {
    const mayor = construirLibroMayor(caso);
    titulo('Libro Mayor');
    for (const grupo of mayor.grupos) {
      for (const item of grupo.cuentas) {
        const cuerpo = item.movimientos.map((movimiento) => [
          formatearFecha(movimiento.fecha),
          `#${movimiento.numero}`,
          movimiento.glosa,
          movimiento.debe ? formatearNumero(movimiento.debe) : '',
          movimiento.haber ? formatearNumero(movimiento.haber) : '',
          formatearNumero(movimiento.saldo),
        ]);
        cuerpo.push([
          'Totales',
          '',
          item.naturalezaSaldo === 'DEUDOR' ? 'Saldo deudor' : 'Saldo acreedor',
          formatearNumero(item.totalDebe),
          formatearNumero(item.totalHaber),
          formatearNumero(item.saldo),
        ]);
        tabla(
          [[`${item.cuenta.codigo} — ${item.cuenta.nombre} (${grupo.etiqueta})`, '', '', 'Debe', 'Haber', 'Saldo']],
          cuerpo,
          { 0: 58, 1: 34, 3: 66, 4: 66, 5: 66 },
        );
      }
    }
  }

  if (opciones.secciones.includes('balanceComprobacion')) {
    const balance = construirBalanceComprobacion(caso);
    titulo('Balance de Comprobación');
    const cuerpo = balance.filas.map((fila) => [
      fila.cuenta.codigo,
      fila.cuenta.nombre,
      formatearNumero(fila.sumaDebe),
      formatearNumero(fila.sumaHaber),
      fila.saldoDeudor ? formatearNumero(fila.saldoDeudor) : '',
      fila.saldoAcreedor ? formatearNumero(fila.saldoAcreedor) : '',
    ]);
    cuerpo.push([
      '',
      'TOTALES',
      formatearNumero(balance.totalDebe),
      formatearNumero(balance.totalHaber),
      formatearNumero(balance.totalDeudor),
      formatearNumero(balance.totalAcreedor),
    ]);
    tabla(
      [['Código', 'Cuenta', 'Suma Debe', 'Suma Haber', 'Saldo Deudor', 'Saldo Acreedor']],
      cuerpo,
      { 0: 50 },
    );
    documento.setFontSize(10);
    documento.text(
      balance.cuadrado
        ? 'El balance de comprobación está cuadrado.'
        : 'Atención: el balance de comprobación no está cuadrado.',
      40,
      cursor,
    );
    cursor += 20;
  }

  if (opciones.secciones.includes('estadoResultados')) {
    const estado = construirEstadoResultados(caso);
    titulo('Estado de Resultados');
    const cuerpo = estado.filas
      .filter((fila) => fila.clase !== 'detalle' || !esCero(fila.monto))
      .map((fila) => [
        `${fila.signo === '-' ? '(-) ' : ''}${fila.etiqueta}`,
        formatearNumero(fila.monto),
      ]);
    tabla([['Concepto', `Importe (${simbolo})`]], cuerpo, { 1: 110 });
  }

  if (opciones.secciones.includes('balanceGeneral')) {
    const general = construirBalanceGeneral(caso);
    titulo('Balance General');
    const cuerpo: (string | number)[][] = [];
    const bloques = [
      general.activoCorriente,
      general.activoNoCorriente,
      general.pasivoCorriente,
      general.pasivoNoCorriente,
      general.patrimonio,
    ];
    for (const bloque of bloques) {
      if (bloque.cuentas.length === 0) continue;
      cuerpo.push([bloque.etiqueta.toUpperCase(), '', '']);
      for (const detalle of bloque.cuentas) {
        cuerpo.push([detalle.cuenta.codigo, detalle.cuenta.nombre, formatearNumero(detalle.monto)]);
      }
      cuerpo.push(['', `Total ${bloque.etiqueta.toLowerCase()}`, formatearNumero(bloque.total)]);
    }
    cuerpo.push([
      '',
      general.resultadoNetoDeImpuesto
        ? 'Resultado del ejercicio (neto de impuesto)'
        : 'Resultado del ejercicio (antes de impuesto)',
      formatearNumero(general.resultadoEjercicio),
    ]);
    cuerpo.push(['', 'TOTAL ACTIVO', formatearNumero(general.totalActivo)]);
    cuerpo.push(['', 'TOTAL PASIVO', formatearNumero(general.totalPasivo)]);
    cuerpo.push(['', 'TOTAL PATRIMONIO', formatearNumero(general.totalPatrimonio)]);
    cuerpo.push([
      '',
      'TOTAL PASIVO + PATRIMONIO',
      formatearNumero(general.totalPasivoPatrimonio),
    ]);
    tabla([['Código', 'Concepto', `Importe (${simbolo})`]], cuerpo, { 0: 60, 2: 110 });
    documento.setFontSize(10);
    documento.text(
      general.cuadrado
        ? 'Sí cumple: Total Activo = Total Pasivo + Total Patrimonio.'
        : 'Atención: la ecuación contable no cierra.',
      40,
      cursor,
    );
  }

  // Numeración de páginas
  const totalPaginas = documento.getNumberOfPages();
  for (let pagina = 1; pagina <= totalPaginas; pagina += 1) {
    documento.setPage(pagina);
    documento.setFontSize(8);
    documento.setTextColor(120, 127, 138);
    documento.text(
      `Contabilidad UNI · ${empresa} · Página ${pagina} de ${totalPaginas}`,
      40,
      documento.internal.pageSize.getHeight() - 20,
    );
  }

  return documento.output('blob');
}

export function nombreReporte(caso: Caso): string {
  return nombreDeArchivo(`reporte-financiero-${caso.nombre}`, 'pdf');
}
