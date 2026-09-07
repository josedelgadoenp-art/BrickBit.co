"""El motor causal, contra los casos donde la respuesta correcta se conoce.

Aquí no se prueba «que no truene»: se prueba que dé la MISMA respuesta que da
Pearl. Un conjunto de ajuste mal calculado no falla ruidosamente — produce un
coeficiente con su error estándar y sus estrellas, perfectamente presentable y
perfectamente equivocado. Si esta suite no es dura, la herramienta miente con
buena presentación.
"""

from __future__ import annotations

import pytest

from abak_core.causal import ErrorCausal, GrafoCausal, Papel, clasificar, conjunto_ajuste
from abak_core.causal.grafo import conjuntos_alternativos


def g(*arcos: str) -> GrafoCausal:
    """`g("z->t", "z->y", "t->y")` — se lee como se dibuja."""
    return GrafoCausal([tuple(a.split("->")) for a in arcos])  # type: ignore[misc]


# --------------------------------------------------------------- confusión ---

def test_confusion_clasica_hay_que_controlar_el_confusor():
    """Z causa al tratamiento y al resultado: sin controlarlo, el efecto sale sesgado."""
    grafo = g("z->t", "z->y", "t->y")
    assert conjunto_ajuste(grafo, "t", "y") == {"z"}
    assert clasificar(grafo, "t", "y", {"z"})["z"] is Papel.CONFUSOR


def test_dos_confusores_se_controlan_los_dos():
    grafo = g("a->t", "a->y", "b->t", "b->y", "t->y")
    assert conjunto_ajuste(grafo, "t", "y") == {"a", "b"}


def test_basta_con_cerrar_el_camino_una_vez():
    """u → z → t y u → y: controlar z cierra el camino; no hace falta u también."""
    grafo = g("u->z", "z->t", "u->y", "t->y")
    ajuste = conjunto_ajuste(grafo, "t", "y")
    assert ajuste in ({"z"}, {"u"}), ajuste
    assert len(ajuste) == 1, "el conjunto no es mínimo"


# --------------------------------------------------------------- mediación ---

def test_un_mediador_no_se_controla():
    """T → M → Y: controlar M borra justo el efecto que se quiere medir."""
    grafo = g("t->m", "m->y")
    assert conjunto_ajuste(grafo, "t", "y") == set()
    assert clasificar(grafo, "t", "y", set())["m"] is Papel.MEDIADOR


def test_el_mediador_no_se_controla_ni_habiendo_confusion():
    grafo = g("z->t", "z->y", "t->m", "m->y", "t->y")
    ajuste = conjunto_ajuste(grafo, "t", "y")
    assert ajuste == {"z"}
    assert "m" not in ajuste
    assert clasificar(grafo, "t", "y", ajuste)["m"] is Papel.MEDIADOR


def test_un_descendiente_del_tratamiento_no_se_controla():
    grafo = g("t->y", "t->d")
    assert conjunto_ajuste(grafo, "t", "y") == set()
    assert clasificar(grafo, "t", "y", set())["d"] is Papel.DESCENDIENTE


# ------------------------------------------------------------ colisionador ---

def test_sesgo_m_el_colisionador_se_deja_fuera():
    """El caso que engaña a todo el mundo.

    u1 → t, u1 → c, u2 → c, u2 → y. El camino t ← u1 → c ← u2 → y YA está
    cerrado, porque c es un colisionador libre. Controlar c lo ABRE e inventa
    correlación. La respuesta correcta es no controlar nada.
    """
    grafo = g("u1->t", "u1->c", "u2->c", "u2->y", "t->y")
    assert conjunto_ajuste(grafo, "t", "y") == set()

    papeles = clasificar(grafo, "t", "y", set())
    assert papeles["c"] is Papel.COLISIONADOR
    # u1 llega a «y» sólo a través de «t»: es causa del tratamiento, NO confusor.
    assert papeles["u1"] is Papel.CAUSA_DEL_TRATAMIENTO
    assert papeles["u2"] is Papel.PREDICTOR


def test_controlar_el_colisionador_rompe_el_criterio():
    """Verificación directa: con «c» adentro, la puerta trasera deja de cerrarse."""
    grafo = g("u1->t", "u1->c", "u2->c", "u2->y", "t->y")
    assert grafo.cumple_puerta_trasera("t", "y", set())
    assert not grafo.cumple_puerta_trasera("t", "y", {"c"})
    # Metiendo también u1 o u2 se vuelve a cerrar.
    assert grafo.cumple_puerta_trasera("t", "y", {"c", "u1"})


def test_un_colisionador_puro_no_estorba_si_se_deja_en_paz():
    grafo = g("t->c", "y->c", "t->y")
    assert conjunto_ajuste(grafo, "t", "y") == set()


# --------------------------------------------------------- identificación ---

def test_sin_la_variable_que_hace_falta_no_se_puede_y_se_dice():
    """Si el confusor no está entre las columnas, NO hay regresión que lo salve."""
    grafo = g("u->t", "u->y", "t->y")
    assert conjunto_ajuste(grafo, "t", "y", disponibles=set()) is None
    assert conjunto_ajuste(grafo, "t", "y", disponibles={"u"}) == {"u"}


def test_conjuntos_alternativos_para_probar_robustez():
    grafo = g("u->z", "z->t", "u->y", "t->y")
    alternativos = conjuntos_alternativos(grafo, "t", "y")
    assert {"z"} in alternativos and {"u"} in alternativos


# ------------------------------------------------------------- estructura ---

def test_un_ciclo_se_rechaza_y_se_nombra():
    with pytest.raises(ErrorCausal) as exc:
        g("a->b", "b->c", "c->a")
    assert "ciclo" in str(exc.value).lower()
    assert "→" in str(exc.value)


def test_una_variable_no_se_causa_a_si_misma():
    with pytest.raises(ErrorCausal):
        g("a->a")


def test_una_variable_fuera_del_grafo_se_dice_claro():
    with pytest.raises(ErrorCausal) as exc:
        conjunto_ajuste(g("a->b"), "a", "z")
    assert "«z»" in str(exc.value)


def test_ancestros_y_descendientes():
    grafo = g("a->b", "b->c", "c->d")
    assert grafo.ancestros("d") == {"a", "b", "c"}
    assert grafo.descendientes("a") == {"b", "c", "d"}
    assert grafo.ancestros("a") == set()


# ------------------------------------------------------------ inmobiliario ---

def test_el_metro_subio_los_precios_o_lo_pusieron_donde_ya_subian():
    """La pregunta que da dinero, y por qué no se contesta con una regresión suelta.

    El gobierno pone estaciones donde ya hay demanda; la demanda también empuja
    el precio. Sin controlar la demanda previa, al metro se le acredita algo que
    no hizo. Y «densidad», que llega DESPUÉS de la estación, es un mediador:
    controlarla escondería parte del efecto real.
    """
    grafo = g(
        "demanda_previa->estacion_metro",
        "demanda_previa->precio_m2",
        "estacion_metro->precio_m2",
        "estacion_metro->densidad",
        "densidad->precio_m2",
        "ingreso_zona->precio_m2",
    )
    ajuste = conjunto_ajuste(grafo, "estacion_metro", "precio_m2")
    assert ajuste == {"demanda_previa"}

    papeles = clasificar(grafo, "estacion_metro", "precio_m2", ajuste)
    assert papeles["demanda_previa"] is Papel.CONFUSOR
    assert papeles["densidad"] is Papel.MEDIADOR
    assert papeles["ingreso_zona"] is Papel.PREDICTOR
