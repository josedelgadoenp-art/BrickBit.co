"""El registro de nodos: una sola fuente de verdad.

Agregar una herramienta nueva a Abak es escribir un archivo de Python. Nada
mas. No se toca el frontend, ni la API, ni el ejecutor, ni el generador de
codigo: los cuatro leen de aqui.

De cada `EspecNodo` salen, sin duplicacion:
  - la paleta del frontend           (familia, titulo, ayuda.que_hace)
  - el panel de inspector            (ayuda completa)
  - el formulario de parametros      (Params -> JSON Schema -> controles)
  - la verificacion de tipos         (entradas, salidas)
  - el codigo generado               (emit)
  - la invalidacion de cache         (version)
  - la documentacion                 (docs/nodos.md, autogenerado)
"""

from __future__ import annotations

import ast
from typing import Any, ClassVar, Iterable

from pydantic import BaseModel, ConfigDict, Field

from ..graph.spec import Esquema
from ..graph.tipos import COLOR, DESCRIPCION, JERARQUIA


# ---------------------------------------------------------------------------
# Familias: las pestanas de la paleta
# ---------------------------------------------------------------------------


class Familia(BaseModel):
    id: str
    titulo: str
    descripcion: str
    color: str
    orden: int
    icono: str = "cuadro"


FAMILIAS: dict[str, Familia] = {
    f.id: f
    for f in [
        Familia(id="datos", titulo="Datos", orden=10, color="#6fa287", icono="tabla",
                descripcion="Traer datos al analisis y prepararlos: archivos, ejemplos, uniones, filtros."),
        Familia(id="fuentes", titulo="Fuentes oficiales", orden=15, color="#55997e", icono="antena",
                descripcion="Series en vivo de INEGI y Banxico. Se guardan en cache: el analisis "
                            "reproduce los mismos numeros aunque la fuente revise la serie."),
        Familia(id="transformar", titulo="Transformar", orden=20, color="#55997e", icono="funcion",
                descripcion="Crear variables nuevas: logaritmos, tasas de crecimiento, rezagos, deflactar, estandarizar."),
        Familia(id="explorar", titulo="Explorar", orden=30, color="#9aac6b", icono="lupa",
                descripcion="Mirar los datos antes de modelarlos: descriptivos, correlaciones, tablas cruzadas, pruebas."),
        Familia(id="econometria", titulo="Econometria", orden=40, color="#c07a66", icono="regresion",
                descripcion="Regresiones y modelos de siempre: MCO, variables instrumentales, panel, eleccion discreta."),
        Familia(id="series", titulo="Series de tiempo", orden=50, color="#cf928b", icono="onda",
                descripcion="Todo lo que tiene fecha: raiz unitaria, ARIMA, VAR, impulso-respuesta, cointegracion, ciclos."),
        Familia(id="espacial", titulo="Econometria espacial", orden=60, color="#b7c489", icono="mapa",
                descripcion="Cuando la ubicacion importa: matrices de vecindad, Moran, LISA, SAR y SEM."),
        Familia(id="macro", titulo="Macro e insumo-producto", orden=70, color="#24664a", icono="matriz",
                descripcion="Estructura productiva: Leontief, multiplicadores, encadenamientos, impacto sectorial, keynesiano."),
        Familia(id="ml", titulo="Machine learning", orden=80, color="#8fa8bd", icono="arbol",
                descripcion="Prediccion con XGBoost y validacion honesta para series y panel."),
        Familia(id="graficos", titulo="Graficos", orden=90, color="#7f93a8", icono="grafica",
                descripcion="Gramatica por capas: un lienzo y encima puntos, lineas, bandas, tendencias y facetas."),
        Familia(id="salida", titulo="Resultados", orden=100, color="#a99b8c", icono="salida",
                descripcion="Lo que te llevas: tablas de publicacion, exportar a Excel o CSV, informe."),
    ]
}


# ---------------------------------------------------------------------------
# Ayuda: no es opcional
# ---------------------------------------------------------------------------


