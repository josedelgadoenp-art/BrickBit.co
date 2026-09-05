"""Invariantes del registro. Todo esto falla al importar, no en producción."""

import pytest

from abaco_core.codegen.contexto import resolver_ayudantes
from abaco_core.registry import AYUDANTES, FAMILIAS, REGISTRO, catalogo, todos


def test_hay_herramientas():
    assert len(REGISTRO) >= 50


@pytest.mark.parametrize("cls", list(REGISTRO.values()), ids=lambda c: c.op)
def test_toda_herramienta_se_explica(cls):
    """Un sistema que quiere ser más fácil que SPSS no puede tener nodos sin explicar.

    La explicación es el producto tanto como el cálculo: es lo que permite que
    alguien que no es econometrista sepa si la herramienta que abrió es la que
    necesita, y cómo leer lo que le salió.
    """
    a = cls.ayuda
    assert len(a.que_hace) > 30, f"{cls.op}: 'qué hace' demasiado corto"
    assert len(a.cuando_usarlo) > 25, f"{cls.op}: falta 'cuándo usarlo'"
    assert len(a.interpretacion) > 30, f"{cls.op}: falta cómo leer el resultado"


@pytest.mark.parametrize("cls", list(REGISTRO.values()), ids=lambda c: c.op)
def test_puertos_y_familia_consistentes(cls):
    assert cls.familia in FAMILIAS
    assert cls.op.startswith(f"{cls.familia}.")
    for p in list(cls.entradas) + list(cls.salidas):
        assert p.tipo, f"{cls.op}: puerto {p.nombre} sin tipo"


@pytest.mark.parametrize("cls", list(REGISTRO.values()), ids=lambda c: c.op)
def test_esquema_de_params_es_serializable(cls):
    import json

    json.dumps(cls.esquema_params())


def test_ayudantes_sin_ciclos():
    """El cierre transitivo de todos los ayudantes tiene que resolver."""
    orden = resolver_ayudantes(list(AYUDANTES))
    assert len(orden) == len(AYUDANTES)
    vistos = set()
    for a in orden:
        assert set(a.depende_de) <= vistos, f"{a.nombre} se emite antes que sus dependencias"
        vistos.add(a.nombre)


def test_ayudantes_definen_su_nombre():
    for nombre, ayudante in AYUDANTES.items():
        ayudante.como_ast()  # valida que el bloque defina `nombre`


def test_catalogo_completo():
    c = catalogo()
    assert len(c["nodos"]) == len(REGISTRO)
    assert {f["id"] for f in c["familias"]} >= {n["familia"] for n in c["nodos"]}
    for tipo in c["tipos"].values():
        assert tipo["color"].startswith("#")


def test_familias_no_vacias():
    """Una familia sin herramientas es una pestaña vacía en la paleta."""
    vacias = [f.id for f in FAMILIAS.values() if not list(todos(f.id))]
    assert not vacias, f"Familias sin herramientas: {vacias}"
