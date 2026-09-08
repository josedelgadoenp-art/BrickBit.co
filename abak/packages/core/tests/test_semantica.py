"""Que cada herramienta haga lo que dice, no solo que no reviente.

La auditoria de `test_auditoria.py` comprueba que las 67 herramientas se
ejecuten. Eso descarta que revienten, y nada mas: una que agrupe mal, filtre al
reves o rezague en la direccion equivocada pasa esa prueba con las manos en los
bolsillos. Aqui se comprueba el RESULTADO contra un calculo hecho aparte.

Se concentra en la familia de preparacion de datos y en las transformaciones,
que son las que nunca se habian ejecutado y las que mas silenciosamente pueden
mentir: un rezago mal puesto no da error, da un modelo que mira al futuro.
"""

import pandas as pd
import pytest

from abak_core import compilar, ejecutar

from .conftest import grafo

pytest.importorskip("statsmodels")

ESTADOS = ("d", "datos.ejemplo", "Entidades", {"conjunto": "mexico_estados"})
PANEL = ("d", "datos.ejemplo", "Panel", {"conjunto": "panel_estados"})


def _tabla(nodos, aristas, nodo, puerto="datos") -> pd.DataFrame:
    """La salida de un bloque, como DataFrame, para poder compararla."""
    r = ejecutar(compilar(grafo("semantica", nodos, aristas)))
    assert r.ok, r.bitacora[-2:]
    art = {n.nodo_id: n for n in r.nodos}[nodo].artefactos[puerto]
    return pd.DataFrame(art["filas"], columns=[c["nombre"] for c in art["columnas"]])


def _fuente(conjunto="mexico_estados") -> pd.DataFrame:
    r = ejecutar(compilar(grafo("fuente", [("d", "datos.ejemplo", "D", {"conjunto": conjunto})], [])))
    art = {n.nodo_id: n for n in r.nodos}["d"].artefactos["datos"]
    return pd.DataFrame(art["filas"], columns=[c["nombre"] for c in art["columnas"]])


# --- Filtrar ----------------------------------------------------------------

def test_filtrar_deja_exactamente_las_filas_que_cumplen():
    origen = _fuente()
    esperadas = int((origen["precio_m2"] > 15000).sum())
    t = _tabla([ESTADOS, ("f", "datos.filtrar", "F",
                          {"condiciones": [{"columna": "precio_m2", "operador": "mayor",
                                            "valor": "15000"}]})],
               [("d", "datos", "f", "datos")], "f")
    assert len(t) == esperadas, f"quedaron {len(t)} y debían quedar {esperadas}"
    assert (t["precio_m2"].astype(float) > 15000).all()


def test_filtrar_con_dos_condiciones_las_une_con_y():
    origen = _fuente()
    esperadas = int(((origen["precio_m2"] > 12000) & (origen["escolaridad_anios"] > 9)).sum())
    t = _tabla([ESTADOS, ("f", "datos.filtrar", "F",
                          {"unir_con": "y",
                           "condiciones": [
                               {"columna": "precio_m2", "operador": "mayor", "valor": "12000"},
                               {"columna": "escolaridad_anios", "operador": "mayor", "valor": "9"}]})],
               [("d", "datos", "f", "datos")], "f")
    assert len(t) == esperadas


def test_filtrar_con_o_es_la_union_y_no_la_interseccion():
    origen = _fuente()
    esperadas = int(((origen["precio_m2"] > 20000) | (origen["escolaridad_anios"] > 11)).sum())
    t = _tabla([ESTADOS, ("f", "datos.filtrar", "F",
                          {"unir_con": "o",
                           "condiciones": [
                               {"columna": "precio_m2", "operador": "mayor", "valor": "20000"},
                               {"columna": "escolaridad_anios", "operador": "mayor", "valor": "11"}]})],
               [("d", "datos", "f", "datos")], "f")
    assert len(t) == esperadas
    assert esperadas > 0