class Ayuda(BaseModel):
    """La explicacion en espanol llano de una herramienta.

    Un sistema que quiere ser mas facil que SPSS no puede tener herramientas sin
    explicar: la explicacion es el producto tanto como el calculo. Una prueba
    recorre el registro y falla si un nodo no trae `que_hace`, `cuando_usarlo` e
    `interpretacion`.
    """

    model_config = ConfigDict(extra="forbid")

    que_hace: str
    cuando_usarlo: str
    interpretacion: str
    supuestos: list[str] = Field(default_factory=list)
    advertencias: list[str] = Field(default_factory=list)
    referencia: str | None = None
    equivalente: dict[str, str] = Field(
        default_factory=dict,
        description="Como se llama esto en los sistemas que la gente ya conoce: {'stata': 'regress', 'r': 'lm()'}. Baja el costo de migrar.",
    )


# ---------------------------------------------------------------------------
# Puertos
# ---------------------------------------------------------------------------


class Puerto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str
    tipo: str
    requerido: bool = True
    multiple: bool = False
    titulo: str | None = None
    descripcion: str | None = None

    def model_post_init(self, _ctx: Any) -> None:
        if self.tipo not in JERARQUIA:
            raise ValueError(f"Tipo de puerto desconocido: {self.tipo!r}")

    @property
    def ayuda_tipo(self) -> str:
        return DESCRIPCION[self.tipo]


# ---------------------------------------------------------------------------
# Ayudantes: como el script exportado se mantiene autonomo
# ---------------------------------------------------------------------------


class Ayudante(BaseModel):
    """Una funcion de Python que el compilador pega en el preludio del script.

    Un nodo complejo no cabe razonablemente como AST en linea. La salida
    tentadora es que el script importe `abak_runtime`, y ahi deja de ser
    portable. En vez de eso, el compilador emite **solo los ayudantes que el
    grafo usa**, en orden de dependencia, y el `.py` resultante corre en
    cualquier maquina con pandas y statsmodels, sin Abak de por medio.
    """

    model_config = ConfigDict(extra="forbid")

    nombre: str
    fuente: str
    imports: list[tuple[str, str | None]] = Field(default_factory=list)
    depende_de: list[str] = Field(default_factory=list)

    def como_ast(self) -> list[ast.stmt]:
        """Las sentencias del ayudante, listas para pegarse en el preludio.

        Se admite mas de una sentencia porque hay ayudantes que necesitan sus
        constantes al lado (una paleta, una tabla de valores criticos). Lo que
        se exige es que el bloque DEFINA el nombre con el que se registro: asi
        `usar_ayudante("dibujar")` no puede acabar emitiendo otra cosa.
        """
        arbol = ast.parse(self.fuente.strip())
        definidos: set[str] = set()
        for nodo in arbol.body:
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                definidos.add(nodo.name)
            elif isinstance(nodo, ast.Assign):
                definidos.update(d.id for d in nodo.targets if isinstance(d, ast.Name))
            elif isinstance(nodo, ast.AnnAssign) and isinstance(nodo.target, ast.Name):
                definidos.add(nodo.target.id)
            else:
                raise ValueError(
                    f"El ayudante {self.nombre!r} solo admite definiciones y asignaciones "
                    f"en el nivel superior; trae un {type(nodo).__name__}"
                )
        if self.nombre not in definidos:
            raise ValueError(
                f"El ayudante {self.nombre!r} no define ese nombre; define {sorted(definidos)}"
            )
        return arbol.body


AYUDANTES: dict[str, Ayudante] = {}


def registrar_ayudante(ayudante: Ayudante) -> Ayudante:
    ayudante.como_ast()  # valida al importar, no en tiempo de ejecucion
    AYUDANTES[ayudante.nombre] = ayudante
    return ayudante


# ---------------------------------------------------------------------------
# Controles del formulario: pistas de interfaz sobre los parametros
# ---------------------------------------------------------------------------


