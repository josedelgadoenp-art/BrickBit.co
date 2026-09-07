"""El muestreo honesto: rápido, pero diciendo lo que cuesta.

Lo que se prueba no es que `sample()` funcione —eso lo hace pandas— sino que el
reporte de precisión sea correcto: si el margen que promete no se cumple, la
herramienta es peor que no tenerla, porque da confianza falsa.
"""

from __future__ import annotations

import ast

import numpy as np
import pandas as pd
import pytest

from abak_core.registry.base import AYUDANTES

_espacio: dict = {}
exec(ast.unparse(ast.parse(AYUDANTES["tomar_muestra"].fuente)), {"pd": pd, "np": np}, _espacio)  # noqa: S102
tomar_muestra = _espacio["tomar_muestra"]


def _poblacion(n: int = 200_000, semilla: int = 5) -> pd.DataFrame:
    r = np.random.default_rng(semilla)
    ciudades = r.choice(["CDMX", "Monterrey", "Mérida", "Tijuana"], size=n,
                        p=[0.55, 0.25, 0.05, 0.15])
    return pd.DataFrame({
        "precio": r.lognormal(14.6, 0.45, n),
        "m2": r.normal(120, 35, n).clip(30, 400),
        "ciudad": ciudades,
    })


def test_el_margen_prometido_se_cumple_de_verdad():
    """La prueba dura: se repite el muestreo y se cuenta cuántas veces la media
    real cae dentro del intervalo que la herramienta prometió.

    Con un 95% nominal, sobre 200 repeticiones debe cubrir cerca de 190 veces.
    Si cubriera muchas menos, el reporte estaría mintiendo.
    """
    poblacion = _poblacion(50_000)
    media_real = poblacion["precio"].mean()

    dentro = 0
    repeticiones = 200
    for semilla in range(repeticiones):
        muestra, reporte = tomar_muestra(poblacion, 2_000, semilla)
        fila = reporte[reporte["columna"] == "precio"].iloc[0]
        bajo = fila["media_en_muestra"] - 1.96 * fila["error_estandar"]
        alto = fila["media_en_muestra"] + 1.96 * fila["error_estandar"]
        dentro += bool(bajo <= media_real <= alto)

    cobertura = dentro / repeticiones
    assert 0.90 <= cobertura <= 0.99, f"cobertura {cobertura:.2%}, debería rondar el 95%"


def test_una_muestra_mas_grande_promete_menos_error():
    poblacion = _poblacion(50_000)
    _, chica = tomar_muestra(poblacion, 1_000, 1)
    _, grande = tomar_muestra(poblacion, 16_000, 1)
    ee_chica = chica[chica["columna"] == "precio"].iloc[0]["error_estandar"]
    ee_grande = grande[grande["columna"] == "precio"].iloc[0]["error_estandar"]
    # Cuadruplicar la muestra debe partir el error a la mitad, más o menos.
    assert ee_grande < ee_chica / 2


def test_el_interruptor_de_usar_todo_devuelve_la_poblacion_entera():
    """El flujo completo: exploras en muestra, y para el resultado final lo prendes."""
    poblacion = _poblacion(20_000)
    muestra, reporte = tomar_muestra(poblacion, 1_000, 1, usar_todo=True)
    assert len(muestra) == len(poblacion)
    assert reporte.attrs["fraccion"] == 1.0
    # Sin muestreo no hay error de muestreo: la corrección por población finita
    # lo lleva a cero, que es lo correcto y no un descuido.
    assert reporte[reporte["columna"] == "precio"].iloc[0]["error_estandar"] == pytest.approx(0, abs=1e-9)


def test_pedir_mas_filas_de_las_que_hay_no_es_un_error():
    poblacion = _poblacion(500)
    muestra, reporte = tomar_muestra(poblacion, 5_000, 1)
    assert len(muestra) == 500
    assert reporte.attrs["fraccion"] == 1.0


def test_el_estrato_conserva_a_los_grupos_chicos():
    """Sin estratificar, una ciudad con pocas ventas puede desaparecer, y con
    ella la posibilidad de estimar cualquier cosa sobre esa ciudad."""
    poblacion = _poblacion(40_000)
    _, _ = tomar_muestra(poblacion, 400, 1)
    muestra, _ = tomar_muestra(poblacion, 400, 1, estrato="ciudad")

    proporcion_real = poblacion["ciudad"].value_counts(normalize=True)
    proporcion_muestra = muestra["ciudad"].value_counts(normalize=True)
    for ciudad in proporcion_real.index:
        assert ciudad in proporcion_muestra.index, f"desapareció {ciudad}"
        assert proporcion_muestra[ciudad] == pytest.approx(proporcion_real[ciudad], abs=0.02)


def test_las_columnas_de_texto_no_entran_al_reporte():
    _, reporte = tomar_muestra(_poblacion(5_000), 500, 1)
    assert set(reporte["columna"]) == {"precio", "m2"}


def test_la_misma_semilla_da_la_misma_muestra():
    poblacion = _poblacion(10_000)
    a, _ = tomar_muestra(poblacion, 500, 42)
    b, _ = tomar_muestra(poblacion, 500, 42)
    c, _ = tomar_muestra(poblacion, 500, 43)
    assert a.index.equals(b.index)
    assert not a.index.equals(c.index)


def test_el_nodo_compila_dentro_de_abak():
    from abak_core import GrafoSpec, compilar
    from abak_core.registry import cargar_todos
    cargar_todos()

    grafo = GrafoSpec.model_validate({
        "nodos": [
            {"id": "d", "op": "datos.ejemplo", "params": {"conjunto": "mexico_estados"}},
            {"id": "m", "op": "datos.muestra", "params": {"n": 1000}},
            {"id": "r", "op": "econometria.mco", "params": {
                "y": "precio_m2", "x": ["ingreso_hogar_mensual"]}},
        ],
        "aristas": [
            {"origen": "d", "puerto_origen": "datos", "destino": "m", "puerto_destino": "datos"},
            {"origen": "m", "puerto_origen": "datos", "destino": "r", "puerto_destino": "datos"},
        ],
    })
    programa = compilar(grafo)
    assert not programa.hay_errores, [d.mensaje for d in programa.diagnosticos]