# --- Agrupar ----------------------------------------------------------------

@pytest.mark.parametrize("funcion", ["mean", "sum", "median", "min", "max", "std"])
def test_agrupar_calcula_lo_que_dice(funcion):
    origen = _fuente()
    esperado = (origen.groupby("ciclo", observed=True)["precio_m2"]
                .agg(funcion).sort_index().round(6))
    t = _tabla([ESTADOS, ("g", "datos.agrupar", "G",
                          {"por": ["ciclo"], "columnas": ["precio_m2"], "funcion": funcion})],
               [("d", "datos", "g", "datos")], "g")
    obtenido = (t.set_index("ciclo")["precio_m2"].astype(float).sort_index().round(6))
    # Se comparan VALORES, no tipos: `sum` de enteros da int64 y el artefacto
    # llega en float. Y NaN cuenta como igual a NaN — la desviación de un grupo
    # de una sola fila es NaN legítimamente.
    esperado = esperado.astype(float)
    assert list(obtenido.index) == list(esperado.index)
    for clave in esperado.index:
        a, b = obtenido[clave], esperado[clave]
        if pd.isna(a) or pd.isna(b):
            assert pd.isna(a) and pd.isna(b), f"«{funcion}» en «{clave}»: {a} vs {b}"
        else:
            assert a == pytest.approx(b), f"«{funcion}» en «{clave}»: {a} vs {b}"


def test_agrupar_con_count_cuenta_filas():
    origen = _fuente()
    esperado = origen.groupby("ciclo", observed=True).size().sort_index().tolist()
    t = _tabla([ESTADOS, ("g", "datos.agrupar", "G",
                          {"por": ["ciclo"], "columnas": ["precio_m2"], "funcion": "count"})],
               [("d", "datos", "g", "datos")], "g")
    assert t.set_index("ciclo")["precio_m2"].sort_index().tolist() == esperado


# --- Ordenar, seleccionar, remodelar ---------------------------------------

def test_ordenar_descendente_pone_el_mayor_primero():
    t = _tabla([ESTADOS, ("o", "datos.ordenar", "O",
                          {"por": ["precio_m2"], "descendente": True})],
               [("d", "datos", "o", "datos")], "o")
    valores = t["precio_m2"].astype(float).tolist()
    assert valores == sorted(valores, reverse=True)


def test_seleccionar_quitar_es_el_complemento_de_conservar():
    columnas = ["entidad", "precio_m2"]
    conservadas = _tabla([ESTADOS, ("s", "datos.seleccionar", "S",
                                    {"columnas": columnas, "modo": "conservar"})],
                         [("d", "datos", "s", "datos")], "s").columns.tolist()
    assert sorted(conservadas) == sorted(columnas)


def test_remodelar_a_largo_multiplica_las_filas_por_las_columnas():
    origen = _fuente()
    t = _tabla([ESTADOS, ("r", "datos.remodelar", "R",
                          {"direccion": "a_largo", "identificadores": ["entidad"],
                           "columnas": ["precio_m2", "escolaridad_anios"]})],
               [("d", "datos", "r", "datos")], "r")
    assert len(t) == len(origen) * 2, "a largo, cada fila se vuelve una por columna"
    assert set(t["variable"]) == {"precio_m2", "escolaridad_anios"}


# --- Unir -------------------------------------------------------------------

def test_unir_por_la_izquierda_conserva_todas_las_filas_de_la_izquierda():
    origen = _fuente()
    nodos = [ESTADOS,
             ("g", "datos.agrupar", "Promedio por ciclo",
              {"por": ["ciclo"], "columnas": ["precio_m2"], "funcion": "mean"}),
             ("u", "datos.unir", "Unir",
              {"llave_izquierda": ["ciclo"], "llave_derecha": ["ciclo"], "tipo": "izquierda"})]
    aristas = [("d", "datos", "g", "datos"),
               ("d", "datos", "u", "izquierda"), ("g", "datos", "u", "derecha")]
    t = _tabla(nodos, aristas, "u")
    assert len(t) == len(origen), "una unión por la izquierda no puede perder filas"


