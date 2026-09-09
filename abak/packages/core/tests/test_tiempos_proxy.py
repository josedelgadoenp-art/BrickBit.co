"""El proxy tiene que aguantar más que el navegador.

Está medido: el proxy del reescrito de Next corta a los **30 segundos** por
omisión, y una petición de 45 s devuelve 500 a los 30. Pedirle un análisis a la
IA con el catálogo entero tarda bastante más que eso, así que el asistente
fallaba siempre — y como ese 500 del proxy no trae JSON, en pantalla salía otro
error completamente distinto.

Estos dos números viven en archivos separados y no hay nada que los ate salvo
esta prueba. Si alguien baja el del proxy o sube el del navegador, quien corta
primero vuelve a ser el proxy, y su 500 no explica nada.
"""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
CONFIG = RAIZ / "apps" / "web" / "next.config.mjs"
CLIENTE = RAIZ / "apps" / "web" / "src" / "lib" / "api.ts"


def _numero(texto: str, patron: str) -> int:
    encontrado = re.search(patron, texto)
    assert encontrado, f"no se encontró «{patron}»"
    return int(encontrado.group(1).replace("_", ""))


@pytest.mark.skipif(not CONFIG.exists(), reason="sin frontend en esta copia")
def test_el_proxy_aguanta_mas_que_el_navegador():
    proxy = _numero(CONFIG.read_text(encoding="utf-8"), r"proxyTimeout:\s*([\d_]+)")
    cliente = _numero(CLIENTE.read_text(encoding="utf-8"), r"AbortSignal\.timeout\(([\d_]+)\)")
    assert proxy > cliente, (
        f"el proxy corta a los {proxy/1000:.0f} s y el navegador a los {cliente/1000:.0f} s: "
        "cortaría primero el proxy, y su error no explica nada")
    assert proxy - cliente >= 5_000, "hace falta margen entre los dos"


@pytest.mark.skipif(not CONFIG.exists(), reason="sin frontend en esta copia")
def test_el_proxy_da_tiempo_de_sobra_a_una_peticion_a_la_ia():
    """Menos de dos minutos y el asistente vuelve a fallar en las peticiones
    grandes, que son justo las que valen la pena."""
    proxy = _numero(CONFIG.read_text(encoding="utf-8"), r"proxyTimeout:\s*([\d_]+)")
    assert proxy >= 120_000, f"el proxy sólo aguanta {proxy/1000:.0f} s"
