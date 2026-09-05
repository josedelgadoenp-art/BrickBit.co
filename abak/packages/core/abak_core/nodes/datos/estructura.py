"""Declarar la estructura de los datos: serie de tiempo, panel, ubicacion.

Estos tres nodos son las unicas «promociones» del sistema de tipos: convierten
una `tabla` cualquiera en una `serie`, un `panel` o una `geotabla`. Existen
porque la diferencia entre un VAR con indice temporal y un VAR sobre filas en
desorden es un error que en otros sistemas se comete callado.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...graph.spec import Esquema
from ...registry.base import (Ayuda, Ayudante, CampoColumna, CampoColumnas, EspecNodo,
                              Puerto, registrar, registrar_ayudante)

registrar_ayudante(Ayudante(
    nombre="reindexar_por_frecuencia",
    fuente='''
def reindexar_por_frecuencia(datos, frecuencia):
    """Reindexa a una frecuencia regular, y avisa fuerte si eso vacia la serie.

    Reindexar a una frecuencia que no cuadra con las fechas —fin de trimestre
    contra inicio de trimestre, por ejemplo— produce una tabla del tamano
    correcto y COMPLETAMENTE vacia. Ese es el peor error posible: no truena, y
    los modelos de mas adelante fallan con mensajes que no apuntan aqui.
    """
    reindexado = datos.asfreq(frecuencia)
    utiles = int(reindexado.notna().any(axis=1).sum())
    if len(datos) and utiles < max(1, len(datos) // 2):
        raise ValueError(
            f"Al fijar la frecuencia '{frecuencia}' solo quedaron {utiles} periodos con datos "
            f"de los {len(datos)} originales. Casi siempre significa que la frecuencia elegida no "
            f"corresponde a las fechas: revisa si tus fechas caen al INICIO o al FINAL del periodo "
            f"(por ejemplo 'QS' es inicio de trimestre y 'QE' es fin de trimestre)."
        )
    return reindexado
''',
))

FRECUENCIAS = {"D": "diaria", "W": "semanal", "MS": "mensual (inicio de mes)",
               "ME": "mensual (fin de mes)", "QS": "trimestral (inicio)",
               "QE": "trimestral (fin)", "YS": "anual (inicio)", "YE": "anual (fin)"}


@registrar
class DefinirSerie(EspecNodo):
    op = "datos.serie_temporal"
    familia = "datos"
    titulo = "Definir serie temporal"
    prefijo_var = "serie"
    ayuda = Ayuda(
        que_hace="Le dice a Abak cual columna es la fecha y cada cuanto estan medidos los datos.",
        cuando_usarlo="Antes de cualquier herramienta de series de tiempo: ADF, ARIMA, VAR, filtros de ciclo.",
        interpretacion="Despues de este paso la tabla queda ordenada por fecha y con la frecuencia declarada. "
                       "Si aparecen filas nuevas con huecos, es que tu serie tenia periodos faltantes: "
                       "es mejor enterarse aqui que dentro de un modelo.",
        supuestos=["Los periodos deben estar espaciados de forma regular; si no, los rezagos no significan lo mismo en cada punto."],
        advertencias=["Sin frecuencia declarada, statsmodels adivina, y cuando adivina mal el pronostico sale con fechas equivocadas."],
        equivalente={"stata": "tsset fecha, quarterly", "r": "ts()", "eviews": "Structure/Resize"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="datos", tipo="serie", titulo="Serie")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        columna_fecha: str = CampoColumna()
        frecuencia: Literal["D", "W", "MS", "ME", "QS", "QE", "YS", "YE"] = "QS"
        rellenar_huecos: bool = True

    def emit(self, ctx: Any) -> Any:
        ctx.importar("pandas", "pd")
        ent, sal = ctx.entrada("datos"), ctx.salida("datos")
        fecha, frec = ctx.p("columna_fecha"), ctx.p("frecuencia")
        ctx.nota(f"La columna «{fecha}» pasa a ser el indice, con frecuencia {FRECUENCIAS[frec]}.")
        ctx.emitir("SAL = ENT.copy()", SAL=sal, ENT=ent)
        ctx.emitir("SAL[COL] = pd.to_datetime(SAL[COL])", SAL=ctx.ref_salida("datos"), COL=ctx.lit(fecha))
        ctx.emitir("SAL = SAL.sort_values(COL).set_index(COL)",
                   SAL=ctx.salida("datos"), COL=ctx.lit(fecha))
        if ctx.p("rellenar_huecos"):
            ctx.usar_ayudante("reindexar_por_frecuencia")
            ctx.emitir("SAL = reindexar_por_frecuencia(SAL, FREC)",
                       SAL=ctx.salida("datos"), FREC=ctx.lit(frec))
            ctx.nota("Los periodos que falten aparecen como filas vacias en vez de desaparecer sin aviso.")
        else:
            ctx.emitir("SAL.index.freq = FREC", SAL=ctx.ref_salida("datos"), FREC=ctx.lit(frec))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        base = entradas.get("datos", Esquema())
        fecha = params.columna_fecha  # type: ignore[attr-defined]
        return {"datos": base.con(quitar=[fecha], indice_temporal=fecha)}


@registrar
class DefinirPanel(EspecNodo):
    op = "datos.panel"
    familia = "datos"
    titulo = "Definir panel"
    prefijo_var = "panel"
    ayuda = Ayuda(
        que_hace="Declara cual columna identifica a la entidad (estado, empresa, hogar) y cual al periodo.",
        cuando_usarlo="Antes de estimar efectos fijos o aleatorios.",
        interpretacion="El resultado tiene un indice de dos niveles: entidad y tiempo. Es lo que permite "
                       "que un modelo distinga la variacion entre entidades de la variacion dentro de cada una.",
        supuestos=["La pareja (entidad, periodo) debe ser unica: no puede haber dos filas del mismo estado en el mismo anio."],
        equivalente={"stata": "xtset entidad anio", "r": "plm::pdata.frame()"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="datos", tipo="panel", titulo="Panel")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        entidad: str = CampoColumna()
        periodo: str = CampoColumna()

    def emit(self, ctx: Any) -> Any:
        ctx.importar("pandas", "pd")
        ent, sal = ctx.entrada("datos"), ctx.salida("datos")
        e, t = ctx.p("entidad"), ctx.p("periodo")
        ctx.nota(f"Panel: cada fila es «{e}» observado en «{t}».")
        ctx.emitir("SAL = ENT.set_index([E, T]).sort_index()",
                   SAL=sal, ENT=ent, E=ctx.lit(e), T=ctx.lit(t))
        ctx.emitir("assert SAL.index.is_unique, 'Hay filas repetidas para la misma entidad y periodo'",
                   SAL=ctx.ref_salida("datos"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        base = entradas.get("datos", Esquema())
        e, t = params.entidad, params.periodo  # type: ignore[attr-defined]
        return {"datos": base.con(quitar=[e, t], id_entidad=e, indice_temporal=t)}


@registrar
class DefinirUbicacion(EspecNodo):
    op = "datos.ubicacion"
    familia = "datos"
    titulo = "Definir ubicacion"
    prefijo_var = "geo"
    ayuda = Ayuda(
        que_hace="Declara que columnas traen la latitud y la longitud de cada fila.",
        cuando_usarlo="Antes de construir una matriz de pesos espaciales o de dibujar un mapa.",
        interpretacion="No cambia los datos: marca la tabla como geografica para que las herramientas "
                       "espaciales la acepten.",
        advertencias=["En Mexico la longitud es NEGATIVA (alrededor de -99). Si te salen puntos en China, "
                       "estan invertidas la latitud y la longitud."],
        equivalente={"stata": "spset", "r": "sf::st_as_sf()"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="datos", tipo="geotabla", titulo="Tabla con ubicacion")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        latitud: str = CampoColumna(default="lat")
        longitud: str = CampoColumna(default="lng")
        etiqueta: str | None = CampoColumna(default=None)

    def emit(self, ctx: Any) -> Any:
        lat, lng = ctx.p("latitud"), ctx.p("longitud")
        ctx.nota(f"Ubicacion: latitud en «{lat}», longitud en «{lng}».")
        ctx.emitir("SAL = ENT.dropna(subset=[LAT, LNG]).copy()",
                   SAL=ctx.salida("datos"), ENT=ctx.entrada("datos"),
                   LAT=ctx.lit(lat), LNG=ctx.lit(lng))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"datos": entradas.get("datos", Esquema())}


@registrar
class Remodelar(EspecNodo):
    op = "datos.remodelar"
    familia = "datos"
    titulo = "Cambiar de ancho a largo (o al reves)"
    prefijo_var = "remodelado"
    ayuda = Ayuda(
        que_hace="Reacomoda la tabla: de una columna por anio a una fila por anio, o al contrario.",
        cuando_usarlo="Casi todas las herramientas estadisticas piden formato largo (una fila por "
                      "observacion). Las hojas de calculo casi siempre vienen en ancho.",
        interpretacion="El numero total de datos no cambia; cambia como estan acomodados.",
        equivalente={"stata": "reshape long", "r": "tidyr::pivot_longer()"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="datos", tipo="tabla")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        direccion: Literal["a_largo", "a_ancho"] = "a_largo"
        identificadores: list[str] = CampoColumnas(default_factory=list)
        columnas: list[str] = CampoColumnas(default_factory=list)
        nombre_variable: str = Field(default="variable")
        nombre_valor: str = Field(default="valor")

    def emit(self, ctx: Any) -> Any:
        ent, sal = ctx.entrada("datos"), ctx.salida("datos")
        if ctx.p("direccion") == "a_largo":
            ctx.nota("Formato largo: una fila por observacion.")
            if ctx.p("columnas"):
                ctx.emitir("SAL = ENT.melt(id_vars=IDS, value_vars=COLS, var_name=VAR, value_name=VAL)",
                           SAL=sal, ENT=ent, IDS=ctx.plit("identificadores"), COLS=ctx.plit("columnas"),
                           VAR=ctx.plit("nombre_variable"), VAL=ctx.plit("nombre_valor"))
            else:
                ctx.emitir("SAL = ENT.melt(id_vars=IDS, var_name=VAR, value_name=VAL)",
                           SAL=sal, ENT=ent, IDS=ctx.plit("identificadores"),
                           VAR=ctx.plit("nombre_variable"), VAL=ctx.plit("nombre_valor"))
        else:
            ctx.nota("Formato ancho: una columna por categoria.")
            ctx.emitir("SAL = ENT.pivot_table(index=IDS, columns=VAR, values=VAL, observed=True).reset_index()",
                       SAL=sal, ENT=ent, IDS=ctx.plit("identificadores"),
                       VAR=ctx.plit("nombre_variable"), VAL=ctx.plit("nombre_valor"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"datos": Esquema()}  # cambia demasiado para anticiparlo con honestidad
