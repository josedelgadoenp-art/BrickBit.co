"""El asistente: pides el análisis en español y Abak lo arma.

La decisión de diseño que sostiene todo lo demás: **el modelo no escribe
código, escribe un GRAFO**. Su única salida posible es una lista de bloques del
catálogo con sus parámetros, y eso pasa por la misma validación de Pydantic y
el mismo compilador que un análisis armado a mano. Un `op` que no existe se
rechaza; un parámetro con el tipo equivocado se rechaza; una conexión entre
puertos incompatibles se rechaza.

Eso significa que el peor caso de una alucinación es un grafo que no compila y
un mensaje de error — nunca código arbitrario ejecutándose en la máquina de
nadie. Si el modelo pudiera emitir Python, esta función sería la vulnerabilidad
más grande del producto; emitiendo grafos, es la más contenida.

La llave de la API vive SÓLO en el entorno del servidor. Nunca viaja al
navegador, nunca se guarda en el grafo y nunca sale en el script exportado.
"""

from __future__ import annotations

import json
import os
from typing import Any

MODELO = "claude-opus-5"
TOPE_SALIDA = 16_000
# Un grafo razonable son decenas de bloques. El tope evita que una petición
# ambigua devuelva un análisis de doscientos pasos que nadie va a revisar.
TOPE_NODOS = 40


class ErrorAsistente(Exception):
    """Algo impidió construir el análisis. Lleva un mensaje para la persona."""


# El esquema de la respuesta. Con `output_config.format` el modelo no puede
# devolver otra forma: no hay que parsear prosa ni rezarle a un bloque de texto.
ESQUEMA_RESPUESTA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "explicacion": {
            "type": "string",
            "description": "Qué análisis armaste y por qué, en 2-4 frases, en español de México. "
                           "Dirigido a un economista, no a un programador.",
        },
        "advertencias": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Supuestos que tomaste, datos que faltan, o límites de lo que armaste. "
                           "Vacío si no hay ninguno. Nunca inventes columnas que no existen: si "
                           "falta algo, dilo aquí en vez de suponerlo.",
        },
        "nodos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Identificador corto y único, ej. «n1»."},
                    "op": {"type": "string", "description": "El `op` exacto de una herramienta del catálogo."},
                    "etiqueta": {"type": "string", "description": "Nombre en español para este paso."},
                    "params": {"type": "object", "description": "Parámetros según el esquema de esa herramienta."},
                    "notas": {"type": "string", "description": "Por qué este paso. Sale como comentario en el código."},
                },
                "required": ["id", "op", "etiqueta", "params", "notas"],
                "additionalProperties": False,
            },
        },
        "aristas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "origen": {"type": "string"},
                    "puerto_origen": {"type": "string"},
                    "destino": {"type": "string"},
                    "puerto_destino": {"type": "string"},
                },
                "required": ["origen", "puerto_origen", "destino", "puerto_destino"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["explicacion", "advertencias", "nodos", "aristas"],
    "additionalProperties": False,
}


def catalogo_para_el_modelo() -> str:
    """El catálogo de herramientas, tal como lo publica el registro.

    Se arma del MISMO registro que alimenta la paleta, así que una herramienta
    nueva queda disponible para el asistente sin tocar este archivo. Mantener
    dos listas es garantizar que se separen.
    """
    from abak_core.registry import cargar_todos, catalogo

    cargar_todos()
    cat = catalogo()
    lineas: list[str] = []
    for familia in cat["familias"]:
        nodos = [n for n in cat["nodos"] if n["familia"] == familia["id"]]
        if not nodos:
            continue
        lineas.append(f"\n## {familia['titulo']} — {familia['descripcion']}")
        for n in nodos:
            ayuda = n.get("ayuda") or {}
            entradas = ", ".join(f"{p['nombre']}:{p['tipo']}" for p in n.get("entradas") or []) or "—"
            salidas = ", ".join(f"{p['nombre']}:{p['tipo']}" for p in n.get("salidas") or []) or "—"
            lineas.append(
                f"\n### {n['op']} — {n['titulo']}\n"
                f"{ayuda.get('que_hace', '')}\n"
                f"Cuándo: {ayuda.get('cuando_usarlo', '')}\n"
                f"entradas: {entradas} | salidas: {salidas}\n"
                f"params: {json.dumps(n['params_schema'].get('properties', {}), ensure_ascii=False)}"
            )
    return "\n".join(lineas)


