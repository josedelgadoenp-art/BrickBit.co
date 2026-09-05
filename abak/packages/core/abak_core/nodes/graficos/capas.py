"""Graficos por capas: un lienzo, y encima lo que quieras apilar.

La idea viene de ggplot2: un grafico no es un «tipo de grafico» de un menu, es
una pila. Declaras que columna va en cada eje y luego agregas puntos, o linea, o
las dos, mas una banda de confianza y una tendencia. Cada capa es un nodo, y el
lienzo se lee de arriba hacia abajo igual que el grafico.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ... import viz  # noqa: F401  (registra los ayudantes de la gramatica)
from ...graph.spec import Esquema
from ...registry.base import Ayuda, CampoColumna, EspecNodo, Puerto, registrar


class _Capa(EspecNodo):
    """Base de las capas: entra un grafico, sale el mismo grafico con una capa mas."""

    familia = "graficos"
    prefijo_var = "grafico"
    entradas = [Puerto(nombre="grafico", tipo="capa", titulo="Grafico")]
    salidas = [Puerto(nombre="grafico", tipo="capa", titulo="Grafico")]

    ayudante: str = ""

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {}


@registrar
class Lienzo(EspecNodo):
    op = "graficos.lienzo"
    familia = "graficos"
    titulo = "Lienzo (empezar un grafico)"
    prefijo_var = "grafico"
    ayuda = Ayuda(
        que_hace="Empieza un grafico: dice que columna va en el eje horizontal, cual en el vertical y "
                 "cual separa las series por color.",
        cuando_usarlo="Siempre es el primer nodo de un grafico. Encima se apilan las capas.",
        interpretacion="Por si solo no dibuja nada: hace falta al menos una capa (puntos, linea, barras).",
        advertencias=["Abak no permite dos ejes verticales, a proposito. Dos medidas de escalas distintas "
                      "van en dos graficos o indexadas a una base comun: con dos ejes se puede elegir la "
                      "conclusion moviendo las escalas."],
        equivalente={"r": "ggplot(datos, aes(x, y, color))", "spss": "Constructor de graficos"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="grafico", tipo="capa", titulo="Grafico")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        x: str = CampoColumna()
        y: str | None = CampoColumna(default=None)
        color: str | None = CampoColumna(default=None)
        tamano: str | None = CampoColumna(tipo="numerica", default=None)
        etiqueta: str | None = CampoColumna(default=None)

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("lienzo")
        ctx.nota(f"Eje horizontal: «{ctx.p('x')}»" +
                 (f", eje vertical: «{ctx.p('y')}»" if ctx.p("y") else "") +
                 (f", una serie por «{ctx.p('color')}»" if ctx.p("color") else "") + ".")
        ctx.emitir("SAL = lienzo(ENT, x=X, y=Y, color=COLOR, tamano=TAM, texto=TXT)",
                   SAL=ctx.salida("grafico"), ENT=ctx.entrada("datos"),
                   X=ctx.plit("x"), Y=ctx.plit("y"), COLOR=ctx.plit("color"),
                   TAM=ctx.plit("tamano"), TXT=ctx.plit("etiqueta"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {}


@registrar
class CapaPuntos(_Capa):
    op = "graficos.puntos"
    titulo = "+ Puntos (dispersion)"
    ayuda = Ayuda(
        que_hace="Dibuja un punto por observacion.",
        cuando_usarlo="Para ver la relacion entre dos variables numericas, y sobre todo para ver la "
                      "dispersion: cuanto se separan los casos de la relacion promedio.",
        interpretacion="La nube dice mas que la recta. Si los puntos se abren en abanico, hay "
                       "heterocedasticidad; si se agrupan en islas, puede haber submuestras distintas.",
        equivalente={"r": "+ geom_point()"},
    )

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        opacidad: float = Field(default=0.85, gt=0.05, le=1.0)
        tamano: int = Field(default=9, ge=4, le=30)

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("capa_puntos")
        ctx.emitir("SAL = capa_puntos(ENT, opacidad=OP, tamano=TAM)",
                   SAL=ctx.salida("grafico"), ENT=ctx.entrada("grafico"),
                   OP=ctx.plit("opacidad"), TAM=ctx.plit("tamano"))
        return ctx.fin()


@registrar
class CapaLinea(_Capa):
    op = "graficos.linea"
    titulo = "+ Linea"
    ayuda = Ayuda(
        que_hace="Une los puntos consecutivos con una linea continua, una serie por color.",
        cuando_usarlo="Para series de tiempo. La linea insinua continuidad entre observaciones, asi que "
                      "solo tiene sentido cuando el eje horizontal es un orden real (tiempo, rangos).",
        interpretacion="Fijate en el nivel y en la pendiente. Un salto de nivel suele ser un cambio "
                       "metodologico de la fuente, no un fenomeno economico.",
        advertencias=["Nunca uses linea sobre categorias sin orden: sugiere una transicion que no existe."],
        equivalente={"r": "+ geom_line()"},
    )

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        ancho: int = Field(default=2, ge=1, le=6)
        marcadores: bool = False
        es_estimado: bool = Field(default=False, description="Dibujar en ambar y punteado, por ser dato estimado")

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("capa_linea")
        if ctx.p("es_estimado"):
            ctx.nota("Serie marcada como estimada: se dibuja en ambar y punteada.")
        ctx.emitir("SAL = capa_linea(ENT, ancho=A, marcadores=M, estimado=EST)",
                   SAL=ctx.salida("grafico"), ENT=ctx.entrada("grafico"),
                   A=ctx.plit("ancho"), M=ctx.plit("marcadores"), EST=ctx.plit("es_estimado"))
        return ctx.fin()


@registrar
class CapaBarras(_Capa):
    op = "graficos.barras"
    titulo = "+ Barras"
    ayuda = Ayuda(
        que_hace="Dibuja una barra por categoria.",
        cuando_usarlo="Para comparar magnitudes entre categorias: produccion por sector, precio por entidad.",
        interpretacion="Ordena las barras por su valor, no alfabeticamente: el orden es informacion.",
        advertencias=["El eje de las barras SIEMPRE empieza en cero. Truncarlo exagera diferencias "
                      "chicas y es la forma mas comun de mentir con una grafica."],
        equivalente={"r": "+ geom_col()"},
    )

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        opacidad: float = Field(default=0.9, gt=0.1, le=1.0)

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("capa_barras")
        ctx.emitir("SAL = capa_barras(ENT, opacidad=OP)",
                   SAL=ctx.salida("grafico"), ENT=ctx.entrada("grafico"), OP=ctx.plit("opacidad"))
        return ctx.fin()


@registrar
class CapaBanda(_Capa):
    op = "graficos.banda"
    titulo = "+ Banda de confianza"
    ayuda = Ayuda(
        que_hace="Sombrea el area entre un limite inferior y uno superior.",
        cuando_usarlo="Para intervalos de confianza y de pronostico. Un pronostico sin banda es una "
                      "opinion disfrazada de numero.",
        interpretacion="Mientras mas ancha la banda, menos sabes. Si la banda de dos series se traslapa, "
                       "no puedes afirmar que una sea distinta de la otra.",
        equivalente={"r": "+ geom_ribbon()"},
    )

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        limite_bajo: str = CampoColumna(tipo="numerica")
        limite_alto: str = CampoColumna(tipo="numerica")
        opacidad: float = Field(default=0.20, gt=0.02, le=0.8)
        etiqueta: str = "Intervalo de confianza"

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("capa_banda")
        ctx.nota("La banda va en ambar y por debajo de la linea: marca lo estimado sin taparlo.")
        ctx.emitir("SAL = capa_banda(ENT, bajo=BAJO, alto=ALTO, opacidad=OP, etiqueta=ETI)",
                   SAL=ctx.salida("grafico"), ENT=ctx.entrada("grafico"),
                   BAJO=ctx.plit("limite_bajo"), ALTO=ctx.plit("limite_alto"),
                   OP=ctx.plit("opacidad"), ETI=ctx.plit("etiqueta"))
        return ctx.fin()


@registrar
class CapaTendencia(_Capa):
    op = "graficos.tendencia"
    titulo = "+ Linea de tendencia"
    ayuda = Ayuda(
        que_hace="Ajusta y dibuja una recta de minimos cuadrados sobre los puntos, con su intervalo.",
        cuando_usarlo="Para ver de un vistazo si hay relacion y de que signo.",
        interpretacion="Es la misma recta de un MCO simple. Si el intervalo es tan ancho que cabe una "
                       "recta horizontal, no hay evidencia de relacion.",
        advertencias=["La tendencia es una estimacion: se dibuja en ambar, no en el color de la serie."],
        equivalente={"r": "+ geom_smooth(method='lm')"},
    )

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        metodo: Literal["lm"] = "lm"
        intervalo: bool = True

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("capa_tendencia")
        ctx.emitir("SAL = capa_tendencia(ENT, metodo=MET, intervalo=IC)",
                   SAL=ctx.salida("grafico"), ENT=ctx.entrada("grafico"),
                   MET=ctx.plit("metodo"), IC=ctx.plit("intervalo"))
        return ctx.fin()


@registrar
class CapaReferencia(_Capa):
    op = "graficos.referencia"
    titulo = "+ Linea de referencia"
    ayuda = Ayuda(
        que_hace="Traza una linea horizontal o vertical en un valor que tu elijas.",
        cuando_usarlo="Para marcar el cero, una meta, el promedio nacional o la fecha de un cambio de regimen.",
        interpretacion="Da un punto de comparacion: sin el, el lector no sabe si un valor es alto o bajo.",
        equivalente={"r": "+ geom_hline()"},
    )

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        eje: Literal["y", "x"] = "y"
        valor: float = 0.0
        etiqueta: str | None = None

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("capa_referencia")
        ctx.emitir("SAL = capa_referencia(ENT, eje=EJE, valor=VAL, etiqueta=ETI)",
                   SAL=ctx.salida("grafico"), ENT=ctx.entrada("grafico"),
                   EJE=ctx.plit("eje"), VAL=ctx.plit("valor"), ETI=ctx.plit("etiqueta"))
        return ctx.fin()


@registrar
class Facetas(_Capa):
    op = "graficos.facetas"
    titulo = "+ Facetas (un panel por categoria)"
    ayuda = Ayuda(
        que_hace="Parte el grafico en varios paneles chicos, uno por categoria.",
        cuando_usarlo="Cuando tienes mas de cinco o seis series y el grafico se vuelve un plato de "
                      "espagueti. Casi siempre es mejor que meter mas colores.",
        interpretacion="Con el eje vertical compartido las magnitudes se comparan entre paneles; sin "
                       "compartirlo se ve mejor la forma de cada uno, pero ya no se comparan niveles.",
        equivalente={"r": "+ facet_wrap(~ grupo)"},
    )

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        por: str = CampoColumna()
        columnas: int = Field(default=3, ge=1, le=6)
        compartir_eje_y: bool = True

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("facetas")
        ctx.emitir("SAL = facetas(ENT, por=POR, columnas=COLS, compartir_y=COMP)",
                   SAL=ctx.salida("grafico"), ENT=ctx.entrada("grafico"),
                   POR=ctx.plit("por"), COLS=ctx.plit("columnas"), COMP=ctx.plit("compartir_eje_y"))
        return ctx.fin()


@registrar
class Escala(_Capa):
    op = "graficos.escala"
    titulo = "+ Escala de un eje"
    ayuda = Ayuda(
        que_hace="Cambia como se dibuja un eje: escala logaritmica, limites, formato de los numeros.",
        cuando_usarlo="La escala logaritmica es util cuando los valores abarcan varios ordenes de "
                      "magnitud, o cuando lo que importa son los cambios porcentuales.",
        interpretacion="En escala logaritmica, la misma distancia vertical significa el mismo cambio "
                       "porcentual, no el mismo cambio absoluto. Hay que decirlo en el pie del grafico.",
        advertencias=["Poner limites al eje puede exagerar o esconder diferencias. Si los cambias, dilo."],
        equivalente={"r": "+ scale_y_log10()"},
    )

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        eje: Literal["y", "x"] = "y"
        tipo: Literal["lineal", "log"] = "lineal"
        minimo: float | None = None
        maximo: float | None = None
        formato: str | None = None

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("escala")
        if ctx.p("tipo") == "log":
            ctx.nota("Escala logaritmica: la misma distancia significa el mismo cambio porcentual.")
        ctx.emitir("SAL = escala(ENT, eje=EJE, tipo=TIPO, minimo=MIN, maximo=MAX, formato=FMT)",
                   SAL=ctx.salida("grafico"), ENT=ctx.entrada("grafico"), EJE=ctx.plit("eje"),
                   TIPO=ctx.plit("tipo"), MIN=ctx.plit("minimo"), MAX=ctx.plit("maximo"),
                   FMT=ctx.plit("formato"))
        return ctx.fin()


@registrar
class Tema(_Capa):
    op = "graficos.tema"
    titulo = "+ Titulos y estilo"
    ayuda = Ayuda(
        que_hace="Pone titulo, nombres de los ejes, la nota al pie y elige modo claro u oscuro.",
        cuando_usarlo="Al final, antes de dibujar. Un grafico sin titulo ni unidades no se puede usar "
                      "fuera de la pantalla donde lo hiciste.",
        interpretacion="La nota al pie es donde va la fuente. Si el grafico sale de casa, la fuente no "
                       "es opcional.",
        equivalente={"r": "+ labs() + theme()"},
    )

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        titulo: str | None = None
        eje_x: str | None = None
        eje_y: str | None = None
        nota: str | None = Field(default=None, description="Pie del grafico: la fuente va aqui")
        modo: Literal["claro", "oscuro"] = "claro"
        leyenda: bool = True

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("tema")
        ctx.emitir("SAL = tema(ENT, titulo=T, eje_x=EX, eje_y=EY, modo=MODO, nota=NOTA, leyenda=LEY)",
                   SAL=ctx.salida("grafico"), ENT=ctx.entrada("grafico"), T=ctx.plit("titulo"),
                   EX=ctx.plit("eje_x"), EY=ctx.plit("eje_y"), MODO=ctx.plit("modo"),
                   NOTA=ctx.plit("nota"), LEY=ctx.plit("leyenda"))
        return ctx.fin()


@registrar
class Dibujar(EspecNodo):
    op = "graficos.dibujar"
    familia = "graficos"
    titulo = "Dibujar"
    prefijo_var = "figura"
    terminal = True
    cacheable = False
    ayuda = Ayuda(
        que_hace="Convierte la pila de capas en una grafica interactiva.",
        cuando_usarlo="Es el ultimo nodo de todo grafico.",
        interpretacion="La grafica es interactiva: pasa el cursor para ver los valores, y usa la leyenda "
                       "para prender y apagar series.",
        equivalente={"r": "print(p)"},
    )
    entradas = [Puerto(nombre="grafico", tipo="capa")]
    salidas = [Puerto(nombre="figura", tipo="figura")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("dibujar")
        ctx.emitir("SAL = dibujar(ENT)", SAL=ctx.salida("figura"), ENT=ctx.entrada("grafico"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {}

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        from ...runtime.artefactos import figura_a_json

        f = salidas.get("figura")
        if f is None:
            return {}
        return {"figura": figura_a_json(f, titulo="Grafica")}
