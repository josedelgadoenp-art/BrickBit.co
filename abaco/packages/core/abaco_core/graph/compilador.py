"""El compilador de nodos: del JSON del lienzo a un programa de Python.

Siete etapas. Las cinco primeras viven aqui y son de milisegundos: corren en la
API en cada cambio del lienzo, y son lo que alimenta la pestana Codigo en vivo y
los subrayados rojos sobre los nodos mal configurados.

    (1) Parsear    JSON de React Flow -> GrafoSpec
    (2) Resolver   buscar cada op en el registro, validar parametros
    (3) Verificar  tipos de puerto, puertos obligatorios, columnas existentes
    (4) Planear    ciclos, orden topologico, poda, cono ancestral
    (5) Bajar a IR lista plana de instrucciones con nombres de variable

La emision (6) y la ejecucion (7) viven en codegen/ y runtime/.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from ..registry.base import EspecNodo, ErrorRegistro, obtener
from .spec import Esquema, GrafoSpec, NodoSpec
from .tipos import acepta, explicar_incompatibilidad

PALABRAS_RESERVADAS = {
    "and", "as", "assert", "async", "await", "break", "class", "continue", "def",
    "del", "elif", "else", "except", "False", "finally", "for", "from", "global",
    "if", "import", "in", "is", "lambda", "None", "nonlocal", "not", "or", "pass",
    "raise", "return", "True", "try", "while", "with", "yield", "pd", "np", "sm",
    "plt", "px", "go", "xgb",
}


# ---------------------------------------------------------------------------
# Diagnosticos
# ---------------------------------------------------------------------------


class Diagnostico(BaseModel):
    severidad: Literal["error", "aviso", "info"] = "error"
    codigo: str
    mensaje: str
    nodo_id: str | None = None
    puerto: str | None = None
    param: str | None = None
    sugerencia: str | None = None


class ErrorCompilacion(Exception):
    def __init__(self, diagnosticos: list[Diagnostico]):
        self.diagnosticos = diagnosticos
        primero = diagnosticos[0].mensaje if diagnosticos else "grafo invalido"
        super().__init__(primero)


# ---------------------------------------------------------------------------
# IR
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Instruccion:
    """Una operacion del programa. Deliberadamente aburrida: sin control de flujo.

    Todo el poder expresivo vive en los nodos, no en el IR. Un IR con `if` y
    `for` seria un lenguaje, y entonces habria que disenar un lenguaje.
    """

    nodo_id: str
    op: str
    version: str
    etiqueta: str
    entradas: dict[str, str]      # puerto -> nombre de variable (varias van con \x00)
    salidas: dict[str, str]       # puerto -> nombre de variable que liga
    params: BaseModel
    esquemas_entrada: dict[str, Esquema]
    huella: str
    notas: str | None = None


@dataclass
class Programa:
    instrucciones: list[Instruccion] = field(default_factory=list)
    titulo: str = "Analisis"
    semilla: int = 42
    huella_grafo: str = ""
    diagnosticos: list[Diagnostico] = field(default_factory=list)
    esquemas: dict[str, dict[str, Esquema]] = field(default_factory=dict)
    orden: list[str] = field(default_factory=list)
    podados: list[str] = field(default_factory=list)

    @property
    def hay_errores(self) -> bool:
        return any(d.severidad == "error" for d in self.diagnosticos)


# ---------------------------------------------------------------------------
# Nombres de variable: parte del producto, no un detalle
# ---------------------------------------------------------------------------


def identificador(texto: str, respaldo: str = "resultado") -> str:
    """'Precios CDMX 2020' -> 'precios_cdmx_2020'.

    El script exportado lo van a leer personas. `var_0`, `var_1`, `var_2` es
    exactamente lo que hace que un codigo generado se sienta generado.
    """
    normal = unicodedata.normalize("NFKD", texto or "")
    ascii_ = "".join(c for c in normal if not unicodedata.combining(c))
    limpio = "".join(c if c.isalnum() else "_" for c in ascii_.lower())
    while "__" in limpio:
        limpio = limpio.replace("__", "_")
    limpio = limpio.strip("_")
    if not limpio or limpio[0].isdigit():
        limpio = f"{respaldo}_{limpio}".strip("_")
    if limpio in PALABRAS_RESERVADAS:
        limpio = f"{limpio}_"
    return limpio or respaldo


class Nombrador:
    """Reparte nombres de variable unicos y estables."""

    def __init__(self) -> None:
        self.usados: set[str] = set(PALABRAS_RESERVADAS)

    def nuevo(self, base: str, sufijo: str | None = None) -> str:
        raiz = identificador(base)
        if sufijo:
            raiz = f"{raiz}_{identificador(sufijo)}"
        if raiz not in self.usados:
            self.usados.add(raiz)
            return raiz
        n = 2
        while f"{raiz}_{n}" in self.usados:
            n += 1
        nombre = f"{raiz}_{n}"
        self.usados.add(nombre)
        return nombre


# ---------------------------------------------------------------------------
# (2) Resolver
# ---------------------------------------------------------------------------


def _resolver(grafo: GrafoSpec, diag: list[Diagnostico]) -> dict[str, type[EspecNodo]]:
    especs: dict[str, type[EspecNodo]] = {}
    vistos: set[str] = set()
    for nodo in grafo.nodos:
        if nodo.id in vistos:
            diag.append(Diagnostico(codigo="nodo_duplicado", nodo_id=nodo.id,
                                    mensaje=f"Hay dos nodos con el id {nodo.id!r}."))
            continue
        vistos.add(nodo.id)
        try:
            especs[nodo.id] = obtener(nodo.op)
        except ErrorRegistro as exc:
            diag.append(Diagnostico(codigo="op_desconocido", nodo_id=nodo.id, mensaje=str(exc)))
    return especs


def _validar_params(nodo: NodoSpec, spec: type[EspecNodo], diag: list[Diagnostico]) -> BaseModel | None:
    try:
        return spec.Params.model_validate(nodo.params)
    except ValidationError as exc:
        for err in exc.errors():
            campo = ".".join(str(p) for p in err["loc"]) or None
            diag.append(Diagnostico(
                codigo="param_invalido", nodo_id=nodo.id, param=campo,
                mensaje=f"{spec.titulo}: {_traducir_pydantic(err)}",
            ))
        return None


def _traducir_pydantic(err: dict[str, Any]) -> str:
    campo = ".".join(str(p) for p in err["loc"]) or "el parametro"
    tipo = err["type"]
    if tipo == "missing":
        return f"falta configurar «{campo}»."
    if tipo.startswith("greater_than"):
        return f"«{campo}» {err['msg'].replace('Input should be', 'debe ser')}."
    if tipo == "literal_error":
        return f"«{campo}» no admite ese valor. {err['msg']}"
    return f"«{campo}»: {err['msg']}"


# ---------------------------------------------------------------------------
# (3) Verificar tipos y conexiones
# ---------------------------------------------------------------------------


def _verificar_aristas(
    grafo: GrafoSpec, especs: dict[str, type[EspecNodo]], diag: list[Diagnostico]
) -> dict[str, dict[str, list[tuple[str, str]]]]:
    """Devuelve, por nodo, puerto de entrada -> [(nodo origen, puerto origen)]."""
    conexiones: dict[str, dict[str, list[tuple[str, str]]]] = {n.id: {} for n in grafo.nodos}

    for arista in grafo.aristas:
        so, sd = especs.get(arista.origen), especs.get(arista.destino)
        if arista.origen not in conexiones or arista.destino not in conexiones:
            diag.append(Diagnostico(codigo="arista_colgante",
                                    mensaje=f"Hay una conexion que apunta a un nodo que no existe ({arista.origen} -> {arista.destino})."))
            continue
        if so is None or sd is None:
            continue
        po, pd_ = so.puerto_salida(arista.puerto_origen), sd.puerto_entrada(arista.puerto_destino)
        if po is None:
            diag.append(Diagnostico(codigo="puerto_inexistente", nodo_id=arista.origen, puerto=arista.puerto_origen,
                                    mensaje=f"{so.titulo} no tiene una salida llamada {arista.puerto_origen!r}."))
            continue
        if pd_ is None:
            diag.append(Diagnostico(codigo="puerto_inexistente", nodo_id=arista.destino, puerto=arista.puerto_destino,
                                    mensaje=f"{sd.titulo} no tiene una entrada llamada {arista.puerto_destino!r}."))
            continue
        if not acepta(pd_.tipo, po.tipo):
            diag.append(Diagnostico(
                codigo="tipos_incompatibles", nodo_id=arista.destino, puerto=arista.puerto_destino,
                mensaje=f"«{so.titulo}» no se puede conectar a «{sd.titulo}». " + explicar_incompatibilidad(pd_.tipo, po.tipo),
            ))
            continue
        conexiones[arista.destino].setdefault(arista.puerto_destino, []).append((arista.origen, arista.puerto_origen))

    for nodo in grafo.nodos:
        spec = especs.get(nodo.id)
        if spec is None:
            continue
        for puerto in spec.entradas:
            llegadas = conexiones[nodo.id].get(puerto.nombre, [])
            if puerto.requerido and not llegadas:
                diag.append(Diagnostico(
                    codigo="entrada_faltante", nodo_id=nodo.id, puerto=puerto.nombre,
                    mensaje=f"«{spec.titulo}» necesita que le conectes {puerto.titulo or puerto.nombre}: {puerto.ayuda_tipo.lower()}.",
                ))
            if len(llegadas) > 1 and not puerto.multiple:
                diag.append(Diagnostico(
                    codigo="entrada_multiple", nodo_id=nodo.id, puerto=puerto.nombre,
                    mensaje=f"«{spec.titulo}» solo admite una conexion en {puerto.nombre!r}, y le llegan {len(llegadas)}.",
                ))
    return conexiones


def _verificar_columnas(
    nodo_id: str, spec: type[EspecNodo], params: BaseModel,
    esquemas: dict[str, Esquema], diag: list[Diagnostico],
) -> None:
    """Comprueba que las columnas citadas en los parametros existan de verdad.

    Es generico: se lee la pista `abaco.control` del JSON Schema, asi que un
    nodo nuevo obtiene esta validacion sin escribir una linea. Es lo que hace
    que cambiar un nodo aguas arriba marque en rojo, en el acto, los nodos de
    aguas abajo que se quedaron sin esa columna.
    """
    props = spec.esquema_params().get("properties", {})
    for campo, esquema_campo in props.items():
        pista = (esquema_campo.get("abaco") or {})
        control = pista.get("control")
        if control not in ("columna", "columnas"):
            continue
        esquema = esquemas.get(pista.get("puerto", "datos"))
        if esquema is None or not esquema.columnas:
            continue  # sin esquema conocido no se puede afirmar nada
        valor = getattr(params, campo, None)
        pedidas = [valor] if control == "columna" else list(valor or [])
        # El indice temporal y el id de entidad no son columnas del DataFrame, pero
        # si son direccionables: los nodos de grafico hacen reset_index() antes de
        # dibujar, y pedir "no puedes usar tu columna de fecha" seria absurdo.
        direccionables = set(esquema.nombres())
        direccionables.update(x for x in (esquema.indice_temporal, esquema.id_entidad) if x)
        for col in pedidas:
            if col is None or str(col) in direccionables:
                continue
            parecidas = _parecidas(str(col), sorted(direccionables))
            diag.append(Diagnostico(
                codigo="columna_inexistente", nodo_id=nodo_id, param=campo,
                mensaje=f"«{spec.titulo}»: la columna «{col}» no existe en los datos que le llegan.",
                sugerencia=f"¿Quisiste decir «{parecidas[0]}»?" if parecidas else
                           f"Columnas disponibles: {', '.join(sorted(direccionables)[:12])}",
            ))


def _parecidas(objetivo: str, candidatas: list[str], n: int = 3) -> list[str]:
    import difflib

    return difflib.get_close_matches(objetivo, candidatas, n=n, cutoff=0.6)


# ---------------------------------------------------------------------------
# (4) Planear el DAG
# ---------------------------------------------------------------------------


def _detectar_ciclo(grafo: GrafoSpec) -> list[str] | None:
    """DFS con colores. Devuelve el ciclo completo, no un 'hay un ciclo'."""
    BLANCO, GRIS, NEGRO = 0, 1, 2
    color = {n.id: BLANCO for n in grafo.nodos}
    padre: dict[str, str | None] = {n.id: None for n in grafo.nodos}
    salida: dict[str, list[str]] = {n.id: [] for n in grafo.nodos}
    for a in grafo.aristas:
        if a.origen in salida and a.destino in salida:
            salida[a.origen].append(a.destino)

    def dfs(u: str) -> list[str] | None:
        color[u] = GRIS
        for v in salida[u]:
            if color[v] == GRIS:
                ciclo, actual = [v], u
                while actual is not None and actual != v:
                    ciclo.append(actual)
                    actual = padre[actual]
                ciclo.append(v)
                return list(reversed(ciclo))
            if color[v] == BLANCO:
                padre[v] = u
                if (c := dfs(v)) is not None:
                    return c
        color[u] = NEGRO
        return None

    for n in grafo.nodos:
        if color[n.id] == BLANCO and (c := dfs(n.id)) is not None:
            return c
    return None


def _orden_topologico(grafo: GrafoSpec, incluidos: set[str]) -> list[str]:
    """Kahn, con desempate por (profundidad, y, x).

    Un orden topologico cualquiera tambien seria correcto, pero produciria un
    script que el usuario no reconoce como suyo. Este hace que el codigo se lea
    de arriba hacia abajo igual que el lienzo.
    """
    entrantes = {n: 0 for n in incluidos}
    hijos: dict[str, list[str]] = {n: [] for n in incluidos}
    for a in grafo.aristas:
        if a.origen in incluidos and a.destino in incluidos:
            entrantes[a.destino] += 1
            hijos[a.origen].append(a.destino)

    pos = {n.id: n.posicion for n in grafo.nodos}
    profundidad = {n: 0 for n in incluidos}
    listos = sorted([n for n, g in entrantes.items() if g == 0],
                    key=lambda n: (pos[n].y, pos[n].x, n))
    orden: list[str] = []
    while listos:
        u = listos.pop(0)
        orden.append(u)
        for v in hijos[u]:
            profundidad[v] = max(profundidad[v], profundidad[u] + 1)
            entrantes[v] -= 1
            if entrantes[v] == 0:
                listos.append(v)
        listos.sort(key=lambda n: (profundidad[n], pos[n].y, pos[n].x, n))
    return orden


def _podar(
    grafo: GrafoSpec, especs: dict[str, type[EspecNodo]], objetivo: str | None
) -> tuple[set[str], list[str]]:
    """Se compila solo lo que alcanza un nodo terminal (o el objetivo pedido).

    Los sub-grafos huerfanos de experimentos abandonados no cuestan computo.
    """
    todos = set(especs)
    padres: dict[str, list[str]] = {n: [] for n in todos}
    for a in grafo.aristas:
        if a.origen in todos and a.destino in todos:
            padres[a.destino].append(a.origen)

    if objetivo is not None:
        semillas = {objetivo} if objetivo in todos else set()
    else:
        semillas = {n for n in todos if especs[n].terminal}
        if not semillas:
            return todos, []  # sin terminales, el usuario esta explorando: se compila todo

    vivos: set[str] = set()
    pila = list(semillas)
    while pila:
        u = pila.pop()
        if u in vivos:
            continue
        vivos.add(u)
        pila.extend(padres[u])
    return vivos, sorted(todos - vivos)


# ---------------------------------------------------------------------------
# (5) Bajar a IR
# ---------------------------------------------------------------------------


def _huella(
    op: str, version: str, params: BaseModel, huellas_padres: list[str], semilla: int
) -> str:
    crudo = json.dumps(
        {
            "op": op,
            "version": version,
            "params": params.model_dump(mode="json"),
            "padres": sorted(huellas_padres),
            "semilla": semilla,
        },
        sort_keys=True, ensure_ascii=False, default=str,
    )
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()[:32]


def compilar(grafo: GrafoSpec, objetivo: str | None = None) -> Programa:
    """Compila el grafo. Nunca lanza por errores del usuario: los devuelve.

    Que los errores del usuario vengan como datos y no como excepciones es lo
    que permite que la interfaz muestre *todos* los problemas del lienzo a la
    vez, en lugar de uno por intento.
    """
    diag: list[Diagnostico] = []
    programa = Programa(titulo=grafo.titulo, semilla=grafo.semilla, huella_grafo=grafo.huella())

    especs = _resolver(grafo, diag)
    conexiones = _verificar_aristas(grafo, especs, diag)

    if (ciclo := _detectar_ciclo(grafo)) is not None:
        diag.append(Diagnostico(
            codigo="ciclo", nodo_id=ciclo[0],
            mensaje="El analisis se muerde la cola: " + " → ".join(ciclo) +
                    ". Un analisis tiene que ir en una sola direccion.",
            sugerencia="Lo que parece iteracion (validacion cruzada, pronostico recursivo) va dentro de un nodo, no dibujado.",
        ))
        programa.diagnosticos = diag
        return programa

    vivos, podados = _podar(grafo, especs, objetivo)
    programa.podados = podados
    orden = _orden_topologico(grafo, vivos)
    programa.orden = orden

    nombrador = Nombrador()
    var_de: dict[tuple[str, str], str] = {}       # (nodo, puerto salida) -> variable
    esq_de: dict[tuple[str, str], Esquema] = {}   # (nodo, puerto salida) -> esquema
    huella_de: dict[str, str] = {}
    por_id = {n.id: n for n in grafo.nodos}

    for nodo_id in orden:
        nodo, spec = por_id[nodo_id], especs[nodo_id]
        params = _validar_params(nodo, spec, diag)
        if params is None:
            continue

        entradas: dict[str, str] = {}
        esquemas_entrada: dict[str, Esquema] = {}
        for puerto in spec.entradas:
            llegadas = conexiones[nodo_id].get(puerto.nombre, [])
            variables = [var_de[(o, p)] for (o, p) in llegadas if (o, p) in var_de]
            if not variables:
                continue
            entradas[puerto.nombre] = "\x00".join(variables) if puerto.multiple else variables[0]
            primero = llegadas[0]
            if primero in esq_de:
                esquemas_entrada[puerto.nombre] = esq_de[primero]

        _verificar_columnas(nodo_id, spec, params, esquemas_entrada, diag)

        etiqueta = nodo.etiqueta or spec.titulo
        salidas = {
            p.nombre: nombrador.nuevo(
                nodo.etiqueta or spec.prefijo_var,
                p.nombre if len(spec.salidas) > 1 else None,
            )
            for p in spec.salidas
        }

        padres = sorted({o for (o, _p) in sum(conexiones[nodo_id].values(), [])})
        huella = _huella(spec.op, spec.version, params,
                         [huella_de.get(p, p) for p in padres], grafo.semilla)
        huella_de[nodo_id] = huella

        try:
            salida_esq = spec().esquema_salida(esquemas_entrada, params)
        except Exception as exc:  # el nodo no supo deducir: no es fatal
            salida_esq = {}
            diag.append(Diagnostico(severidad="aviso", codigo="esquema_desconocido", nodo_id=nodo_id,
                                    mensaje=f"No se pudo anticipar el resultado de «{spec.titulo}»: {exc}"))
        for puerto, esquema in salida_esq.items():
            esq_de[(nodo_id, puerto)] = esquema
        for puerto, var in salidas.items():
            var_de[(nodo_id, puerto)] = var
        programa.esquemas[nodo_id] = salida_esq

        programa.instrucciones.append(Instruccion(
            nodo_id=nodo_id, op=spec.op, version=spec.version, etiqueta=etiqueta,
            entradas=entradas, salidas=salidas, params=params,
            esquemas_entrada=esquemas_entrada, huella=huella, notas=nodo.notas,
        ))

    programa.diagnosticos = diag
    return programa