INSTRUCCIONES = """Eres el asistente de Abak, un programa de análisis económico sin código.

Tu trabajo: convertir lo que una persona pide en español en un GRAFO de bloques
del catálogo. No escribes código. No inventas herramientas. Sólo compones las
que existen.

Reglas que no se rompen:

1. Usa ÚNICAMENTE los `op` del catálogo, tal cual están escritos.
2. Usa ÚNICAMENTE los nombres de columna que aparezcan en los datos descritos.
   Si te falta una columna para lo que te piden, NO la inventes ni la sustituyas
   por otra parecida: arma lo que sí se pueda y dilo en `advertencias`.
3. Conecta cada bloque a sus entradas obligatorias. El análisis se lee de
   izquierda a derecha: los datos primero, después las transformaciones,
   después la estimación, al final los gráficos.
4. Si la pregunta es CAUSAL («¿el metro subió los precios?», «¿qué efecto tuvo
   la remodelación?»), usa `causal.efecto` y dibuja las flechas del grafo con lo
   que sepas del problema. Si es descriptiva o de pronóstico, usa MCO, ARIMA,
   panel o lo que corresponda.
5. Los logaritmos, rezagos y diferencias son bloques de la familia
   «transformar»: no los metas como si fueran parámetros de la regresión.
6. Prefiere el análisis más simple que conteste la pregunta. Un grafo de 30
   pasos que nadie revisa es peor que uno de 6 que se entiende.

Sobre honestidad, que es el principio de la casa:

- Si lo que piden no se puede con los datos que hay, dilo en `advertencias` y
  arma lo más cercano que sí se pueda. No rellenes con supuestos silenciosos.
- Si la pregunta es causal pero no hay con qué identificar el efecto, dilo.
- Nunca prometas en `explicacion` algo que el grafo no hace."""


def _describir_datos(esquemas: list[dict[str, Any]] | None) -> str:
    if not esquemas:
        return ("No hay datos cargados todavía. Si el análisis los necesita, empieza con "
                "`datos.ejemplo` (conjuntos: mexico_estados, mexico_macro, panel_estados, "
                "insumo_producto, hogares) y dilo en las advertencias.")
    partes = []
    for e in esquemas:
        cols = ", ".join(f"{c['nombre']} ({c['tipo']})" for c in e.get("columnas", []))
        partes.append(f"- Bloque «{e.get('etiqueta', '?')}» (id {e.get('nodo_id')}): {cols}")
    return "Datos disponibles en el lienzo:\n" + "\n".join(partes)


