/** Identificadores únicos para cuentas, asientos, líneas y casos. */
export function nuevoId(prefijo = 'id'): string {
  const aleatorio = Math.random().toString(36).slice(2, 10);
  return `${prefijo}-${Date.now().toString(36)}-${aleatorio}`;
}