def control(tipo: str, **extra: Any) -> dict[str, Any]:
    """Pista de interfaz que viaja dentro del JSON Schema del parametro.

    El frontend no sabe nada de econometria: lee `abak.control` y dibuja el
    control que toque. `columna`/`columnas` ademas se alimentan del esquema
    propagado, asi que el desplegable muestra las columnas que de verdad
    existen en ese punto del grafo, no las del archivo original.
    """
    return {"abak": {"control": tipo, **extra}}


def CampoColumna(puerto: str = "datos", tipo: str | None = None, **kw: Any) -> Any:
    return Field(json_schema_extra=control("columna", puerto=puerto, tipo_columna=tipo), **kw)


def CampoColumnas(puerto: str = "datos", tipo: str | None = None, **kw: Any) -> Any:
    return Field(json_schema_extra=control("columnas", puerto=puerto, tipo_columna=tipo), **kw)


# ---------------------------------------------------------------------------
# EspecNodo
# ---------------------------------------------------------------------------


class SinParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EspecNodo:
    """Clase base de toda herramienta de Abak.

    Las subclases declaran metadatos como atributos de clase y sobreescriben
    `emit`. `esquema_salida` y `resumir` tienen comportamiento por omision
    razonable.
    """

    op: ClassVar[str]
    version: ClassVar[str] = "1.0.0"
    familia: ClassVar[str]
    titulo: ClassVar[str]
    ayuda: ClassVar[Ayuda]
    entradas: ClassVar[list[Puerto]] = []
    salidas: ClassVar[list[Puerto]] = []
    Params: ClassVar[type[BaseModel]] = SinParams
    #: prefijo del nombre de variable en el codigo generado, si el usuario no puso etiqueta
    prefijo_var: ClassVar[str] = "resultado"
    #: nodos terminales: los que justifican por si solos ejecutar el grafo
    terminal: ClassVar[bool] = False
    #: objetos que no se pueden serializar y por lo tanto no se cachean
    cacheable: ClassVar[bool] = True
    #: el nodo lee archivos: el preludio define RUTA_DATOS y la exportacion arma un .zip
    necesita_datos: ClassVar[bool] = False

    def columnas_requeridas(self, params: BaseModel) -> set[str] | None:
        """Qué columnas usa este nodo. `None` significa «cualquiera».

        Sirve para leer del archivo SÓLO lo que el análisis necesita. En un CSV
        de 200 columnas del que se usan 6, eso es 30 veces menos memoria, y sale
        gratis: la información ya está en los parámetros.

        Devolver `None` desactiva la poda para todo el grafo aguas arriba. Es lo
        correcto para un nodo que puede tocar columnas que no nombró —por
        ejemplo, «Descriptivos» sin lista, que resume todas las numéricas—:
        podar ahí cambiaría el resultado en silencio, y eso es peor que gastar
        memoria.
        """
        pedidas: set[str] = set()
        for campo, esquema in self.esquema_params().get("properties", {}).items():
            control = (esquema.get("abak") or {}).get("control")
            if control not in ("columna", "columnas"):
                continue
            valor = getattr(params, campo, None)
            if control == "columna":
                if valor:
                    pedidas.add(str(valor))
            else:
                pedidas.update(str(c) for c in (valor or []))
        return pedidas

    def archivos(self, params: BaseModel) -> dict[str, str]:
        """{ruta dentro del zip: ruta real en disco}.

        Es lo que permite que "exportar" entregue un .zip con el script y sus
        datos al lado, y que el script corra tal cual al descomprimirlo. Sin
        esto, un `.py` que lee un CSV que no existe no es reproducible.
        """
        return {}

    # -- lo que implementa cada nodo -----------------------------------------

    def emit(self, ctx: Any) -> Any:  # -> BloqueCodigo
        raise NotImplementedError(f"{type(self).__name__} no implementa emit()")

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        """Que esquema tiene cada puerto de salida. Por omision: pasa el primero de entrada."""
        base = next(iter(entradas.values()), Esquema())
        return {p.nombre: base for p in self.salidas if p.tipo in ("tabla", "serie", "panel", "geotabla")}

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        """Convierte los objetos de salida en artefactos JSON para la interfaz.

        Corre FUERA del programa generado: es presentacion pura y por lo tanto
        no puede alterar el analisis ni causar divergencia entre lo que se
        ejecuta y lo que se exporta.
        """
        from ..runtime.artefactos import resumen_generico

        return resumen_generico(salidas)

    # -- utilidades -----------------------------------------------------------

    @classmethod
    def puerto_entrada(cls, nombre: str) -> Puerto | None:
        return next((p for p in cls.entradas if p.nombre == nombre), None)

    @classmethod
    def puerto_salida(cls, nombre: str) -> Puerto | None:
        return next((p for p in cls.salidas if p.nombre == nombre), None)

    @classmethod
    def esquema_params(cls) -> dict[str, Any]:
        return cls.Params.model_json_schema()

    @classmethod
    def descriptor(cls) -> dict[str, Any]:
        """Lo que consume el frontend para construir paleta, formulario e inspector."""
        return {
            "op": cls.op,
            "version": cls.version,
            "familia": cls.familia,
            "titulo": cls.titulo,
            "terminal": cls.terminal,
            "ayuda": cls.ayuda.model_dump(),
            "entradas": [
                {**p.model_dump(), "ayuda_tipo": p.ayuda_tipo} for p in cls.entradas
            ],
            "salidas": [
                {**p.model_dump(), "ayuda_tipo": p.ayuda_tipo} for p in cls.salidas
            ],
            "params_schema": cls.esquema_params(),
        }


