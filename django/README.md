# Contabilidad UNI - versión en Python con Django

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
.venv/Scripts/python manage.py cargar_demo        # dos casos de ejemplo (opcional)
.venv/Scripts/python manage.py runserver
```

Abrir http://127.0.0.1:8000/. En Linux o Mac, `.venv/bin/python` en lugar de
`.venv/Scripts/python`.

Comandos útiles:

| Comando | Para qué |
| --- | --- |
| `manage.py test nucleo` | 41 pruebas: motor contable, pantallas, PDF, Excel e importación |
| `manage.py cargar_demo --borrar` | Borra todo y vuelve a cargar los dos casos de clase |
| `manage.py createsuperuser` | Entrar a `/admin/` y ver las tablas por dentro |

## Cómo está organizado

```
django/
  contabilidad/        configuración del proyecto (settings, urls, wsgi)
  nucleo/
    dominio/           el motor contable: Python puro, no importa Django
    datos/             plantillas de plan de cuentas y los dos casos de ejemplo
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

El PDF reemplaza a jsPDF y el Excel es nuevo: en el navegador no tenía sentido,
pero con Python una hoja de cálculo sale casi gratis y el profesor suele pedir
los cuadros en Excel.

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
este repositorio y confirmar. Las variables (`DJANGO_DEBUG=0`, la clave secreta,
los dominios permitidos) ya están en ese archivo.

Un detalle del plan gratuito: el disco se borra en cada despliegue, así que la
base SQLite queda vacía de nuevo. Para que los casos no se pierdan hace falta un
disco persistente o una base PostgreSQL. Mientras eso no esté, conviene usar
"Respaldo JSON" en Configuración para guardarse el caso.

Otras opciones que también sirven: PythonAnywhere (tiene plan gratuito y
consola web), Railway y Fly.io.

## Los dos casos de ejemplo

`manage.py cargar_demo` carga los casos de las clases, que sirven para comprobar
que todo calcula igual que antes:

| Caso | Asientos | Impuesto | Suma del Debe | Utilidad neta |
| --- | --- | --- | --- | --- |
| CYBERTEC S.A. | 4 | 0% | 100,000.00 | 10,000.00 |
| Comercializadora Metropolitana | 8 | 30% | 9,168,776.00 | 105,016.80 |

Esas mismas cifras están escritas en `nucleo/tests/test_motor.py`: si una
fórmula se rompe, las pruebas lo dicen.
