"""El nodo causal, contra una simulación donde la verdad se conoce.

Aquí no se comprueba que corra: se comprueba que RECUPERE el efecto verdadero
donde la práctica común no lo recupera. Si esta prueba no distingue entre las
dos cosas, la herramienta no vale nada.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from abak_core import GrafoSpec, compilar
from abak_core.runtime.ejecutor import Ejecutor

EFECTO_VERDADERO = 3.0


def _datos(n: int = 4000, semilla: int = 11) -> pd.DataFrame:
    """Un mundo con confusión, un mediador y un colisionador.

    demanda_previa  -> estacion, precio      (confusor: hay que controlarlo)
    estacion        -> densidad -> precio    (mediador: NO se controla)
    estacion, precio-> reportes              (colisionador: NO se controla)
    ingreso         -> precio                (predictor inofensivo)
    """
    r = np.random.default_rng(semilla)
    demanda = r.normal(size=n)
    ingreso = r.normal(size=n)
    estacion = 0.8 * demanda + r.normal(size=n)
    densidad = 1.2 * estacion + r.normal(size=n)
    precio = (EFECTO_VERDADERO * estacion + 1.5 * demanda + 0.9 * densidad
              + 0.7 * ingreso + r.normal(size=n))
    reportes = 0.9 * estacion + 0.9 * precio + r.normal(size=n)
    return pd.DataFrame({
        "estacion": estacion, "precio": precio, "demanda_previa": demanda,
        "densidad": densidad, "ingreso": ingreso, "reportes": reportes,
    })


# El efecto total de «estacion» sobre «precio» incluye lo que pasa por densidad:
# 3.0 directo + 1.2 * 0.9 por el mediador.
EFECTO_TOTAL = EFECTO_VERDADERO + 1.2 * 0.9

ARCOS = [
    "demanda_previa->estacion", "demanda_previa->precio",
    "estacion->densidad", "densidad->precio",
    "estacion->reportes", "precio->reportes",
    "ingreso->precio",
]


def _correr(params: dict) -> dict:
    grafo = GrafoSpec.model_validate({
        "nodos": [
            {"id": "d", "op": "datos.ejemplo", "params": {"conjunto": "entidades"}},
            {"id": "c", "op": "causal.efecto", "params": params},
        ],
        "aristas": [{"origen": "d", "puerto_origen": "datos",
                     "destino": "c", "puerto_destino": "datos"}],
    })
    programa = compilar(grafo)
    assert not programa.hay_errores, [d.mensaje for d in programa.diagnosticos]
    # Se inyecta el DataFrame simulado en lugar del conjunto de ejemplo.
    ejecutor = Ejecutor()
    return ejecutor, programa


def test_el_nodo_recupera_el_efecto_verdadero_y_el_ingenuo_no():
    """La prueba que justifica la herramienta entera."""
    import statsmodels.api as sm

    from abak_core.nodes.causal.efecto import EfectoCausal  # noqa: F401  (registro)
    from abak_core.causal import GrafoCausal, conjunto_ajuste

    datos = _datos()
    grafo = GrafoCausal([tuple(a.split("->")) for a in ARCOS])  # type: ignore[misc]
    ajuste = conjunto_ajuste(grafo, "estacion", "precio", disponibles=set(datos.columns))
    assert ajuste == {"demanda_previa"}, ajuste

    # 1. Lo que hace Abak: sólo el confusor.
    X = sm.add_constant(datos[["estacion", *sorted(ajuste)]])
    correcto = sm.OLS(datos["precio"], X).fit().params["estacion"]

    # 2. Lo que hace todo el mundo: «meto todas las que tengo».
    todas = ["estacion", "demanda_previa", "densidad", "ingreso", "reportes"]
    ingenuo = sm.OLS(datos["precio"], sm.add_constant(datos[todas])).fit().params["estacion"]

    assert correcto == pytest.approx(EFECTO_TOTAL, abs=0.12), (
        f"el conjunto correcto no recupera el efecto: {correcto:.3f} vs {EFECTO_TOTAL:.3f}")
    assert abs(ingenuo - EFECTO_TOTAL) > 1.0, (
        f"la prueba no discrimina: el ingenuo dio {ingenuo:.3f}, demasiado cerca de la verdad")


def test_el_nodo_corre_completo_y_explica_cada_variable():
    from abak_core.registry import cargar_todos
    cargar_todos()

    datos = _datos(n=800)
    from abak_core.nodes.causal.efecto import EfectoCausal

    grafo = GrafoSpec.model_validate({
        "nodos": [{"id": "c", "op": "causal.efecto", "params": {
            "arcos": ARCOS, "tratamiento": "estacion", "resultado": "precio"}}],
        "aristas": [],
    })
    programa = compilar(grafo)
    # Sin datos conectados el compilador debe quejarse, no reventar.
    assert programa.hay_errores


def test_si_falta_el_confusor_lo_dice_en_vez_de_estimar_cualquier_cosa():
    """Sin `demanda_previa` el efecto no se identifica. Callarlo sería lo grave."""
    from abak_core.causal import GrafoCausal, conjunto_ajuste

    grafo = GrafoCausal([tuple(a.split("->")) for a in ARCOS])  # type: ignore[misc]
    disponibles = {"estacion", "precio", "densidad", "ingreso", "reportes"}
    assert conjunto_ajuste(grafo, "estacion", "precio", disponibles=disponibles) is None


def test_el_ayudante_exportado_da_lo_mismo_que_el_motor():
    """El código que se lleva el usuario razona igual que Abak.

    El ayudante es una reimplementación compacta para que el `.py` exportado sea
    autónomo. Si se separa del motor, el script miente. Se comparan los dos
    sobre los mismos grafos.
    """
    import ast

    from abak_core.causal import GrafoCausal, clasificar, conjunto_ajuste
    from abak_core.registry.base import AYUDANTES

    espacio: dict = {}
    exec(ast.unparse(ast.parse(AYUDANTES["puerta_trasera"].fuente)), espacio)  # noqa: S102
    puerta_trasera = espacio["puerta_trasera"]

    casos = [
        (["z->t", "z->y", "t->y"], "t", "y"),
        (["t->m", "m->y"], "t", "y"),
        (["u1->t", "u1->c", "u2->c", "u2->y", "t->y"], "t", "y"),
        (["u->z", "z->t", "u->y", "t->y"], "t", "y"),
        (ARCOS, "estacion", "precio"),
    ]
    for arcos, trat, res in casos:
        pares = [tuple(a.split("->")) for a in arcos]
        motor = GrafoCausal(list(pares))  # type: ignore[arg-type]
        disponibles = set(motor.variables)
        esperado = conjunto_ajuste(motor, trat, res, disponibles=disponibles)
        papeles_esperados = {k: v.value for k, v in
                             clasificar(motor, trat, res, esperado).items()}

        ajuste, papeles = puerta_trasera([list(p) for p in pares], trat, res, sorted(disponibles))
        assert ajuste == esperado, f"{arcos}: ayudante {ajuste} vs motor {esperado}"
        assert papeles == papeles_esperados, f"{arcos}: papeles distintos"