def armar_grafo(respuesta: dict[str, Any]) -> dict[str, Any]:
    """Convierte la respuesta del modelo en un grafo válido de Abak.

    Aquí es donde una alucinación se vuelve un mensaje de error en vez de un
    problema: todo pasa por el validador y el compilador de siempre.
    """
    from abak_core import GrafoSpec, compilar
    from abak_core.registry import REGISTRO, cargar_todos

    cargar_todos()
    nodos = respuesta.get("nodos") or []
    if not nodos:
        raise ErrorAsistente("El asistente no propuso ningún paso. Prueba a pedirlo con más detalle.")
    if len(nodos) > TOPE_NODOS:
        raise ErrorAsistente(
            f"El asistente propuso {len(nodos)} pasos y el tope son {TOPE_NODOS}. "
            f"Pide algo más acotado.")

    desconocidos = sorted({n.get("op", "") for n in nodos} - set(REGISTRO))
    if desconocidos:
        raise ErrorAsistente(
            "El asistente nombró herramientas que no existen: " + ", ".join(desconocidos) +
            ". Vuelve a intentarlo; si se repite, pídelo de otra manera.")

    # Posiciones: el modelo no las da, y no debería. Se colocan en cascada para
    # que el análisis se lea de izquierda a derecha, como el resto de Abak.
    hijos: dict[str, int] = {}
    columna: dict[str, int] = {}
    for arista in respuesta.get("aristas") or []:
        hijos[arista["destino"]] = hijos.get(arista["destino"], 0) + 1
    for i, n in enumerate(nodos):
        columna[n["id"]] = i

    grafo = {
        "nodos": [
            {
                "id": n["id"],
                "op": n["op"],
                "etiqueta": n.get("etiqueta") or n["op"],
                "params": n.get("params") or {},
                "notas": n.get("notas") or None,
                "posicion": {"x": 120 + 330 * (columna[n["id"]] % 4),
                             "y": 90 + 190 * (columna[n["id"]] // 4)},
            }
            for n in nodos
        ],
        "aristas": respuesta.get("aristas") or [],
    }

    spec = GrafoSpec.model_validate(grafo)   # tipos y parámetros
    programa = compilar(spec)                 # puertos, ciclos, columnas
    return {
        "grafo": grafo,
        "explicacion": respuesta.get("explicacion", ""),
        "advertencias": respuesta.get("advertencias") or [],
        "diagnosticos": [d.model_dump() for d in programa.diagnosticos],
    }


def pedir_grafo(peticion: str, esquemas: list[dict[str, Any]] | None = None,
                grafo_actual: dict[str, Any] | None = None) -> dict[str, Any]:
    """Le pide a Claude que arme el análisis y devuelve el grafo ya validado."""
    import anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ErrorAsistente(
            "Falta la llave de la API de Anthropic. Ponla en la variable de entorno "
            "ANTHROPIC_API_KEY antes de arrancar el servidor y vuelve a intentarlo.")

    cliente = anthropic.Anthropic()
    contexto = catalogo_para_el_modelo()

    partes = [_describir_datos(esquemas)]
    if grafo_actual and grafo_actual.get("nodos"):
        partes.append("El lienzo ya trae este análisis; puedes extenderlo o rehacerlo:\n"
                      + json.dumps(grafo_actual, ensure_ascii=False)[:8000])
    partes.append(f"Lo que se pide:\n{peticion.strip()}")

    try:
        with cliente.messages.stream(
            model=MODELO,
            max_tokens=TOPE_SALIDA,
            thinking={"type": "adaptive"},
            # El catálogo es idéntico en cada petición: se cachea y el resto de
            # las llamadas cuesta una fracción.
            system=[
                {"type": "text", "text": INSTRUCCIONES},
                {"type": "text", "text": f"# Catálogo de herramientas\n{contexto}",
                 "cache_control": {"type": "ephemeral"}},
            ],
            output_config={"format": {"type": "json_schema", "schema": ESQUEMA_RESPUESTA}},
            messages=[{"role": "user", "content": "\n\n".join(partes)}],
        ) as flujo:
            mensaje = flujo.get_final_message()
    except anthropic.AuthenticationError as exc:
        raise ErrorAsistente("La llave de la API de Anthropic no es válida.") from exc
    except anthropic.RateLimitError as exc:
        raise ErrorAsistente("La API de Anthropic está limitando las peticiones. "
                             "Espera un momento y vuelve a intentarlo.") from exc
    except anthropic.APIStatusError as exc:
        raise ErrorAsistente(f"La API de Anthropic respondió con un error ({exc.status_code}).") from exc
    except anthropic.APIConnectionError as exc:
        raise ErrorAsistente("No se pudo conectar con la API de Anthropic. Revisa tu red.") from exc

    if mensaje.stop_reason == "refusal":
        raise ErrorAsistente("El modelo declinó esta petición. Pruébala de otra forma.")

    texto = next((b.text for b in mensaje.content if b.type == "text"), None)
    if not texto:
        raise ErrorAsistente("El asistente no devolvió nada utilizable.")
    try:
        respuesta = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ErrorAsistente("El asistente devolvió una respuesta que no se pudo leer.") from exc

    resultado = armar_grafo(respuesta)
    resultado["uso"] = {
        "entrada": mensaje.usage.input_tokens,
        "salida": mensaje.usage.output_tokens,
        "cache_leido": getattr(mensaje.usage, "cache_read_input_tokens", 0),
    }
    return resultado
