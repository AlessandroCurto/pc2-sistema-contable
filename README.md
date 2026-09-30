# ContaSys — Aplicativo de un Sistema Contable

Aplicación web que automatiza el ciclo contable completo: se registran los asientos de
cualquier caso y el sistema arma el **Libro Diario**, el **Libro Mayor**, el **Balance de
Comprobación**, el **Estado de Resultados** y el **Balance General**, además de un
**reporte en PDF**.

El sistema es **genérico**: no tiene ningún caso escrito en el código. La empresa, el plan
de cuentas, el período y la tasa del impuesto a la renta se cargan desde la interfaz, así
que sirve para cualquier enunciado.

## Cómo se usa (ruta rápida para probarlo)

1. Abrir la aplicación.
2. Entrar a **Casos** y pulsar **Cargar** en uno de los casos de ejemplo, o **Nuevo caso**
   para escribir uno propio.
3. En **Plan de Cuentas**, crear o ajustar las cuentas (código, nombre, tipo y clasificación).
4. En **Registrar Asiento**, cargar cada operación del enunciado. El asiento solo se guarda
   si el Debe iguala al Haber.
5. Revisar **Libro Diario**, **Libro Mayor**, **Balance de Comprobación**, **Estado de
   Resultados** y **Balance General**.
6. En **Generar PDF / Enviar**, descargar todo en un solo archivo.

## Ejecutar en local

Necesitas Node.js 20 o superior.

```bash
npm install
npm run dev       # abre http://localhost:5173
```

Otros comandos:

```bash
npm run test      # pruebas automáticas (motor contable + flujo de la interfaz)
npm run lint      # revisión del código
npm run build     # compilación de producción en dist/
npm run preview   # sirve lo compilado
npm run verificar # lint + pruebas + compilación
```

## Publicación

El proyecto se publica como **página estática en GitHub Pages** desde este mismo
repositorio. Cada push a `main` ejecuta `.github/workflows/deploy.yml`, que corre el lint y
las pruebas, compila y publica. Para activarlo una sola vez:
**Settings → Pages → Build and deployment → Source: GitHub Actions**.

## Arquitectura

No hay servidor ni base de datos: todo corre en el navegador y los datos se guardan en
`localStorage`. Esa decisión permite publicar la app como página estática y que el profesor
la abra desde un enlace, sin instalar nada.

```
src/
  dominio/      Motor contable puro (sin React): tipos, validaciones y los cinco reportes
  almacen/      Estado de la aplicación y persistencia en localStorage
  datos/        Plantillas de plan de cuentas y casos de ejemplo (solo datos)
  componentes/  Piezas de interfaz reutilizables (tarjetas, botones, campos, avisos)
  paginas/      Pantallas completas
  servicios/    PDF, CSV y manejo de archivos
tests/          Pruebas del motor contable y del flujo de la interfaz
```

Reglas que se respetan en todo el proyecto:

- `src/dominio/` no importa React ni toca el navegador: son funciones puras y se prueban solas.
- Las páginas nunca calculan contabilidad; llaman a las funciones del dominio.
- Los casos de ejemplo viven en `src/datos/`. **Ningún reporte depende de ellos.**

### Modelo de datos

| Concepto | Contenido |
| --- | --- |
| `Caso` | empresa + plan de cuentas + asientos. Se puede exportar e importar en JSON. |
| `Cuenta` | código, nombre, tipo (`ACTIVO`, `PASIVO`, `PATRIMONIO`, `INGRESO`, `GASTO`) y clasificación para los reportes. |
| `Asiento` | número correlativo, fecha, glosa y sus líneas. |
| `LineaAsiento` | cuenta, importe al Debe e importe al Haber. |

La clasificación de cada cuenta decide dónde aparece:

- Activo y pasivo: **corriente** o **no corriente** (Balance General).
- Ingresos y gastos: ventas, devoluciones, descuentos, costo de ventas, gasto de ventas,
  gasto de administración, ingresos y gastos financieros, otros ingresos y otros gastos
  (Estado de Resultados).

### Cómo se calcula cada reporte

- **Libro Diario**: los asientos en orden cronológico; a igual fecha manda el correlativo.
- **Libro Mayor**: agrupa los movimientos por cuenta y por tipo, con saldo acumulado y
  naturaleza (deudor o acreedor).