# --- Transformaciones -------------------------------------------------------

def test_el_rezago_mira_al_pasado_y_no_al_futuro():
    """El error mas caro de todos: un rezago del signo contrario deja que el
    modelo vea el futuro, y ningun diagnostico lo delata.

    Se comprueba sobre una serie simple: al declarar un panel, la entidad y el
    periodo pasan a ser el indice y dejan de ser columnas de la tabla.
    """
    nodos = [("d", "datos.ejemplo", "Macro", {"conjunto": "mexico_macro"}),
             ("s", "datos.serie_temporal", "Serie",
              {"columna_fecha": "fecha", "frecuencia": "QS"}),
             ("l", "transformar.rezago", "Rezago",
              {"columnas": ["pib_indice"], "periodos": 1})]
    t = _tabla(nodos, [("d", "datos", "s", "datos"), ("s", "datos", "l", "datos")], "l")
    col = next(c for c in t.columns if c.startswith("rez1_"))
    actual = t["pib_indice"].astype(float).tolist()
    rezagada = pd.to_numeric(t[col], errors="coerce").tolist()
    assert pd.isna(rezagada[0]), "el primer periodo no puede tener rezago"
    for i in range(1, len(actual)):
        assert rezagada[i] == pytest.approx(actual[i - 1]), (
            "el rezago no trae el valor del periodo ANTERIOR")


def test_estandarizar_deja_media_cero_y_desviacion_uno():
    nodos = [ESTADOS, ("z", "transformar.estandarizar", "Z",
                       {"columnas": ["precio_m2"], "metodo": "z"})]
    t = _tabla(nodos, [("d", "datos", "z", "datos")], "z")
    col = next(c for c in t.columns if c != "precio_m2" and "precio_m2" in c)
    v = pd.to_numeric(t[col], errors="coerce").dropna()
    assert v.mean() == pytest.approx(0, abs=1e-6)
    assert v.std(ddof=0) == pytest.approx(1, abs=1e-6)


def test_winsorizar_recorta_las_colas_en_su_sitio():
    """Recorta la MISMA columna, a propósito: el nodo avisa que cambia los datos
    y lo deja escrito en la nota metodológica."""
    origen = _fuente()
    nodos = [ESTADOS, ("w", "transformar.winsorizar", "W",
                       {"columnas": ["precio_m2"], "percentil": 5.0})]
    t = _tabla(nodos, [("d", "datos", "w", "datos")], "w")
    assert len(t) == len(origen), "winsorizar recorta valores, no filas"
    v = pd.to_numeric(t["precio_m2"], errors="coerce")
    assert v.max() < origen["precio_m2"].max(), "el máximo tenía que bajar"
    assert v.min() > origen["precio_m2"].min(), "el mínimo tenía que subir"
    assert v.min() == pytest.approx(origen["precio_m2"].quantile(0.05))
    assert v.max() == pytest.approx(origen["precio_m2"].quantile(0.95))


def test_las_dummies_dejan_una_categoria_fuera():
    """Meter TODAS las indicadoras junto con la constante es colinealidad
    perfecta y la regresion no se puede estimar."""
    origen = _fuente()
    categorias = origen["ciclo"].nunique()
    nodos = [ESTADOS, ("i", "transformar.dummies", "D",
                       {"columnas": ["ciclo"], "quitar_primera": True})]
    t = _tabla(nodos, [("d", "datos", "i", "datos")], "i")
    nuevas = [c for c in t.columns if c.startswith("ciclo_")]
    assert len(nuevas) == categorias - 1, (
        f"con {categorias} categorías deben salir {categorias - 1} indicadoras")


