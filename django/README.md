# Sistema y Gestión Financiera - versión en Python con Django

La misma aplicación de la carpeta raíz (React + TypeScript), traducida a Python.
Automatiza el ciclo contable completo: plan de cuentas, asientos, Libro Diario,
Libro Mayor, Balance de Comprobación, Estado de Resultados, Balance General y el
reporte en PDF.

No hay un caso escrito en el código: cada enunciado se carga como un **caso**
(empresa, plan de cuentas y asientos), así sirve para cualquier ejercicio.

## Por qué esta versión no vive en GitHub Pages

GitHub Pages entrega archivos: HTML, CSS y JavaScript. Django necesita un
proceso de Python corriendo para responder cada pedido, así que en Pages no
puede funcionar. Por eso:

- La versión de React sigue publicada en Pages, sin cambios.
- Esta versión se corre en la computadora con `runserver` (como en las clases) o
  se despliega en un hosting de Python (`render.yaml` ya viene listo).

## Levantarla en la computadora

```bash
cd django
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py cargar_demo        # tres casos de ejemplo (opcional)
.venv/Scripts/python manage.py runserver
```

Abrir http://127.0.0.1:8000/. En Linux o Mac, `.venv/bin/python` en lugar de
`.venv/Scripts/python`.

Comandos útiles:

| Comando | Para qué |
| --- | --- |
| `manage.py test nucleo` | 154 pruebas: motor contable, pantallas, PDF, Excel e importación |
| `manage.py cargar_demo --borrar` | Borra todo y vuelve a cargar los tres casos de clase |
| `manage.py createsuperuser` | Entrar a `/admin/` y ver las tablas por dentro |

## Cómo está organizado

```
django/
  contabilidad/        configuración del proyecto (settings, urls, wsgi)
  nucleo/
    dominio/           el motor contable: Python puro, no importa Django
    datos/             plantillas de plan de cuentas y los casos de ejemplo
    servicios/         PDF (ReportLab), Excel (pandas) y respaldos JSON
    models.py          Caso, Cuenta, Asiento, LineaAsiento (SQLite)
    forms.py           formularios; la validación la hace el dominio
    views.py           una vista por pantalla
    templates/nucleo/  las pantallas en HTML
    static/nucleo/     el mismo CSS de la versión web
    tests/             las pruebas
```

La regla importante: **`nucleo/dominio/` no importa Django**. Son dataclasses y
funciones puras, igual que `src/dominio/` en la versión de React no importa
React. Los modelos se convierten a esas dataclasses con `a_dominio()`, y los
reportes se calculan siempre ahí. Así las fórmulas se pueden probar solas y son
las mismas que ya estaban verificadas.

Otro cambio de fondo: la plata se lleva en `Decimal` con redondeo
`ROUND_HALF_UP`, no en los números con coma flotante de JavaScript. Dos cuentas
de 0.1 + 0.2 dan exactamente 0.30.

## Qué usa de cada librería

| Librería | Dónde | Para qué |
| --- | --- | --- |
| Django | todo | modelos, formularios, sesiones, plantillas y el panel `/admin/` |
| ReportLab | `servicios/pdf.py` | el PDF de los cinco reportes, con portada y numeración |
| pandas | `servicios/excel.py` | exportar los reportes a Excel e importar asientos de un .xlsx o .csv |
| openpyxl | con pandas | es el motor que escribe y lee los .xlsx |
| WhiteNoise | `settings.py` | sirve el CSS y los iconos sin nginx, para que el despliegue sea directo |
| Anthropic | `servicios/chatbot.py` | el asistente que responde dentro de la aplicación |

El PDF reemplaza a jsPDF y el Excel es nuevo: en el navegador no tenía sentido,
pero con Python una hoja de cálculo sale casi gratis y el profesor suele pedir
los cuadros en Excel.

## El asistente: MULUNI

