"""Trabajar sobre una muestra, diciendo lo que cuesta.

Con millones de filas, esperar cuatro segundos por iteracion mata la
exploracion: se prueban tres ideas en vez de treinta, y las buenas son de las
que no se probaron. La salida obvia —«corre sobre una muestra»— tiene un
problema: los resultados dejan de ser los de la poblacion y NADIE se acuerda al
leerlos tres semanas despues.

Este nodo hace las dos cosas a la vez. Toma la muestra Y calcula cuanta
precision estas entregando a cambio, columna por columna, con el error estandar
de la media al tamaño elegido. Y trae un interruptor: `usar_todo`. Iteras en
muestra, y para el resultado final lo prendes y corre sobre la poblacion
completa sin tocar nada mas del analisis.

El error de muestreo NO es el error estadistico de siempre. Es adicional, y se
suma a la incertidumbre que ya trae cualquier estimacion. Por eso se reporta
aparte en vez de esconderse en un intervalo de confianza.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...graph.spec import Columna, Esquema
from ...registry.base import (Ayuda, Ayudante, CampoColumna, EspecNodo, Puerto,
                              registrar, registrar_ayudante)

registrar_ayudante(Ayudante(
    nombre="tomar_muestra",
    imports=[("pandas", "pd"), ("numpy", "np")],
    fuente='''
def tomar_muestra(datos, n, semilla, estrato=None, usar_todo=False):
    """Devuelve (muestra, reporte). Con `usar_todo`, la muestra es todo."""
    total = len(datos)
    if usar_todo or n >= total:
        muestra = datos
        n_real = total
    elif estrato:
        # Muestreo estratificado: se conserva la proporcion de cada grupo. Sin
        # esto, un estrato chico (una ciudad con pocas ventas) puede desaparecer
        # de la muestra y con el la posibilidad de estimar su efecto.
        #
        # Se arma con un bucle y no con `groupby().apply()` porque apply se come
        # la columna del estrato: la mete al indice y la muestra sale sin ella.
        parte = n / total
        trozos = []
        for _, grupo in datos.groupby(estrato, observed=True):
            cuantas = min(len(grupo), max(1, int(round(len(grupo) * parte))))
            trozos.append(grupo.sample(cuantas, random_state=semilla))
        muestra = pd.concat(trozos)
        n_real = len(muestra)
    else:
        muestra = datos.sample(n, random_state=semilla)
        n_real = len(muestra)

    filas = []
    fraccion = n_real / total if total else 1.0
    for columna in datos.columns:
        serie = muestra[columna]
        # La comprobacion tiene que ser de pandas y no de numpy:
        # `np.issubdtype` truena con los tipos de extension (StringDtype,
        # Int64, category), que es justo lo que trae un archivo real.
        if not pd.api.types.is_numeric_dtype(serie):
            continue
        valores = serie.dropna().astype(float)
        if len(valores) < 2:
            continue
        desviacion = float(valores.std(ddof=1))
        # Error estandar de la media, con correccion por poblacion finita: al
        # muestrear una parte grande de una poblacion cerrada, el error real es
        # menor que el de la formula de siempre.
        ee = desviacion / np.sqrt(len(valores))
        # Correccion por poblacion finita, SIEMPRE. Al muestrear una parte
        # grande de una poblacion cerrada el error real es menor que el de la
        # formula de siempre, y cuando la muestra ES la poblacion el factor vale
        # cero: sin muestreo no hay error de muestreo. Aplicarla solo cuando la
        # fraccion era menor que uno dejaba un error inventado en el caso
        # «usar todo», que es justo el que se reporta al final.
        if total > 1:
            ee *= float(np.sqrt(max(0.0, (total - len(valores)) / (total - 1))))
        media = float(valores.mean())
        filas.append({
            "columna": str(columna),
            "media_en_muestra": media,
            "error_estandar": float(ee),
            "margen_95_pct": float(1.96 * ee / abs(media) * 100) if media else None,
        })

    reporte = pd.DataFrame(filas)
    reporte.attrs["filas_poblacion"] = total
    reporte.attrs["filas_muestra"] = n_real
    reporte.attrs["fraccion"] = fraccion
    return muestra, reporte
''',
))


@registrar
class Muestra(EspecNodo):
    op = "datos.muestra"
    version = "1.0.0"
    familia = "datos"
    titulo = "Trabajar sobre una muestra"
    prefijo_var = "muestra"
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [
        Puerto(nombre="datos", tipo="tabla", titulo="La muestra"),
        Puerto(nombre="precision", tipo="tabla", titulo="Que precision entregas"),
    ]
    ayuda = Ayuda(
        que_hace="Toma una muestra al azar para que el analisis corra en segundos, y te dice "
                 "cuanta precision estas entregando a cambio, columna por columna.",
        cuando_usarlo="Mientras exploras un archivo de millones de filas. Cuando ya sepas que "
                      "analisis quieres, prende «usar todo» y el mismo lienzo corre sobre la "
                      "poblacion completa.",
        interpretacion="`margen_95_pct` dice cuanto se puede mover la media de esa columna por el "
                       "puro hecho de haber muestreado, en porcentaje de la media. Si es 0.4%, la "
                       "muestra no te esta costando nada; si es 12%, cualquier conclusion fina "
                       "sobre esa columna es de la muestra, no del mercado.",
        supuestos=["La muestra es aleatoria: si tus filas vienen ordenadas por algo que importa, "
                   "usa el estrato para no perder grupos chicos"],
        advertencias=["El error de muestreo es ADICIONAL al error estadistico normal. No lo "
                      "sustituye ni se anula con el.",
                      "Un resultado sacado de una muestra se reporta diciendo que es de una "
                      "muestra, y con que tamaño. Esta tabla es para copiarla al reporte."],
        referencia="Cochran, «Sampling Techniques» (1977), caps. 2 y 5",
        equivalente={"stata": "sample 5", "r": "dplyr::slice_sample(n = 50000)",
                     "python": "df.sample(50_000)"},
    )

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        n: int = Field(default=50_000, ge=100, le=50_000_000,
                       description="Cuantas filas quieres en la muestra.")
        metodo: Literal["aleatorio", "estratificado"] = "aleatorio"
        estrato: str | None = CampoColumna(
            default=None, description="Con «estratificado», la columna cuyos grupos se conservan.")
        usar_todo: bool = Field(
            default=False,
            description="Prendelo para el resultado final: corre sobre TODAS las filas.")

    def columnas_requeridas(self, params: BaseModel) -> set[str] | None:
        # Una muestra puede tocar cualquier columna: el reporte de precision las
        # recorre todas. Devolver None desactiva la poda para este nodo.
        return None

    def emit(self, ctx: Any) -> None:
        ctx.usar_ayudante("tomar_muestra")
        estrato = ctx.p("estrato") if ctx.p("metodo") == "estratificado" else None
        if ctx.p("usar_todo"):
            ctx.nota("Corriendo sobre TODAS las filas (el interruptor «usar todo» esta prendido).")
        else:
            ctx.nota(f"Muestra de {ctx.p('n'):,} filas. Los resultados traen error de muestreo.")
        ctx.emitir(
            "MUE, PRE = tomar_muestra(ENT, N, SEM, estrato=EST, usar_todo=TODO)",
            MUE=ctx.salida("datos"), PRE=ctx.salida("precision"), ENT=ctx.entrada("datos"),
            N=ctx.lit(ctx.p("n")), SEM=ctx.lit(ctx.semilla), EST=ctx.lit(estrato),
            TODO=ctx.lit(bool(ctx.p("usar_todo"))))

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        # La muestra conserva el esquema de entrada: son las MISMAS filas, no
        # valores estimados. Lo estimado es lo que se calcule a partir de ellas,
        # y de eso avisa la tabla de precision.
        entrada = entradas.get("datos") or Esquema(columnas=[])
        return {
            "datos": entrada,
            "precision": Esquema(columnas=[
                Columna(nombre="columna", tipo="texto"),
                Columna(nombre="media_en_muestra", tipo="numerica", es_estimado=True),
                Columna(nombre="error_estandar", tipo="numerica", es_estimado=True),
                Columna(nombre="margen_95_pct", tipo="numerica", es_estimado=True),
            ]),
        }

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        from ...runtime.artefactos import tabla_a_json

        salida: dict[str, Any] = {}
        reporte = salidas.get("precision")
        if reporte is not None:
            poblacion = reporte.attrs.get("filas_poblacion", 0)
            muestra = reporte.attrs.get("filas_muestra", 0)
            fraccion = reporte.attrs.get("fraccion", 1.0)
            titulo = (f"Precision: {muestra:,} de {poblacion:,} filas "
                      f"({fraccion * 100:.1f}%)" if fraccion < 1
                      else f"Sin muestreo: las {poblacion:,} filas")
            salida["precision"] = tabla_a_json(
                reporte, titulo=titulo,
                estimadas=["media_en_muestra", "error_estandar", "margen_95_pct"])
        muestra_df = salidas.get("datos")
        if muestra_df is not None:
            salida["datos"] = tabla_a_json(muestra_df, titulo="La muestra")
        return salida
