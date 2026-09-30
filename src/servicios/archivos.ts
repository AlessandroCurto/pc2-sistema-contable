import type { Caso } from '../dominio/tipos';

/** Descarga un contenido como archivo desde el navegador. */
export function descargar(nombre: string, contenido: Blob | string, tipo = 'application/json'): void {
  const blob = contenido instanceof Blob ? contenido : new Blob([contenido], { type: tipo });
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement('a');
  enlace.href = url;
  enlace.download = nombre;
  document.body.appendChild(enlace);
  enlace.click();
  document.body.removeChild(enlace);
  URL.revokeObjectURL(url);
}

export function nombreDeArchivo(base: string, extension: string): string {
  const limpio = base
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase();
  const fecha = new Date().toISOString().slice(0, 10);
  return `${limpio || 'caso'}-${fecha}.${extension}`;
}

export function exportarCasoJson(caso: Caso): void {
  descargar(nombreDeArchivo(caso.nombre, 'json'), JSON.stringify(caso, null, 2));
}

export function leerArchivoJson(archivo: File): Promise<unknown> {
  return new Promise((resolver, rechazar) => {
    const lector = new FileReader();
    lector.onerror = () => rechazar(new Error('No se pudo leer el archivo.'));
    lector.onload = () => {
      try {
        resolver(JSON.parse(String(lector.result)));
      } catch {
        rechazar(new Error('El archivo no contiene un JSON válido.'));
      }
    };
    lector.readAsText(archivo);
  });
}

/** Exporta cualquier tabla a CSV, con separador ';' para que Excel en español lo abra bien. */
export function exportarCsv(nombre: string, filas: (string | number)[][]): void {
  const texto = filas
    .map((fila) =>
      fila
        .map((celda) => {
          const valor = String(celda ?? '');
          return /[";\n]/.test(valor) ? `"${valor.replace(/"/g, '""')}"` : valor;
        })
        .join(';'),
    )
    .join('\r\n');
  descargar(nombre, `﻿${texto}`, 'text/csv;charset=utf-8');
}