- **Balance de Comprobación**: sumas del Debe y del Haber por cuenta, más el saldo neto.
  Está cuadrado cuando coinciden los totales de sumas y de saldos.
- **Estado de Resultados**: ventas netas, utilidad bruta, utilidad operativa, resultado
  antes de impuestos, impuesto a la renta y utilidad neta.
- **Balance General**: activo frente a pasivo más patrimonio. El resultado del ejercicio
  sale del Estado de Resultados y se suma al patrimonio, porque las cuentas de ingreso y
  gasto se cierran contra él.

## Qué se puede configurar sin tocar el código

- Casos completos: crear, duplicar, exportar e importar en JSON.
- Plan de cuentas: crear, editar y eliminar cuentas (no se deja eliminar una cuenta con
  movimientos). Hay tres plantillas iniciales: PCGE simplificado, numeración por grupos y
  plan vacío.
- Datos de la empresa: razón social, RUC, período, símbolo de moneda.
- Tasa del impuesto a la renta.
- Si el impuesto a la renta afecta o no al patrimonio en el Balance General.
- Qué reportes entran en el PDF.

## Modos de registro

- **Debe / Haber**: el modo normal, con una línea por cuenta.
- **Signo (+ / −)**: el modo de la primera versión mostrada en clase. Un `+` aumenta la
  cuenta y un `−` la disminuye; el sistema decide solo si el movimiento va al Debe o al
  Haber según el tipo de cuenta. Los dos modos guardan exactamente el mismo asiento.

## Casos de ejemplo incluidos

| Caso | Para qué sirve |
| --- | --- |
| **CYBERTEC S.A.** | Constitución, compra de mercadería, venta al contado y ajuste del costo de ventas. Balance de comprobación de 100,000 y utilidad neta de 10,000. |
| **Comercializadora Metropolitana** | Saldos iniciales, compra con letras e IGV, venta mixta, arriendo, pagos y cobros. Balance de comprobación de 9,168,776.00, utilidad neta de 105,016.80 con 30% de impuesto y balance general de 7,126,024.00. |

Las pruebas automáticas comprueban esas cifras, así que cualquier cambio que rompa el
motor contable se detecta al correr `npm run test`.

## Supuestos que se tomaron

Las diapositivas no especificaban todo. Estas son las decisiones que se tomaron y por qué:

1. **Sin servidor.** El requisito era publicar la página desde el repositorio, así que la
   aplicación es estática y guarda los datos en el navegador. Para mover un caso a otra
   computadora se exporta e importa el JSON.
2. **El envío del PDF por correo se hace desde el programa de correo del usuario.** Un
   envío automático necesitaría un servidor de correo. La app genera el PDF, lo descarga y
   abre el correo con el asunto y el mensaje ya escritos para adjuntarlo.
3. **El impuesto a la renta es un cálculo del reporte, no un asiento.** Por eso, por
   omisión, el patrimonio del Balance General usa el resultado **antes** de impuestos y la
   ecuación contable cierra. Hay una opción en Configuración para lo contrario.
4. **Los saldos se muestran en positivo con su naturaleza indicada** (deudor o acreedor).
   En la exposición original algunos totales salían negativos; aquí se corrigió el signo y
   la ecuación contable se verifica de forma explícita.
5. **El correlativo de los asientos se recalcula** al agregar o eliminar, para que el libro
   diario quede siempre numerado de forma cronológica.
6. **Un asiento necesita al menos dos líneas** y cada línea lleva importe en el Debe o en
   el Haber, nunca en los dos a la vez.
7. **Las cuentas con movimientos no se pueden eliminar**, para no dejar asientos rotos.
8. **Los importes se redondean a dos decimales** y el cuadre se comprueba con una
   tolerancia de 0.005 para evitar errores de coma flotante.

## Pruebas automáticas

- `tests/motorContable.test.ts`: reproduce las cifras de los dos casos de ejemplo y prueba
  las validaciones, el modo de signo y el redondeo.
- `tests/aplicacion.test.tsx`: abre la aplicación completa, carga un caso, recorre los
  reportes, comprueba que un asiento descuadrado se rechaza y que el caso sobrevive al
  recargar.
