"""El libro de especificaciones: contar lo que nadie cuenta.

Con veinte intentos, encontrar un p-valor por debajo de 0.05 es lo esperable
aunque no haya nada. Nadie miente al reportar el mejor; simplemente nadie
cuenta los otros diecinueve. Estas pruebas comprueban que Abak sí los cuenta.
"""

from __future__ import annotations

from abak_core.runtime.especificaciones import LibroEspecificaciones


def _modelo(**coefs: tuple[float, float]) -> dict:
    """`_modelo(m2=(0.5, 0.001))` -> artefacto con esa variable y su p-valor."""
    return {
        "tipo": "modelo",
        "coeficientes": (
            [{"variable": "const", "coeficiente": 1.0, "p_valor": 0.5}]
            + [{"variable": v, "coeficiente": c, "error_estandar": 0.1, "p_valor": p}
               for v, (c, p) in coefs.items()]),
        "diagnosticos": {"Observaciones": 100, "R²": 0.5},
    }


def _libro(tmp_path) -> LibroEspecificaciones:
    return LibroEspecificaciones(tmp_path / "especificaciones.jsonl")


def test_cuenta_cada_especificacion(tmp_path):
    libro = _libro(tmp_path)
    for i, coef in enumerate([0.31, 0.42, 0.58]):
        libro.anotar(ejecucion_id=f"e{i}", nodo_id=f"n{i}", etiqueta="MCO",
                     op="econometria.mco", resultado="precio",
                     artefacto_modelo=_modelo(m2=(coef, 0.01)))
    resumen = libro.resumen("precio")
    assert resumen["n_especificaciones"] == 3
    (m2,) = [v for v in resumen["variables"] if v["variable"] == "m2"]
    assert m2["veces"] == 3
    assert m2["minimo"] == 0.31 and m2["maximo"] == 0.58
    assert m2["mediana"] == 0.42

    # Con un número PAR, la mediana es el promedio de los dos centrales: si se
    # tomara el de arriba, con dos especificaciones «mediana» y «máximo» serían
    # el mismo número y el extremo parecería lo típico.
    libro.anotar(ejecucion_id="e3", nodo_id="n3", etiqueta="MCO", op="econometria.mco",
                 resultado="precio", artefacto_modelo=_modelo(m2=(0.60, 0.01)))
    (m2,) = [v for v in libro.resumen("precio")["variables"] if v["variable"] == "m2"]
    assert m2["mediana"] == (0.42 + 0.58) / 2


def test_avisa_cuando_lo_que_reportas_es_el_extremo(tmp_path):
    """El caso que importa: elegiste, entre todas, la más favorable."""
    libro = _libro(tmp_path)
    for i, coef in enumerate([0.31, 0.35, 0.42]):
        libro.anotar(ejecucion_id="e", nodo_id=f"n{i}", etiqueta="MCO", op="econometria.mco",
                     resultado="precio", artefacto_modelo=_modelo(m2=(coef, 0.01)))
    libro.anotar(ejecucion_id="e", nodo_id="elegida", etiqueta="MCO", op="econometria.mco",
                 resultado="precio", artefacto_modelo=_modelo(m2=(0.90, 0.01)))

    (m2,) = [v for v in libro.resumen("precio", actual="elegida")["variables"]
             if v["variable"] == "m2"]
    assert m2["actual"] == 0.90
    assert m2["actual_es_extremo"] is True

    # Y una del montón NO se marca.
    (m2,) = [v for v in libro.resumen("precio", actual="n1")["variables"]
             if v["variable"] == "m2"]
    assert m2["actual_es_extremo"] is False


def test_marca_cuando_el_coeficiente_cambia_de_signo(tmp_path):
    """Si el signo baila entre especificaciones, no hay hallazgo que reportar."""
    libro = _libro(tmp_path)
    for i, coef in enumerate([0.4, -0.3, 0.1]):
        libro.anotar(ejecucion_id="e", nodo_id=f"n{i}", etiqueta="MCO", op="econometria.mco",
                     resultado="precio", artefacto_modelo=_modelo(x=(coef, 0.2)))
    (x,) = libro.resumen("precio")["variables"]
    assert x["cambia_de_signo"] is True


def test_cuenta_cuantas_veces_salio_significativa(tmp_path):
    libro = _libro(tmp_path)
    for i, p in enumerate([0.001, 0.04, 0.30, 0.62]):
        libro.anotar(ejecucion_id="e", nodo_id=f"n{i}", etiqueta="MCO", op="econometria.mco",
                     resultado="precio", artefacto_modelo=_modelo(x=(0.5, p)))
    (x,) = libro.resumen("precio")["variables"]
    assert x["veces"] == 4
    assert x["veces_significativa"] == 2


def test_cada_variable_explicada_lleva_su_propia_cuenta(tmp_path):
    libro = _libro(tmp_path)
    libro.anotar(ejecucion_id="e", nodo_id="a", etiqueta="MCO", op="econometria.mco",
                 resultado="precio", artefacto_modelo=_modelo(x=(0.5, 0.01)))
    libro.anotar(ejecucion_id="e", nodo_id="b", etiqueta="MCO", op="econometria.mco",
                 resultado="renta", artefacto_modelo=_modelo(x=(0.9, 0.01)))
    assert libro.resumen("precio")["n_especificaciones"] == 1
    assert libro.resumen("renta")["n_especificaciones"] == 1
    assert {r["resultado"] for r in libro.resultados_registrados()} == {"precio", "renta"}


def test_la_constante_no_cuenta_como_hallazgo(tmp_path):
    libro = _libro(tmp_path)
    libro.anotar(ejecucion_id="e", nodo_id="a", etiqueta="MCO", op="econometria.mco",
                 resultado="precio", artefacto_modelo=_modelo(x=(0.5, 0.01)))
    assert [v["variable"] for v in libro.resumen("precio")["variables"]] == ["x"]


def test_una_linea_corrupta_no_invalida_el_libro(tmp_path):
    libro = _libro(tmp_path)
    libro.anotar(ejecucion_id="e", nodo_id="a", etiqueta="MCO", op="econometria.mco",
                 resultado="precio", artefacto_modelo=_modelo(x=(0.5, 0.01)))
    with libro.ruta.open("a", encoding="utf-8") as f:
        f.write("{esto no es json\n")
    libro.anotar(ejecucion_id="e", nodo_id="b", etiqueta="MCO", op="econometria.mco",
                 resultado="precio", artefacto_modelo=_modelo(x=(0.7, 0.01)))
    assert libro.resumen("precio")["n_especificaciones"] == 2


def test_sin_historial_no_se_inventa_nada(tmp_path):
    assert _libro(tmp_path).resumen("precio")["n_especificaciones"] == 0
    assert _libro(tmp_path).resultados_registrados() == []
