"""Carga los casos de ejemplo sin tocar la interfaz: manage.py cargar_demo."""

from django.core.management.base import BaseCommand

from ...datos.casos_demo import PLANTILLAS_CASO, obtener_plantilla_caso, crear_caso_demo
from ...models import Caso


class Command(BaseCommand):
    help = "Crea los casos de ejemplo (CYBERTEC y Comercializadora Metropolitana)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--caso",
            dest="caso",
            default="",
            help="Id del caso de ejemplo. Sin esto, carga todos.",
        )
        parser.add_argument(
            "--borrar",
            action="store_true",
            help="Borra los casos existentes antes de cargar.",
        )

    def handle(self, *args, **opciones):
        if opciones["borrar"]:
            borrados = Caso.objects.count()
            Caso.objects.all().delete()
            self.stdout.write("Casos borrados: " + str(borrados))

        if opciones["caso"]:
            plantilla = obtener_plantilla_caso(opciones["caso"])
            if plantilla is None:
                ids = ", ".join(item.id for item in PLANTILLAS_CASO)
                self.stderr.write("No existe ese caso. Disponibles: " + ids)
                return
            plantillas = [plantilla]
        else:
            plantillas = PLANTILLAS_CASO

        for plantilla in plantillas:
            caso = crear_caso_demo(plantilla)
            self.stdout.write(
                self.style.SUCCESS(
                    "Caso cargado: "
                    + caso.nombre
                    + " ("
                    + str(caso.cuentas.count())
                    + " cuentas, "
                    + str(caso.asientos.count())
                    + " asientos)"
                )
            )
