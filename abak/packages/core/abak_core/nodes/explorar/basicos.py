"""Mirar los datos antes de modelarlos."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...graph.spec import Columna, Esquema
from ...registry.base import (Ayuda, Ayudante, CampoColumna, CampoColumnas, EspecNodo,
                              Puerto, registrar, registrar_ayudante)

registrar_ayudante(Ayudante(
    nombre="descriptivos",
    imports=[("pandas", "pd")],
    fuente='''
def descriptivos(datos, columnas=None, por=None):
    """Tabla de descriptivos con lo que de verdad hay que ver antes de modelar.

    Incluye faltantes y asimetria porque son las dos cosas que mas seguido
    explican un resultado raro mas adelante, y las dos que casi nunca aparecen
    en un `describe()` que alguien mire con calma.
    """
    marco = datos[columnas] if columnas else datos.select_dtypes("number")

    def bloque(sub, etiqueta=None):
        d = sub.describe().T
        d = d.rename(columns={"count": "n", "mean": "media", "std": "desv_est",
                              "min": "minimo", "25%": "p25", "50%": "mediana",
                              "75%": "p75", "max": "maximo"})
        d["faltantes"] = sub.isna().sum()
        d["asimetria"] = sub.skew(numeric_only=True)
        d["coef_variacion"] = (d["desv_est"] / d["media"]).abs()
        d = d.reset_index(names="variable")
        if etiqueta is not None:
            d.insert(0, "grupo", etiqueta)
        return d

    if por:
        partes = [bloque(g.select_dtypes("number"), etiqueta=str(v))
                  for v, g in datos.groupby(por, observed=True)]
        return pd.concat(partes, ignore_index=True)
    return bloque(marco)
''',
))

registrar_ayudante(Ayudante(
    nombre="matriz_correlacion",
    imports=[("pandas", "pd"), ("numpy", "np")],
    fuente='''
def matriz_correlacion(datos, columnas, metodo="pearson", con_p=True):
    """Correlaciones en formato largo, con p-valor y estrellas.

    En formato largo y no como matriz cuadrada porque asi se puede ordenar,
    filtrar y graficar, que es lo que uno quiere hacer con ella.
    """
    from scipy import stats

    marco = datos[columnas].dropna()
    filas = []
    for i, a in enumerate(columnas):
        for b in columnas[i + 1:]:
            if metodo == "spearman":
                r, p = stats.spearmanr(marco[a], marco[b])
            else:
                r, p = stats.pearsonr(marco[a], marco[b])
            filas.append({
                "variable_1": a, "variable_2": b, "correlacion": float(r),
                "p_valor": float(p) if con_p else None,
                "estrellas": ("***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""),
                "n": int(len(marco)),
            })
    return pd.DataFrame(filas).sort_values("correlacion", key=abs, ascending=False, ignore_index=True)
''',
))


@registrar
class Descriptivos(EspecNodo):
    op = "explorar.descriptivos"
    familia = "explorar"
    titulo = "Estadisticos descriptivos"
    prefijo_var = "descriptivos"
    terminal = True
    ayuda = Ayuda(
        que_hace="Resume cada variable: cuantos datos hay, promedio, dispersion, minimo, maximo y cuantos faltan.",
        cuando_usarlo="Siempre, antes de modelar. La mitad de los problemas de un analisis se ven aqui.",
        interpretacion="Mira tres cosas: los faltantes (¿cuantas filas vas a perder?), el coeficiente de "
                       "variacion (si pasa de 1, la variable es muy dispersa) y la asimetria (si pasa de "
                       "2, considera trabajar en logaritmos).",
        equivalente={"stata": "summarize, detail", "r": "summary()", "spss": "Descriptivos"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="tabla", tipo="tabla", titulo="Descriptivos")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        columnas: list[str] = CampoColumnas(tipo="numerica", default_factory=list)
        por: str | None = CampoColumna(default=None)

    def columnas_requeridas(self, params: BaseModel) -> set[str] | None:
        # Sin lista, resume TODAS las numéricas: no se puede podar nada.
        if not params.columnas:  # type: ignore[attr-defined]
            return None
        return super().columnas_requeridas(params)

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("descriptivos")
        if ctx.p("por"):
            ctx.nota(f"Un bloque de descriptivos por cada valor de «{ctx.p('por')}».")
        ctx.emitir("SAL = descriptivos(ENT, columnas=COLS, por=POR)",
                   SAL=ctx.salida("tabla"), ENT=ctx.entrada("datos"),
                   COLS=ctx.lit(ctx.p("columnas") or None), POR=ctx.plit("por"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        cols = [Columna(nombre=n, tipo="texto" if n == "variable" else "numerica")
                for n in ["variable", "n", "media", "desv_est", "minimo", "p25", "mediana",
                          "p75", "maximo", "faltantes", "asimetria", "coef_variacion"]]
        return {"tabla": Esquema(columnas=cols)}


@registrar
class Correlacion(EspecNodo):
    op = "explorar.correlacion"
    familia = "explorar"
    titulo = "Correlaciones"
    prefijo_var = "correlaciones"
    terminal = True
    ayuda = Ayuda(
        que_hace="Mide que tan juntas se mueven cada par de variables, y si esa relacion se distingue del azar.",
        cuando_usarlo="Antes de una regresion, para ver que variables se pisan entre si.",
        interpretacion="La correlacion va de -1 a 1. Cerca de cero no significa «sin relacion»: significa "
                       "sin relacion LINEAL. Una U invertida perfecta da correlacion cero.",
        advertencias=["Correlacion no es causalidad, y con muchas variables aparecen correlaciones altas "
                      "por puro azar. Con 20 variables hay 190 pares: unos 10 saldran «significativos» "
                      "al 5% sin que exista nada."],
        equivalente={"stata": "pwcorr, sig", "r": "cor()", "spss": "Correlaciones bivariadas"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="tabla", tipo="tabla", titulo="Correlaciones")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        columnas: list[str] = CampoColumnas(tipo="numerica", default_factory=list)
        metodo: Literal["pearson", "spearman"] = "pearson"

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("matriz_correlacion")
        ctx.nota("Pearson mide relacion lineal." if ctx.p("metodo") == "pearson"
                 else "Spearman mide si se mueven en el mismo sentido, aunque no sea de forma lineal. "
                      "Aguanta mejor los valores extremos.")
        ctx.emitir("SAL = matriz_correlacion(ENT, COLS, metodo=MET)",
                   SAL=ctx.salida("tabla"), ENT=ctx.entrada("datos"),
                   COLS=ctx.plit("columnas"), MET=ctx.plit("metodo"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"tabla": Esquema(columnas=[
            Columna(nombre="variable_1", tipo="texto"), Columna(nombre="variable_2", tipo="texto"),
            Columna(nombre="correlacion", tipo="numerica"), Columna(nombre="p_valor", tipo="numerica"),
            Columna(nombre="estrellas", tipo="texto"), Columna(nombre="n", tipo="numerica")])}


@registrar
class ComparaGrupos(EspecNodo):
    op = "explorar.comparar_grupos"
    familia = "explorar"
    titulo = "Comparar grupos (t / ANOVA)"
    prefijo_var = "comparacion"
    terminal = True
    ayuda = Ayuda(
        que_hace="Compara el promedio de una variable entre dos o mas grupos y dice si la diferencia se "
                 "distingue del azar.",
        cuando_usarlo="«¿Gana mas quien tiene credito?» «¿El precio por m² difiere entre regiones?»",
        interpretacion="El p-valor dice si la diferencia es distinguible del azar, NO si es importante. "
                       "Con muestras grandes, diferencias irrelevantes salen significativas. Mira "
                       "siempre el tamano de la diferencia en las unidades del problema.",
        supuestos=["La prueba t supone varianzas parecidas; se usa la version de Welch, que no lo exige."],
        equivalente={"stata": "ttest y, by(g) / oneway", "r": "t.test()", "spss": "Comparar medias"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="tabla", tipo="tabla", titulo="Resultado")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        variable: str = CampoColumna(tipo="numerica")
        grupo: str = CampoColumna()

    def emit(self, ctx: Any) -> Any:
        ctx.importar("pandas", "pd")
        ctx.importar("scipy.stats", "stats")
        ctx.usar_ayudante("comparar_grupos")
        ctx.emitir("SAL = comparar_grupos(ENT, VAR, GRP)",
                   SAL=ctx.salida("tabla"), ENT=ctx.entrada("datos"),
                   VAR=ctx.plit("variable"), GRP=ctx.plit("grupo"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"tabla": Esquema(columnas=[
            Columna(nombre="prueba", tipo="texto"), Columna(nombre="estadistico", tipo="numerica"),
            Columna(nombre="p_valor", tipo="numerica"), Columna(nombre="grupos", tipo="numerica"),
            Columna(nombre="lectura", tipo="texto")])}


registrar_ayudante(Ayudante(
    nombre="comparar_grupos",
    imports=[("pandas", "pd")],
    fuente='''
def comparar_grupos(datos, variable, grupo):
    """t de Welch con dos grupos, ANOVA con mas de dos. Devuelve tambien las medias."""
    from scipy import stats

    partes = [g[variable].dropna() for _, g in datos.groupby(grupo, observed=True)]
    partes = [p for p in partes if len(p) > 1]
    if len(partes) < 2:
        raise ValueError(f"Hacen falta al menos dos grupos con datos en '{grupo}'.")

    if len(partes) == 2:
        est, p = stats.ttest_ind(partes[0], partes[1], equal_var=False)
        nombre = "t de Welch (dos grupos)"
    else:
        est, p = stats.f_oneway(*partes)
        nombre = f"ANOVA ({len(partes)} grupos)"

    medias = datos.groupby(grupo, observed=True)[variable].agg(["count", "mean", "std"])
    resumen = " · ".join(f"{i}: {r['mean']:.4g} (n={int(r['count'])})" for i, r in medias.iterrows())
    return pd.DataFrame([{
        "prueba": nombre, "estadistico": float(est), "p_valor": float(p),
        "grupos": len(partes),
        "lectura": (("La diferencia entre grupos se distingue del azar. " if p < 0.05
                     else "La diferencia NO se distingue del azar. ") +
                    "Medias — " + resumen +
                    ". El p-valor no dice si la diferencia es importante: eso lo dices tu, mirando su tamano."),
    }])
''',
))
