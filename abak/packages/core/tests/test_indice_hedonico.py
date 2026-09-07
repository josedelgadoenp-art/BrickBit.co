"""El índice hedónico, contra un mercado simulado donde la verdad se conoce.

La prueba central compara dos cosas a la vez: que el índice recupere el
movimiento real del mercado, y que la mediana de lo vendido NO lo haga. Si sólo
comprobara lo primero, no estaría midiendo por qué existe la herramienta.
"""

from __future__ import annotations

import ast

import numpy as np
import pandas as pd
import pytest

from abak_core.registry.base import AYUDANTES

# Se ejecuta el ayudante tal como viaja en el script exportado: si se probara
# otra implementación, la prueba no diría nada del código que se lleva el usuario.
_espacio: dict = {}
exec(ast.unparse(ast.parse(AYUDANTES["indice_hedonico"].fuente)), {"pd": pd, "np": np}, _espacio)  # noqa: S102
indice_hedonico = _espacio["indice_hedonico"]

TRAYECTORIA = [0.0, 0.04, 0.09, 0.06, 0.15]   # subida real acumulada por trimestre


def _mercado(n_por_periodo: int = 400, semilla: int = 3) -> pd.DataFrame:
    """Un mercado donde los precios suben y la MEZCLA de lo vendido cambia.

    Al principio se venden casas grandes; al final, departamentos chicos. La
    mediana de lo vendido va a bajar aunque ningún precio haya bajado: eso es
    exactamente el error que el índice existe para no cometer.
    """
    r = np.random.default_rng(semilla)
    filas = []
    for t, subida in enumerate(TRAYECTORIA):
        # Los metros medios caen de 190 a 90 a lo largo de la muestra.
        m2_medio = 190 - 25 * t
        m2 = r.normal(m2_medio, 18, n_por_periodo).clip(45, 320)
        recamaras = np.clip((m2 / 55).round(), 1, 5)
        antiguedad = r.integers(0, 40, n_por_periodo)
        log_precio = (np.log(58_000) + np.log(m2) + 0.06 * recamaras
                      - 0.004 * antiguedad + subida + r.normal(0, 0.05, n_por_periodo))
        filas.append(pd.DataFrame({
            "trimestre": f"2026T{t + 1}", "precio": np.exp(log_precio),
            "m2": m2, "recamaras": recamaras, "antiguedad": antiguedad,
        }))
    return pd.concat(filas, ignore_index=True)


def test_el_indice_recupera_la_subida_real_y_la_mediana_no():
    """La prueba que justifica la herramienta entera."""
    datos = _mercado()
    tabla = indice_hedonico(datos, "trimestre", "precio", ["m2", "recamaras", "antiguedad"])

    verdadero = [100.0 * np.exp(s) for s in TRAYECTORIA]
    for fila, esperado in zip(tabla.to_dict("records"), verdadero):
        assert fila["indice"] == pytest.approx(esperado, rel=0.02), (
            f"{fila['periodo']}: índice {fila['indice']:.1f} vs verdadero {esperado:.1f}")

    # Y la mediana de lo vendido, que es lo que reporta casi todo el mundo,
    # apunta al lado contrario porque cambió la mezcla.
    medianas = datos.groupby("trimestre")["precio"].median()
    cambio_mediana = (medianas.iloc[-1] / medianas.iloc[0] - 1) * 100
    cambio_real = (np.exp(TRAYECTORIA[-1]) - 1) * 100
    assert cambio_real > 10, "el mercado del caso de prueba apenas se mueve"
    assert cambio_mediana < -20, (
        f"la mediana debería caer con fuerza por composición; cayó {cambio_mediana:.1f}%")


def test_el_primer_periodo_es_la_base():
    tabla = indice_hedonico(_mercado(120), "trimestre", "precio", ["m2"], base=100.0)
    assert tabla.iloc[0]["indice"] == 100.0
    # pandas guarda el None de una columna numérica como NaN; al artefacto llega
    # como null y en pantalla como «—», que es lo correcto: el periodo base no
    # tiene cambio contra nada.
    assert pd.isna(tabla.iloc[0]["cambio_pct"])
    assert tabla.iloc[0]["nota"] == "Periodo base"


def test_la_base_se_puede_cambiar():
    tabla = indice_hedonico(_mercado(120), "trimestre", "precio", ["m2"], base=2020.0)
    assert tabla.iloc[0]["indice"] == 2020.0


def test_avisa_cuando_un_periodo_tiene_pocas_ventas():
    """Con pocas ventas el índice brinca por ruido, y eso hay que decirlo."""
    datos = _mercado(n_por_periodo=200)
    flaco = datos[datos["trimestre"] == "2026T3"].head(5)
    datos = pd.concat([datos[datos["trimestre"] != "2026T3"], flaco], ignore_index=True)

    tabla = indice_hedonico(datos, "trimestre", "precio", ["m2"], minimo_por_periodo=30)
    fila = tabla[tabla["periodo"] == "2026T3"].iloc[0]
    assert fila["ventas"] == 5
    assert "ruidoso" in fila["nota"]


def test_un_precio_de_cero_se_rechaza_con_su_motivo():
    """Un cero no es un precio barato: es un dato malo, y en logaritmos revienta."""
    datos = _mercado(60)
    datos.loc[0, "precio"] = 0.0
    with pytest.raises(ValueError) as exc:
        indice_hedonico(datos, "trimestre", "precio", ["m2"])
    assert "cero" in str(exc.value)


def test_con_un_solo_periodo_no_hay_indice():
    datos = _mercado(60)
    datos = datos[datos["trimestre"] == "2026T1"]
    with pytest.raises(ValueError) as exc:
        indice_hedonico(datos, "trimestre", "precio", ["m2"])
    assert "mas de un periodo" in str(exc.value)


def test_el_nodo_corre_dentro_de_abak():
    from abak_core import GrafoSpec, compilar
    from abak_core.registry import cargar_todos
    cargar_todos()

    grafo = GrafoSpec.model_validate({
        "nodos": [
            {"id": "d", "op": "datos.ejemplo", "params": {"conjunto": "mexico_estados"}},
            {"id": "i", "op": "inmobiliario.indice_hedonico", "params": {
                "periodo": "ciclo", "precio": "precio_m2",
                "caracteristicas": ["ingreso_hogar_mensual", "escolaridad_anios"]}},
        ],
        "aristas": [{"origen": "d", "puerto_origen": "datos",
                     "destino": "i", "puerto_destino": "datos"}],
    })
    programa = compilar(grafo)
    assert not programa.hay_errores, [d.mensaje for d in programa.diagnosticos]