Abajo a la derecha hay un botón con un burrito que abre una conversación.
El dibujo es `static/nucleo/muluni.svg`, hecho a mano: si algún día se quiere un
render 3D de verdad, se reemplaza ese archivo y nada más.
**Funciona sin conexión a ninguna API y sin costo**: las respuestas se arman en el
servidor (`servicios/asistente.py`). Hace tres cosas:

1. **Resuelve un enunciado pegado.** `servicios/enunciados.py` reconoce el vocabulario
   con el que están escritos estos casos (compra, venta, letras, arriendo, costo de ventas)
   y arma los asientos con `Decimal`, así cuadran al céntimo. Mira hacia atrás cuando hace
   falta: el valor de cada letra sale de la operación que las emitió, el *50% de la deuda*
   del saldo inicial de proveedores, y el costo de ventas de las compras que ya leyó. Un
   botón los registra en el caso, pasando por el mismo `importar_asientos()` que valida la
   importación de Excel. No hace falta preparar nada antes: si al plan de cuentas le faltan
   cuentas las agrega con su tipo y rubro correctos, y si no hay ningún caso abierto lo crea
   con el nombre y el período que saca del propio enunciado. La operación que no reconoce la informa en vez de inventarla, y
   nunca propone un asiento descuadrado.
2. **Revisa el caso abierto con sus cifras reales.** «¿Cómo está mi caso?» devuelve el
   resumen con sus importes; «¿por qué no cuadra?» recorre los asientos y nombra el que
   falla, con su diferencia. Aquí el asistente le gana a un modelo de lenguaje: no estima,
   lee el caso y usa el mismo motor contable que las pantallas.
3. **Cambia de caso.** «Abre el caso CYBERTEC» lo busca por nombre (aunque venga a
   medias), lo abre y recarga la pantalla. Si no existe, lo dice y lista los que hay.
4. **Explica el sistema**: registrar asientos, importar desde Excel, plan de cuentas,
   descargas, configuración y los cinco reportes.
5. **Explica la teoría**: partida doble, qué va al Debe y al Haber, IGV, impuesto a la
   renta, costo de ventas, letras y el ciclo contable. También hace la cuenta si le pasas
   un monto («cuánto es el IGV de 1,000,000 incluido»).

Cuando no reconoce la pregunta **lo dice** y ofrece los temas cercanos; nunca inventa una
respuesta ni un botón que no existe.

La respuesta se escribe mientras llega (Server-Sent Events), no de golpe al final, y la
conversación sobrevive al cambio de pantalla.

### Conectarlo a la API (opcional)

Si algún día se pone la variable `ANTHROPIC_API_KEY` en el panel de Render, las preguntas
que el asistente local **no reconoce** pasan al modelo (`servicios/chatbot.py`), que recibe
el caso abierto como contexto. Las que sí reconoce se siguen respondiendo en el servidor,
así que esa parte nunca cuesta. Si la API falla, queda la respuesta local. El modelo se
elige con `CHATBOT_MODELO` (por omisión `claude-sonnet-5-5`).

Sin esa variable no pasa nada: el asistente funciona completo.

**Tope de gasto.** La página es pública, así que cualquiera que la abra podría gastar
el saldo de la cuenta. El límite por sesión no alcanza, porque basta con borrar las
cookies para empezar otra; por eso hay un **tope diario de todo el sitio**
(`CHATBOT_TOPE_DIARIO`, 150 por omisión) que se lleva en la tabla `UsoAsistente`, una
fila por día. Solo cuenta lo que llega a la API: las preguntas que responde el
asistente local no gastan. Al agotarse el cupo **el asistente no se rompe**: sigue
contestando con lo local, gratis, hasta el día siguiente. Con `CHATBOT_TOPE_DIARIO=0`
la API queda apagada del todo.

Ese tope es el de la aplicación. El tope duro conviene ponerlo además en
console.anthropic.com → Billing → límite de gasto mensual.

Otros límites: 40 preguntas por hora y por sesión, 20 mensajes de historial y
4 000 caracteres por mensaje.

## Reglas del sistema que no cambiaron