def test_el_crecimiento_porcentual_es_el_cambio_relativo():
    nodos = [("d", "datos.ejemplo", "Macro", {"conjunto": "mexico_macro"}),
             ("g", "transformar.crecimiento", "Crecimiento",
              {"columnas": ["pib_indice"], "tipo": "porcentaje", "periodos": 1})]
    t = _tabla(nodos, [("d", "datos", "g", "datos")], "g")
    col = next(c for c in t.columns if "pib_indice" in c and c != "pib_indice")
    v = pd.to_numeric(t["pib_indice"], errors="coerce")
    g = pd.to_numeric(t[col], errors="coerce")
    esperado = v.pct_change(1) * 100
    assert g.dropna().round(6).tolist() == esperado.dropna().round(6).tolist()


# --- El orden temporal ------------------------------------------------------

def test_el_rezago_ordena_por_el_periodo_declarado():
    """`shift` toma la fila de ARRIBA, no la del periodo anterior.

    Si la tabla no viene ordenada, el rezago trae un periodo cualquiera y no hay
    diagnóstico que lo delate: sale un modelo que mira al futuro y se ve
    perfectamente sano. Con el periodo declarado, el bloque ordena antes.
    """
    from abak_core import a_texto, emitir

    nodos = [PANEL,
             ("p", "datos.panel", "Panel", {"entidad": "entidad", "periodo": "anio"}),
             ("l", "transformar.rezago", "Rezago",
              {"columnas": ["pib_per_capita"], "periodos": 1, "por_entidad": "entidad"})]
    aristas = [("d", "datos", "p", "datos"), ("p", "datos", "l", "datos")]
    texto = a_texto(emitir(compilar(grafo("orden", nodos, aristas))))
    assert "sort_values(['entidad', 'anio'], kind='stable')" in texto, texto[-1200:]


def test_sin_periodo_declarado_el_rezago_lo_dice():
    """No se puede adivinar el orden, así que se avisa en vez de fingir."""
    from abak_core import a_texto, emitir

    nodos = [PANEL,
             ("l", "transformar.rezago", "Rezago",
              {"columnas": ["pib_per_capita"], "periodos": 1, "por_entidad": "entidad"})]
    texto = a_texto(emitir(compilar(grafo("sin orden", nodos, [("d", "datos", "l", "datos")]))))
    assert "orden del archivo" in texto
    assert "sort_values" not in texto, "sin periodo declarado no puede inventarse un orden"


def test_el_rezago_desordenado_da_lo_mismo_que_el_ordenado():
    """La prueba de fondo: con las filas revueltas, el resultado no cambia.

    Se revuelve DESPUES de declarar la serie, que es el unico orden en el que
    esto muerde de verdad: «Definir serie temporal» y «Definir panel» ordenan
    ellos mismos al declarar el indice, asi que revolver antes no prueba nada.
    Un «Ordenar filas» colocado despues deshace ese orden, y sin el ordenamiento
    del propio rezago el desplazamiento trae el periodo equivocado en silencio.
    """
    nodos = [("d", "datos.ejemplo", "Macro", {"conjunto": "mexico_macro"}),
             ("s", "datos.serie_temporal", "Serie",
              {"columna_fecha": "fecha", "frecuencia": "QS"}),
             ("o", "datos.ordenar", "Revolver",
              {"por": ["pib_indice"], "descendente": True}),
             ("l", "transformar.rezago", "Rezago",
              {"columnas": ["pib_indice"], "periodos": 1})]
    aristas = [("d", "datos", "s", "datos"), ("s", "datos", "o", "datos"),
               ("o", "datos", "l", "datos")]
    t = _tabla(nodos, aristas, "l")
    col = next(c for c in t.columns if c.startswith("rez1_"))
    actual = t["pib_indice"].astype(float).tolist()
    rezagada = pd.to_numeric(t[col], errors="coerce").tolist()
    assert pd.isna(rezagada[0])
    for i in range(1, len(actual)):
        assert rezagada[i] == pytest.approx(actual[i - 1]), (
            "con las filas revueltas el rezago trajo el periodo equivocado")
