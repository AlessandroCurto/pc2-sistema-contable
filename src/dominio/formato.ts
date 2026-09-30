import { redondear } from './numeros';

const formateador = new Intl.NumberFormat('es-PE', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** 1234.5 -> "1,234.50" */
export function formatearNumero(valor: number): string {
  return formateador.format(redondear(valor));
}

/** 1234.5 -> "S/ 1,234.50". El símbolo viene de la configuración del caso. */
export function formatearMoneda(valor: number, simbolo = 'S/'): string {
  const absoluto = Math.abs(redondear(valor));
  const signo = redondear(valor) < 0 ? '-' : '';
  return `${signo}${simbolo} ${formateador.format(absoluto)}`;
}

/** "2024-10-01" -> "01/10/2024". Sin zona horaria: se parte el texto. */
export function formatearFecha(iso: string): string {
  const partes = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso ?? '');
  if (!partes) return iso ?? '';
  return `${partes[3]}/${partes[2]}/${partes[1]}`;
}

export function formatearFechaLarga(iso: string): string {
  const partes = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso ?? '');
  if (!partes) return iso ?? '';
  const meses = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'setiembre', 'octubre', 'noviembre', 'diciembre',
  ];
  const mes = meses[Number(partes[2]) - 1] ?? partes[2];
  return `${Number(partes[3])} de ${mes} de ${partes[1]}`;
}

export function hoyISO(): string {
  const ahora = new Date();
  const mes = String(ahora.getMonth() + 1).padStart(2, '0');
  const dia = String(ahora.getDate()).padStart(2, '0');
  return `${ahora.getFullYear()}-${mes}-${dia}`;
}