- Un asiento se guarda **solo** si el total del Debe iguala al del Haber. Lo
  decide `dominio/asientos.validar_asiento()`, que usan el formulario y la
  importación de Excel.
- Dos formas de llenar una línea: Debe/Haber, o signo (+/-) y monto. Con el
  signo, el lado sale del tipo de la cuenta (`movimiento_desde_signo`).
- El impuesto a la renta se aplica al resultado antes de impuesto solo si es
  positivo. Si en Configuración se marca "el impuesto afecta al patrimonio", el
  Balance General muestra el resultado neto; si no, el resultado antes de
  impuesto.
- Una cuenta con movimientos no se puede eliminar: el sistema dice por qué.

## Importar asientos desde Excel o CSV

En "Registrar Asiento" hay un botón para descargar la plantilla. Las columnas
son `numero`, `fecha`, `glosa`, `codigo`, `debe`, `haber`, y las filas con el
mismo `numero` forman un asiento. También acepta nombres parecidos (`Cargo` y
`Abono` por `debe` y `haber`, `Nro` por `numero`) y fechas en `dd/mm/aaaa` o
`aaaa-mm-dd`.

Cada asiento pasa por la misma revisión de Debe = Haber: los que cuadran entran
y los que no se informan uno por uno, sin dejar nada a medias.

## Publicarla en internet

El archivo `render.yaml` despliega el proyecto en [Render](https://render.com)
con el plan gratuito: entrar con la cuenta de GitHub, **New > Blueprint**, elegir
este repositorio y como ruta poner `django/render.yaml`.

### Dónde se guardan los datos

En Render los casos van en **PostgreSQL** (en Supabase), no en SQLite: el disco
del plan gratuito de Render se borra en cada despliegue y con SQLite se
perderían. La conexión se pasa con la variable `DATABASE_URL`, que se escribe en
el panel de Render (Environment) y **nunca en el repositorio**. Sin
`DATABASE_URL`, la aplicación usa SQLite, que es lo cómodo en la computadora.

Detalles de la base:

- Se entra por el *pooler* de Supabase en modo sesión (puerto 5432), porque
  Render solo tiene IPv4 y la conexión directa de Supabase es IPv6.
- Las tablas viven en el esquema `contabilidad`, con un usuario propio
  (`contabilidad_app`) que solo trabaja ahí. No van en `public` porque Supabase
  publica ese esquema en su API web.
- En cada despliegue corre `cargar_demo --si-vacio`: llena los ejemplos la
  primera vez y después no toca lo que se haya guardado.
- Supabase gratuito pausa el proyecto si pasan 7 días sin uso. Los datos no se
  pierden: se reactiva con un clic en supabase.com.

Otras opciones que también sirven: PythonAnywhere, Railway, Fly.io o Neon para
la base.

## Los casos de ejemplo

`manage.py cargar_demo` carga los casos de las clases, que sirven para comprobar
que todo calcula igual que antes:

| Caso | Asientos | Impuesto | Suma del Debe | Utilidad neta |
| --- | --- | --- | --- | --- |
| CYBERTEC S.A. | 4 | 0% | 100,000.00 | 10,000.00 |
| Comercializadora Metropolitana | 8 | 30% | 9,168,776.00 | 105,016.80 |
| Comercializadora del Sur S.A.C. | 8 | 29.5% | 9,170,697.63 | 100,746.17 |
| Ferretería Los Andes S.R.L. | 8 | 29.5% | 4,891,400.00 | 70,500.00 |

Los Andes agrega lo que a los otros les falta: compra al contado, venta al contado y
al crédito, sueldos y cobranza a clientes sin letras. Su enunciado en texto, leído por
el asistente, da exactamente los mismos asientos (lo comprueba una prueba).

Comercializadora del Sur usa el IGV del 18% (Perú) y junio de 2024 en todos
los asientos: el enunciado mezcla 2023, 2024 y 2025, que son errores de tipeo.

Esas mismas cifras están escritas en `nucleo/tests/test_motor.py`: si una
fórmula se rompe, las pruebas lo dicen.