REGISTRO: dict[str, type[EspecNodo]] = {}


class ErrorRegistro(Exception):
    pass


def registrar(cls: type[EspecNodo]) -> type[EspecNodo]:
    """Decorador que da de alta un nodo. Valida los invariantes al importar."""
    faltan = [a for a in ("op", "familia", "titulo", "ayuda") if not getattr(cls, a, None)]
    if faltan:
        raise ErrorRegistro(f"{cls.__name__} no declara: {', '.join(faltan)}")
    if cls.op in REGISTRO:
        raise ErrorRegistro(f"El op {cls.op!r} ya esta registrado por {REGISTRO[cls.op].__name__}")
    if cls.familia not in FAMILIAS:
        raise ErrorRegistro(f"{cls.op}: familia desconocida {cls.familia!r}")
    if not cls.op.startswith(f"{cls.familia}."):
        raise ErrorRegistro(f"{cls.op}: el op debe empezar con '{cls.familia}.'")
    nombres_e = [p.nombre for p in cls.entradas]
    nombres_s = [p.nombre for p in cls.salidas]
    if len(set(nombres_e)) != len(nombres_e) or len(set(nombres_s)) != len(nombres_s):
        raise ErrorRegistro(f"{cls.op}: hay puertos con nombre repetido")
    REGISTRO[cls.op] = cls
    return cls


def obtener(op: str) -> type[EspecNodo]:
    try:
        return REGISTRO[op]
    except KeyError:
        raise ErrorRegistro(
            f"No existe la herramienta {op!r}. Puede que el analisis se haya guardado "
            f"con una version mas nueva de Abak."
        ) from None


def catalogo() -> dict[str, Any]:
    """El registro completo, listo para servirse en GET /api/v1/registro."""
    familias = sorted(FAMILIAS.values(), key=lambda f: f.orden)
    nodos = [cls.descriptor() for cls in REGISTRO.values()]
    nodos.sort(key=lambda d: (FAMILIAS[d["familia"]].orden, d["titulo"]))
    return {
        "familias": [f.model_dump() for f in familias],
        "nodos": nodos,
        "tipos": {
            t: {"descripcion": DESCRIPCION[t], "padre": JERARQUIA[t], "color": COLOR[t]}
            for t in JERARQUIA
        },
    }


def todos(familia: str | None = None) -> Iterable[type[EspecNodo]]:
    for cls in REGISTRO.values():
        if familia is None or cls.familia == familia:
            yield cls
