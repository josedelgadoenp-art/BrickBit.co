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


def test_sin_llave_la_interfaz_se_entera_y_le_dicen_que_hacer(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    estado = CLIENTE.get("/api/v1/asistente/estado").json()
    assert estado["disponible"] is False
    # El motivo trae el comando exacto: sin eso, la pantalla no da manera de
    # saber si falta configurar algo o si la función no existe.
    assert "setx ANTHROPIC_API_KEY" in estado["motivo"]
    assert "nueva" in estado["motivo"], "hay que avisar que setx no afecta a la ventana actual"

    r = CLIENTE.post("/api/v1/asistente", json={"peticion": "explica el precio de la vivienda"})
    assert r.status_code == 422
    assert "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_sin_el_paquete_instalado_se_dice_y_no_revienta(monkeypatch):
    """El caso que se colaba: la llave puesta pero el paquete sin instalar.

    `/estado` sólo miraba la llave, así que la interfaz ofrecía el asistente y
    la petición moría con un 500 sin explicación. El peor de los dos mundos:
    parece que funciona y falla sin decir por qué.
    """
    import builtins

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-de-prueba")
    real = builtins.__import__

    def sin_anthropic(nombre, *args, **kwargs):
        if nombre == "anthropic":
            raise ImportError("No module named 'anthropic'")
        return real(nombre, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", sin_anthropic)

    estado = CLIENTE.get("/api/v1/asistente/estado").json()
    assert estado["disponible"] is False
    assert "pip install" in estado["motivo"]

    r = CLIENTE.post("/api/v1/asistente", json={"peticion": "explica el precio de la vivienda"})
    assert r.status_code == 422, "debe ser un mensaje en español, no un 500"
    assert "pip install" in r.json()["detail"]


def test_una_peticion_vacia_no_llega_al_modelo():
    """Gastar una llamada en una cadena de dos letras no tiene sentido."""
    assert CLIENTE.post("/api/v1/asistente", json={"peticion": "a"}).status_code == 422


def test_una_llave_con_espacios_pegados_no_se_manda_asi(monkeypatch):
    """Copiar una llave arrastra espacios y saltos de línea con muchísima
    facilidad, y `setx` los guarda tal cual. La API responde 401 y se lee como
    «la llave está mal» cuando la llave está bien: sólo trae basura invisible.
    """
    import abak_api.asistente as modulo

    # Larga de verdad: si no, la caza el filtro de longitud antes de llegar al
    # cliente y esta prueba dejaría de probar lo que dice probar.
    falsa = "sk-ant-api03-" + "D" * 90
    monkeypatch.setenv("ANTHROPIC_API_KEY", f"  {falsa}  \n")
    vistas = {}

    class ClienteFalso:
        def __init__(self, api_key=None, **kw):
            vistas["llave"] = api_key
            raise RuntimeError("corta aquí: sólo interesa qué llave se construyó")

    monkeypatch.setattr(modulo, "revisar", lambda: (True, None))
    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", ClienteFalso)

    with pytest.raises(Exception):
        modulo.pedir_grafo("explica el precio de la vivienda")
    assert vistas["llave"] == falsa, "la llave viajó con espacios"


def test_algo_que_no_es_una_llave_se_dice_antes_de_gastar_una_llamada(monkeypatch):
    """Confundir la llave de la API con la contraseña de claude.ai es de lo más
    común. Se detecta por el prefijo, sin salir a la red."""
    import abak_api.asistente as modulo

    monkeypatch.setenv("ANTHROPIC_API_KEY", "mi-contrasena-de-claude")
    monkeypatch.setattr(modulo, "revisar", lambda: (True, None))
    with pytest.raises(modulo.ErrorAsistente) as exc:
        modulo.pedir_grafo("explica el precio de la vivienda")
    assert "sk-ant-" in str(exc.value)
    assert "console.anthropic.com" in str(exc.value)


def test_el_texto_de_relleno_de_un_instructivo_se_caza_por_largo(monkeypatch):
    """El caso real: alguien copió «sk-ant-tu-llave» de mis propias
    instrucciones. Empieza con el prefijo correcto, así que el filtro anterior
    lo dejaba pasar y sólo se descubría con un 401, que se lee como «mi llave
    está mal» en vez de «pegué el ejemplo»."""
    import abak_api.asistente as modulo

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-tu-llave")
    monkeypatch.setattr(modulo, "revisar", lambda: (True, None))
    with pytest.raises(modulo.ErrorAsistente) as exc:
        modulo.pedir_grafo("explica el precio de la vivienda")
    mensaje = str(exc.value)
    assert "15 caracteres" in mensaje
    assert "ejemplo" in mensaje


def test_el_estado_dice_que_llave_tiene_EL_SERVIDOR(monkeypatch):
    """`setx` no toca los procesos abiertos.

    Un servidor arrancado antes de configurar la llave se queda con la vieja
    para siempre, y en pantalla eso se ve idéntico a una llave mal escrita. La
    huella —longitud y prefijo, nunca la llave— hace que el proceso rancio se
    delate solo, sin revelar el secreto.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-" + "K" * 90)
    llave = CLIENTE.get("/api/v1/asistente/estado").json()["llave"]
    assert llave["hay"] is True
    assert llave["longitud"] == 103
    assert llave["prefijo"] == "sk-ant-api0"
    # Lo que NO puede pasar: que la llave entera viaje al navegador.
    assert "K" * 20 not in str(llave)


def test_sin_llave_la_huella_no_inventa_nada(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert CLIENTE.get("/api/v1/asistente/estado").json()["llave"] == {"hay": False}


def test_un_error_de_la_api_no_se_traga_su_motivo():
    """Un 400 de Anthropic explica exactamente qué está mal.

    Enseñar sólo «error (400)» le quita a la persona lo único que resuelve el
    problema. Pasó de verdad: un 400 que no decía si era el modelo, la salida
    estructurada o la caché.
    """
    from abak_api.asistente import _motivo_api

    class ErrorFalso(Exception):
        status_code = 400
        body = {"type": "error",
                "error": {"type": "invalid_request_error",
                          "message": "model: claude-opus-5 not found"}}

    assert _motivo_api(ErrorFalso()) == "model: claude-opus-5 not found"


def test_si_el_error_no_trae_cuerpo_igual_se_dice_algo():
    from abak_api.asistente import _motivo_api

    class Pelado(Exception):
        status_code = 500
        body = None

    assert _motivo_api(Pelado()) != ""


def test_la_prueba_de_conexion_avisa_si_falta_configuracion(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = CLIENTE.get("/api/v1/asistente/prueba").json()
    assert r["ok"] is False
    assert r["etapa"] == "configuracion"
