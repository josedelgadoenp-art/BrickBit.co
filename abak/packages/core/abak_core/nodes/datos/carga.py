"""Traer datos al analisis."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...graph.spec import Columna, Esquema
from ...registry.base import Ayuda, CampoColumnas, EspecNodo, Puerto, registrar

DIR_EJEMPLOS = Path(__file__).resolve().parents[2] / "data" / "ejemplos"

EJEMPLOS: dict[str, dict[str, Any]] = {
    "mexico_estados": {
        "titulo": "Entidades de Mexico (corte transversal)",
        "descripcion": "Las 32 entidades con precio por m², plusvalia, coordenadas y variables socioeconomicas. Sirve para regresion, mapas y econometria espacial.",
        "archivo": "mexico_estados.csv",
        "estimadas": ["precio_m2", "yield_pct", "dias_en_mercado", "ingreso_hogar_mensual",
                      "escolaridad_anios", "densidad_hab_km2", "poblacion_miles",
                      "empleo_formal_pct", "credito_hipotecario_pc"],
    },
    "mexico_macro": {
        "titulo": "Macro trimestral de Mexico (2005-2025)",
        "descripcion": "84 trimestres con PIB, inflacion, tasa objetivo, tipo de cambio y desempleo. Sirve para ARIMA, VAR y cointegracion.",
        "archivo": "mexico_macro_trimestral.csv",
        "fechas": ["fecha"],
        "estimadas": ["pib_indice", "inflacion_anual", "tasa_objetivo", "tipo_cambio",
                      "desempleo", "consumo_indice", "inversion_indice"],
    },
    "panel_estados": {
        "titulo": "Panel de entidades (2010-2024)",
        "descripcion": "32 entidades por 15 anios con PIB per capita, inversion y credito. Sirve para efectos fijos y aleatorios.",
        "archivo": "panel_estados_anual.csv",
        "estimadas": ["pib_per_capita", "inversion_pc", "credito_pc", "empleo_formal_pct", "salario_real"],
    },
    "insumo_producto": {
        "titulo": "Matriz insumo-producto (12 sectores)",
        "descripcion": "Transacciones intersectoriales, demanda final, produccion y empleo. Sirve para Leontief y multiplicadores.",
        "archivo": "mexico_insumo_producto.csv",
        "estimadas": [],
    },
    "hogares": {
        "titulo": "Hogares y credito hipotecario",
        "descripcion": "2,400 hogares con ingreso, escolaridad y si tienen credito. Sirve para logit, probit y machine learning.",
        "archivo": "hogares_vivienda.csv",
        "estimadas": [],
    },
}


def _esquema_de_csv(ruta: Path, fechas: list[str] | None = None,
                    estimadas: list[str] | None = None, fuente: str | None = None) -> Esquema:
    """Lee solo el encabezado y unas filas: barato, y llena los desplegables ya.

    Es la razon por la que se puede elegir la variable dependiente sin haber
    ejecutado nada.
    """
    import pandas as pd

    try:
        muestra = pd.read_csv(ruta, nrows=200)
    except Exception:
        return Esquema()
    esquema = Esquema.de_dataframe(muestra, fuente=fuente)
    marcadas = set(estimadas or [])
    for col in esquema.columnas:
        if col.nombre in (fechas or []):
            col.tipo = "fecha"
        if col.nombre in marcadas:
            col.es_estimado = True
            col.nota = "Dato estimado o simulado: no es una medicion."
    esquema.n_filas = None
    return esquema


@registrar
class DatosEjemplo(EspecNodo):
    op = "datos.ejemplo"
    familia = "datos"
    titulo = "Datos de ejemplo"
    prefijo_var = "datos"
    necesita_datos = True
    usa_proyeccion = True
    ayuda = Ayuda(
        que_hace="Carga uno de los conjuntos que trae Abak para aprender y probar.",
        cuando_usarlo="Cuando quieras entender como funciona una herramienta antes de usarla con tus propios datos.",
        interpretacion="El resultado es una tabla lista para conectar a cualquier otra herramienta.",
        advertencias=["Estos datos son para practicar. Las columnas marcadas en ambar son "
                      "estimaciones o simulaciones: no sirven para sustentar una decision ni para citarse."],
        equivalente={"stata": "sysuse auto", "r": "data(mtcars)"},
    )
    salidas = [Puerto(nombre="datos", tipo="tabla", titulo="Tabla")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        conjunto: Literal["mexico_estados", "mexico_macro", "panel_estados",
                          "insumo_producto", "hogares"] = Field(
            default="mexico_estados",
            json_schema_extra={"abak": {"control": "opcion", "etiquetas": {
                k: v["titulo"] for k, v in EJEMPLOS.items()}}},
        )

    def archivos(self, params: BaseModel) -> dict[str, str]:
        info = EJEMPLOS[params.conjunto]  # type: ignore[attr-defined]
        return {f"datos/{info['archivo']}": str(DIR_EJEMPLOS / info["archivo"])}

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        info = EJEMPLOS[params.conjunto]  # type: ignore[attr-defined]
        return {"datos": _esquema_de_csv(
            DIR_EJEMPLOS / info["archivo"], info.get("fechas"), info.get("estimadas"),
            fuente=f"Ejemplo Abak: {info['titulo']}")}

    def emit(self, ctx: Any) -> Any:
        info = EJEMPLOS[ctx.p("conjunto")]
        ctx.importar("pandas", "pd")
        ctx.nota(f"{info['titulo']}. {info['descripcion']}")
        usadas = ctx.columnas_a_leer(
            _esquema_de_csv(DIR_EJEMPLOS / info["archivo"], info.get("fechas")).nombres())
        if info.get("estimadas"):
            ctx.nota("Columnas estimadas o simuladas (no son mediciones): "
                     + ", ".join(info["estimadas"]) + ".")
        if usadas:
            ctx.nota(f"Se leen {len(usadas)} columnas: son las unicas que este analisis usa.")
        fechas = [f for f in (info.get("fechas") or []) if not usadas or f in usadas]
        argumentos = []
        huecos = {"SAL": ctx.salida("datos"), "ARCH": ctx.lit(info["archivo"])}
        if usadas:
            argumentos.append("usecols=COLS")
            huecos["COLS"] = ctx.lit(usadas)
        if fechas:
            argumentos.append("parse_dates=FECHAS")
            huecos["FECHAS"] = ctx.lit(fechas)
        cola = (", " + ", ".join(argumentos)) if argumentos else ""
        ctx.emitir(f"SAL = pd.read_csv(RUTA_DATOS / ARCH{cola})", **huecos)
        return ctx.fin()

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        from ...runtime.artefactos import tabla_a_json

        info = EJEMPLOS[params.conjunto]  # type: ignore[attr-defined]
        df = salidas.get("datos")
        if df is None:
            return {}
        return {"datos": tabla_a_json(df, titulo=info["titulo"], estimadas=info.get("estimadas"))}


def tipo_de_arrow(tipo: str) -> str:
    """Tipo de Arrow -> el vocabulario de tipos de Abak."""
    t = str(tipo).lower()
    if t.startswith(("timestamp", "date")):
        return "fecha"
    if t.startswith("bool"):
        return "booleana"
    if t.startswith(("int", "uint", "float", "double", "decimal")):
        return "numerica"
    if t.startswith("dictionary"):
        return "categorica"
    return "texto"


class ColumnaArchivo(BaseModel):
    """Una columna del archivo subido, tal como quedó al convertirlo."""

    model_config = ConfigDict(extra="ignore")
    nombre: str
    tipo_arrow: str = "string"
    faltantes: int = 0


@registrar
class CargarCSV(EspecNodo):
    op = "datos.csv"
    familia = "datos"
    titulo = "Cargar archivo (CSV o Excel)"
    prefijo_var = "datos"
    necesita_datos = True
    usa_proyeccion = True
    ayuda = Ayuda(
        que_hace="Lee un archivo que subiste y lo convierte en una tabla. Al subirlo se guarda en "
                 "formato columnar, que es lo que permite trabajar con archivos de millones de filas.",
        cuando_usarlo="Es casi siempre el primer paso de un analisis propio.",
        interpretacion="Revisa en la pestana Datos que las columnas se hayan leido con el tipo "
                       "correcto y cuantos faltantes trae cada una. Una columna numerica leida como "
                       "texto es la causa mas comun de errores mas adelante.",
        supuestos=["Los tipos se deducen de una muestra grande del archivo y luego se aplican a todo. "
                   "Es a proposito: dejar que se deduzcan trozo por trozo produce columnas de tipo "
                   "mixto que fallan raro y sin avisar."],
        advertencias=["Si los numeros traen coma decimal, indicalo al subir el archivo o se leeran "
                      "como texto.",
                      "Abak lee del archivo SOLO las columnas que tu analisis usa. Si agregas un "
                      "bloque que necesita otra columna, se lee tambien: no hay que volver a subir nada."],
        equivalente={"stata": "import delimited", "r": "arrow::read_parquet()", "spss": "Abrir datos"},
    )
    salidas = [Puerto(nombre="datos", tipo="tabla", titulo="Tabla")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        archivo_id: str = Field(json_schema_extra={"abak": {"control": "archivo"}})
        nombre: str = "datos.csv"
        #: Esquema que devolvio la subida. Viaja en el grafo para que los
        #: desplegables de aguas abajo funcionen sin haber ejecutado nada.
        columnas: list["ColumnaArchivo"] = Field(default_factory=list)
        n_filas: int = 0
        tope_filas: int | None = Field(
            default=None, ge=1,
            description="Leer solo las primeras N filas. Cambia los resultados: dilo si lo usas.")

    def _ruta(self, params: BaseModel) -> str:
        return f"{params.archivo_id}.parquet"  # type: ignore[attr-defined]

    def archivos(self, params: BaseModel) -> dict[str, str]:
        from ...runtime.almacen import ALMACEN

        nombre = self._ruta(params)
        return {f"datos/{nombre}": str(ALMACEN.dir_subidas() / nombre)}

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        cols = [Columna(nombre=c.nombre, tipo=tipo_de_arrow(c.tipo_arrow),  # type: ignore[attr-defined]
                        fuente=params.nombre,                                # type: ignore[attr-defined]
                        nota=(f"{c.faltantes:,} valores faltantes" if c.faltantes else None))
                for c in params.columnas]                                    # type: ignore[attr-defined]
        return {"datos": Esquema(columnas=cols,
                                 n_filas=params.n_filas or None)}            # type: ignore[attr-defined]

    def emit(self, ctx: Any) -> Any:
        ctx.importar("pandas", "pd")
        nombre_visible = ctx.p("nombre")
        disponibles = [c.nombre for c in ctx.p("columnas")]
        usadas = ctx.columnas_a_leer(disponibles)

        ctx.nota(f"Archivo del usuario: {nombre_visible}"
                 + (f" ({ctx.p('n_filas'):,} filas)" if ctx.p("n_filas") else "")
                 + ". Se guardo en formato columnar al subirlo.")
        if usadas:
            ctx.nota(f"De las {len(disponibles)} columnas del archivo se leen {len(usadas)}: "
                     f"son las unicas que este analisis usa. Leer las demas solo gastaria memoria.")
            ctx.emitir("SAL = pd.read_parquet(RUTA_DATOS / ARCH, columns=COLS)",
                       SAL=ctx.salida("datos"), ARCH=ctx.lit(self._ruta(ctx.params)),
                       COLS=ctx.lit(usadas))
        else:
            ctx.emitir("SAL = pd.read_parquet(RUTA_DATOS / ARCH)",
                       SAL=ctx.salida("datos"), ARCH=ctx.lit(self._ruta(ctx.params)))

        if ctx.p("tope_filas"):
            ctx.nota(f"ATENCION: solo se leen las primeras {ctx.p('tope_filas'):,} filas. "
                     "Los resultados NO son los de la tabla completa.")
            ctx.emitir("SAL = SAL.head(TOPE)", SAL=ctx.salida("datos"), TOPE=ctx.plit("tope_filas"))
        return ctx.fin()


@registrar
class TratarFaltantes(EspecNodo):
    op = "datos.faltantes"
    familia = "datos"
    titulo = "Tratar datos faltantes"
    prefijo_var = "datos"
    ayuda = Ayuda(
        que_hace="Decide que hacer con los huecos: quitarlos o rellenarlos.",
        cuando_usarlo="Cuando un modelo se queja de valores faltantes, o antes de estimar cualquier cosa.",
        interpretacion="Fijate en cuantas filas perdiste. Si perdiste muchas, el problema no es tecnico: "
                       "puede que el modelo este descansando en una submuestra que no representa al total.",
        advertencias=["Rellenar con la media reduce la varianza artificialmente y aprieta los errores estandar. "
                      "Es comodo, no es inocuo."],
        supuestos=["Quitar filas solo es inofensivo si los datos faltan al azar (MCAR)."],
        equivalente={"stata": "drop if missing()", "r": "na.omit()"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="datos", tipo="tabla"), Puerto(nombre="reporte", tipo="tabla", titulo="Que se perdio")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        metodo: Literal["quitar_filas", "media", "mediana", "cero", "anterior", "interpolar"] = "quitar_filas"
        columnas: list[str] = CampoColumnas(default_factory=list)

    #: (con columnas elegidas, sin columnas elegidas) por metodo
    def columnas_requeridas(self, params: BaseModel) -> set[str] | None:
        # Sin lista, trata TODAS las columnas.
        if not params.columnas:  # type: ignore[attr-defined]
            return None
        return super().columnas_requeridas(params)

    PLANTILLAS = {
        "quitar_filas": ("SAL = ENT.dropna(subset=COLS)", "SAL = ENT.dropna()"),
        "media": ("SAL[COLS] = ENT[COLS].fillna(ENT[COLS].mean())", "SAL = ENT.fillna(ENT.mean(numeric_only=True))"),
        "mediana": ("SAL[COLS] = ENT[COLS].fillna(ENT[COLS].median())", "SAL = ENT.fillna(ENT.median(numeric_only=True))"),
        "cero": ("SAL[COLS] = ENT[COLS].fillna(0)", "SAL = ENT.fillna(0)"),
        "anterior": ("SAL[COLS] = ENT[COLS].ffill()", "SAL = ENT.ffill()"),
        "interpolar": ("SAL[COLS] = ENT[COLS].interpolate()", "SAL = ENT.interpolate()"),
    }
    EXPLICACION = {
        "quitar_filas": "Se eliminan las filas que tengan huecos.",
        "media": "Los huecos se rellenan con el promedio de su columna.",
        "mediana": "Los huecos se rellenan con la mediana, que aguanta mejor los valores extremos.",
        "cero": "Los huecos se rellenan con cero. Solo tiene sentido si el hueco de verdad significa cero.",
        "anterior": "Cada hueco toma el ultimo valor observado. Es lo habitual en series de tiempo.",
        "interpolar": "Los huecos se rellenan interpolando entre los valores vecinos.",
    }

    def emit(self, ctx: Any) -> Any:
        ctx.importar("pandas", "pd")
        ent, sal = ctx.entrada("datos"), ctx.salida("datos")
        cols, metodo = ctx.p("columnas"), ctx.p("metodo")
        ctx.nota(self.EXPLICACION[metodo])
        ctx.emitir("REP = ENT.isna().sum().rename('faltantes').to_frame()",
                   REP=ctx.salida("reporte"), ENT=ent)
        con_cols, sin_cols = self.PLANTILLAS[metodo]
        if not cols:
            ctx.emitir(sin_cols, SAL=sal, ENT=ent)
        elif metodo == "quitar_filas":
            ctx.emitir(con_cols, SAL=sal, ENT=ent, COLS=ctx.lit(cols))
        else:
            # Rellenar por columna exige copiar primero: no se asigna sobre la entrada,
            # que puede estar conectada tambien a otra rama del grafo.
            ctx.emitir("SAL = ENT.copy()", SAL=sal, ENT=ent)
            ctx.emitir(con_cols, SAL=ctx.ref_salida("datos"), ENT=ent, COLS=ctx.lit(cols))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        base = entradas.get("datos", Esquema())
        reporte = Esquema(columnas=[Columna(nombre="faltantes_antes", tipo="numerica")])
        return {"datos": base, "reporte": reporte}


CargarCSV.Params.model_rebuild()
