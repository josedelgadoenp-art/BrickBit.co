import os
import warnings
from pathlib import Path

import pytest

from abaco_core.registry import cargar_todos

warnings.filterwarnings("ignore")
EJEMPLOS = Path(__file__).resolve().parents[1] / "abaco_core" / "data" / "ejemplos"

# El registro se carga al IMPORTAR, no en un fixture: `@parametrize` se evalúa
# durante la colección, antes de que corra ningún fixture, y con el registro
# vacío las pruebas por herramienta se saltaban en silencio — que es peor que
# fallar, porque parecía que pasaban.
os.environ["ABACO_DATOS"] = str(EJEMPLOS)
cargar_todos()


def grafo(titulo, nodos, aristas, semilla=42):
    """Atajo para construir un GrafoSpec sin escribir el diccionario a mano."""
    from abaco_core import AristaSpec, GrafoSpec, NodoSpec

    return GrafoSpec(
        titulo=titulo, semilla=semilla,
        nodos=[NodoSpec(id=i, op=o, etiqueta=e, params=p or {},
                        posicion={"x": 0, "y": k * 90})
               for k, (i, o, e, p) in enumerate(nodos)],
        aristas=[AristaSpec(origen=a, puerto_origen=b, destino=c, puerto_destino=d)
                 for a, b, c, d in aristas],
    )
