"""El asistente: que una alucinación acabe en un mensaje, no en un problema.

La propiedad que hay que defender aquí es que el modelo **no escribe código**:
su única salida posible es un grafo de bloques del catálogo, y ese grafo pasa
por la misma validación que uno armado a mano. Estas pruebas comprueban que la
puerta está cerrada, sin llamar a la API: lo que se prueba es NUESTRO lado.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from abak_api.asistente import (ESQUEMA_RESPUESTA, ErrorAsistente, armar_grafo,
                                catalogo_para_el_modelo)
from abak_api.main import app

CLIENTE = TestClient(app)


# Una respuesta realista del modelo: precio hedónico sobre los datos de ejemplo.
RESPUESTA_BUENA = {
    "explicacion": "Armé un modelo hedónico: explico el precio por m² con el ingreso del hogar "
                   "y la escolaridad, en logaritmos, con errores robustos.",
    "advertencias": ["Los datos son de corte transversal: esto mide asociación, no efecto causal."],
    "nodos": [
        {"id": "n1", "op": "datos.ejemplo", "etiqueta": "Datos de ejemplo",
         "params": {"conjunto": "mexico_estados"}, "notas": "Corte transversal de las 32 entidades."},
        {"id": "n2", "op": "econometria.mco", "etiqueta": "Modelo hedónico",
         "params": {"y": "precio_m2", "x": ["ingreso_hogar_mensual", "escolaridad_anios"],
                    "errores": "HC1"},
         "notas": "MCO con errores robustos a heterocedasticidad."},
    ],
    "aristas": [{"origen": "n1", "puerto_origen": "datos",
                 "destino": "n2", "puerto_destino": "datos"}],
}


def test_el_catalogo_sale_del_registro_de_verdad():
    """Si el catálogo se escribiera a mano, se separaría del registro."""
    texto = catalogo_para_el_modelo()
    assert "econometria.mco" in texto
    assert "causal.efecto" in texto          # las herramientas nuevas entran solas
    assert "entradas:" in texto and "params:" in texto
    assert len(texto) > 5000


def test_una_respuesta_valida_se_vuelve_un_grafo_que_compila():
    resultado = armar_grafo(RESPUESTA_BUENA)
    grafo = resultado["grafo"]
    assert [n["op"] for n in grafo["nodos"]] == ["datos.ejemplo", "econometria.mco"]
    assert not [d for d in resultado["diagnosticos"] if d["severidad"] == "error"]
    # Las posiciones las pone Abak: el modelo no sabe de píxeles.
    assert all("posicion" in n for n in grafo["nodos"])
    assert resultado["advertencias"]


def test_una_herramienta_inventada_se_rechaza_por_nombre():
    """El caso clásico de alucinación: un `op` que suena bien y no existe."""
    respuesta = json.loads(json.dumps(RESPUESTA_BUENA))
    respuesta["nodos"][1]["op"] = "econometria.regresion_magica"
    with pytest.raises(ErrorAsistente) as exc:
        armar_grafo(respuesta)
    assert "no existen" in str(exc.value)
    assert "econometria.regresion_magica" in str(exc.value)


def _errores(respuesta: dict) -> list[str]:
    """Los errores que el compilador le pone al grafo propuesto.

    No se lanza excepción a propósito: el grafo se devuelve igual, para que la
    persona VEA lo que el asistente intentó y dónde falló, en vez de recibir un
    «no se pudo» sin más.
    """
    return [d["mensaje"] for d in armar_grafo(respuesta)["diagnosticos"]
            if d["severidad"] == "error"]


def test_un_parametro_con_el_tipo_equivocado_lo_caza_el_compilador():
    respuesta = json.loads(json.dumps(RESPUESTA_BUENA))
    respuesta["nodos"][1]["params"]["x"] = "ingreso_hogar_mensual"   # debe ser lista
    assert any("lista" in e or "list" in e for e in _errores(respuesta))


def test_un_parametro_que_no_existe_lo_caza_el_compilador():
    """`extra="forbid"` en los Params: un campo inventado no pasa."""
    respuesta = json.loads(json.dumps(RESPUESTA_BUENA))
    respuesta["nodos"][1]["params"]["hacer_trampa"] = True
    assert any("hacer_trampa" in e for e in _errores(respuesta))


def test_una_columna_inventada_se_caza_contra_el_esquema_real():
    """La alucinación más probable: un nombre de columna que suena bien.

    El esquema se propaga por el grafo, así que el compilador sabe qué columnas
    existen de verdad en ese punto y no hay que confiar en el modelo.
    """
    respuesta = json.loads(json.dumps(RESPUESTA_BUENA))
    respuesta["nodos"][1]["params"]["y"] = "precio_por_metro_cuadrado"
    errores = _errores(respuesta)
    assert any("precio_por_metro_cuadrado" in e and "no existe" in e for e in errores), errores


def test_una_conexion_entre_puertos_que_no_existen_la_caza_el_compilador():
    respuesta = json.loads(json.dumps(RESPUESTA_BUENA))
    respuesta["aristas"][0]["puerto_destino"] = "inventado"
    resultado = armar_grafo(respuesta)
    assert [d for d in resultado["diagnosticos"] if d["severidad"] == "error"]


def test_no_se_acepta_un_analisis_de_doscientos_pasos():
    respuesta = json.loads(json.dumps(RESPUESTA_BUENA))
    respuesta["nodos"] = [
        {"id": f"n{i}", "op": "datos.ejemplo", "etiqueta": "x",
         "params": {"conjunto": "mexico_estados"}, "notas": ""} for i in range(60)
    ]
    respuesta["aristas"] = []
    with pytest.raises(ErrorAsistente) as exc:
        armar_grafo(respuesta)
    assert "tope" in str(exc.value)


def test_una_respuesta_vacia_se_dice_en_español():
    with pytest.raises(ErrorAsistente) as exc:
        armar_grafo({"explicacion": "", "advertencias": [], "nodos": [], "aristas": []})
    assert "ningún paso" in str(exc.value)


def test_el_esquema_de_respuesta_es_estricto():
    """Sin `additionalProperties: false` el modelo puede colar campos sueltos."""
    assert ESQUEMA_RESPUESTA["additionalProperties"] is False
    for clave in ("nodos", "aristas"):
        assert ESQUEMA_RESPUESTA["properties"][clave]["items"]["additionalProperties"] is False
    assert set(ESQUEMA_RESPUESTA["required"]) == {"explicacion", "advertencias", "nodos", "aristas"}


def test_sin_llave_la_interfaz_se_entera_y_no_se_rompe(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert CLIENTE.get("/api/v1/asistente/estado").json() == {"disponible": False}

    r = CLIENTE.post("/api/v1/asistente", json={"peticion": "explica el precio de la vivienda"})
    assert r.status_code == 422
    assert "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_una_peticion_vacia_no_llega_al_modelo():
    """Gastar una llamada en una cadena de dos letras no tiene sentido."""
    assert CLIENTE.post("/api/v1/asistente", json={"peticion": "a"}).status_code == 422
