"""Indice de precios de calidad constante (hedonico encadenado).

El problema que resuelve: el precio mediano de las casas vendidas NO es un
indice de precios. Si un trimestre se vendieron mas departamentos chicos que el
anterior, la mediana baja aunque ningun precio haya bajado. Lo que cambio fue
la MEZCLA de lo que se vendio, no el mercado.

Un indice hedonico separa las dos cosas: estima cuanto vale cada caracteristica
(metros, recamaras, antiguedad, zona) y pregunta cuanto costaria la MISMA casa
en cada periodo. Es la metodologia con la que se construyen el Case-Shiller, el
indice de la SHF y los indices de vivienda de casi todos los bancos centrales.

Metodo: variable ficticia de periodos adyacentes. Para cada par (t-1, t) se
juntan las dos muestras y se estima

    log(precio) = a + B'X + d*D_t + e

donde D_t vale 1 si la observacion es del periodo t. Como X controla las
caracteristicas, `d` es el cambio de precio A CALIDAD CONSTANTE, y
exp(d) - 1 es ese cambio en porcentaje. El indice se encadena multiplicando.

Se usan pares adyacentes y no una sola regresion con todas las fichas porque el
mercado cambia: lo que vale un metro cuadrado en 2020 no es lo que vale en
2026, y una regresion unica obliga a que sea lo mismo.

Referencia: Eurostat / OCDE, «Handbook on Residential Property Price Indices»
(2013), cap. 5 («The Time Dummy Hedonic Method»).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ...graph.spec import Columna, Esquema
from ...registry.base import (Ayuda, Ayudante, CampoColumna, CampoColumnas, EspecNodo,
                              Puerto, registrar, registrar_ayudante)

registrar_ayudante(Ayudante(
    nombre="indice_hedonico",
    imports=[("pandas", "pd"), ("numpy", "np")],
    fuente='''
def indice_hedonico(datos, periodo, precio, caracteristicas, base=100.0, minimo_por_periodo=30):
    """Indice de calidad constante por el metodo de la ficticia adyacente.

    Devuelve una fila por periodo con el indice encadenado, el cambio en % a
    calidad constante, cuantas ventas lo sustentan y que tan bien ajusto la
    regresion de ese par.
    """
    import statsmodels.api as sm

    columnas = [periodo, precio] + list(caracteristicas)
    marco = datos[columnas].dropna().copy()
    if (marco[precio] <= 0).any():
        raise ValueError(
            "Hay precios menores o iguales a cero y el indice trabaja en logaritmos. "
            "Filtra esas filas antes: un precio de cero no es un precio barato, es un dato malo.")
    marco["_log_precio"] = np.log(marco[precio].astype(float))

    periodos = sorted(marco[periodo].dropna().unique())
    if len(periodos) < 2:
        raise ValueError("Hace falta mas de un periodo para construir un indice.")

    conteos = marco.groupby(periodo).size()
    flacos = [str(p) for p in periodos if conteos.get(p, 0) < minimo_por_periodo]

    filas = [{
        "periodo": periodos[0], "indice": float(base), "cambio_pct": None,
        "ventas": int(conteos.get(periodos[0], 0)), "r2": None, "nota": "Periodo base",
    }]
    nivel = float(base)

    for anterior, actual in zip(periodos[:-1], periodos[1:]):
        par = marco[marco[periodo].isin([anterior, actual])].copy()
        par["_D"] = (par[periodo] == actual).astype(float)
        X = sm.add_constant(par[list(caracteristicas) + ["_D"]].astype(float), has_constant="add")
        try:
            ajuste = sm.OLS(par["_log_precio"], X).fit(cov_type="HC1")
            delta = float(ajuste.params["_D"])
            cambio = float(np.expm1(delta)) * 100.0
            r2 = float(ajuste.rsquared)
            nota = ""
        except Exception as exc:                       # par degenerado
            cambio, r2, nota = 0.0, None, f"No se pudo estimar ({exc}); se arrastro el nivel."
        nivel = nivel * (1.0 + cambio / 100.0)
        n = int(conteos.get(actual, 0))
        if n < minimo_por_periodo and not nota:
            nota = f"Solo {n} ventas: el cambio de este periodo es ruidoso."
        filas.append({
            "periodo": actual, "indice": nivel, "cambio_pct": cambio,
            "ventas": n, "r2": r2, "nota": nota,
        })

    tabla = pd.DataFrame(filas)
    tabla.attrs["periodos_flacos"] = flacos
    return tabla
''',
))


@registrar
class IndiceHedonico(EspecNodo):
    op = "inmobiliario.indice_hedonico"
    version = "1.0.0"
    familia = "inmobiliario"
    titulo = "Indice de precios de calidad constante"
    prefijo_var = "indice"
    terminal = True
    usa_proyeccion = True
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="indice", tipo="tabla", titulo="Indice encadenado")]
    ayuda = Ayuda(
        que_hace="Construye un indice de precios que separa el movimiento del MERCADO del cambio "
                 "en la mezcla de lo que se vendio. Es lo que hace el Case-Shiller y el indice de "
                 "la SHF.",
        cuando_usarlo="Cuando tienes ventas u ofertas con fecha, precio y caracteristicas, y "
                      "quieres saber si los precios subieron de verdad. La mediana de lo vendido "
                      "NO contesta eso.",
        interpretacion="El indice arranca en 100 en el primer periodo. Si llega a 118, los precios "
                       "a calidad constante subieron 18% desde entonces. La columna cambio_pct es "
                       "el movimiento de cada periodo, ya limpio de composicion.",
        supuestos=["Las caracteristicas que incluyes explican buena parte del precio: lo que dejes "
                   "fuera y cambie con el tiempo se cuela en el indice",
                   "Dentro de cada par de periodos, el valor de cada caracteristica es estable",
                   "Las observaciones de cada periodo son comparables entre si"],
        advertencias=["Con pocas ventas por periodo el indice brinca por ruido, no por mercado. La "
                      "tabla marca los periodos flacos: hazles caso o agrega a trimestres.",
                      "Si tus datos son ASKING PRICE y no precio de cierre, esto mide lo que se "
                      "pide, no lo que se paga. No son lo mismo y la diferencia se abre en las "
                      "bajadas."],
        referencia="Eurostat/OCDE, «Handbook on Residential Property Price Indices» (2013), cap. 5",
        equivalente={"r": "hedonicIndex / IndexNumR", "stata": "—", "eviews": "—"},
    )

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        periodo: str = CampoColumna(description="La columna que marca el periodo (mes, trimestre, año).")
        precio: str = CampoColumna(tipo="numerica", description="El precio de cada operacion.")
        caracteristicas: list[str] = CampoColumnas(
            tipo="numerica", default_factory=list,
            description="Lo que define la calidad: metros, recamaras, baños, antiguedad…")
        base: float = Field(default=100.0, gt=0, description="Valor del indice en el primer periodo.")
        minimo_por_periodo: int = Field(
            default=30, ge=2, le=100_000,
            description="Debajo de esto, el periodo se marca como ruidoso.")

    def columnas_requeridas(self, params: BaseModel) -> set[str] | None:
        return {params.periodo, params.precio, *params.caracteristicas}

    def emit(self, ctx: Any) -> None:
        ctx.usar_ayudante("indice_hedonico")
        ctx.nota("Indice de calidad constante: ficticia de periodos adyacentes sobre log(precio).")
        ctx.emitir(
            "IDX = indice_hedonico(ENT, PER, PRE, CAR, base=BASE, minimo_por_periodo=MIN)",
            IDX=ctx.salida("indice"), ENT=ctx.entrada("datos"),
            PER=ctx.plit("periodo"), PRE=ctx.plit("precio"), CAR=ctx.plit("caracteristicas"),
            BASE=ctx.lit(ctx.p("base")), MIN=ctx.lit(ctx.p("minimo_por_periodo")))

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"indice": Esquema(columnas=[
            Columna(nombre="periodo", tipo="texto"),
            # El indice y el cambio SON estimaciones de un modelo, no mediciones.
            Columna(nombre="indice", tipo="numerica", es_estimado=True),
            Columna(nombre="cambio_pct", tipo="numerica", es_estimado=True),
            Columna(nombre="ventas", tipo="numerica"),
            Columna(nombre="r2", tipo="numerica", es_estimado=True),
            Columna(nombre="nota", tipo="texto"),
        ])}

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        from ...runtime.artefactos import tabla_a_json

        tabla = salidas.get("indice")
        if tabla is None:
            return {}
        return {"indice": tabla_a_json(
            tabla, titulo="Indice de precios de calidad constante",
            estimadas=["indice", "cambio_pct", "r2"])}
