"""Insumo-producto: Leontief, multiplicadores, encadenamientos e impacto sectorial.

Toda la familia descansa en una sola identidad: x = Ax + f, cuya solucion es
x = (I - A)⁻¹ f. Esa inversa —la matriz de Leontief— dice cuanta produccion
total hace falta en cada sector para entregar una unidad de demanda final de
otro, contando todas las vueltas de la cadena.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...graph.spec import Columna, Esquema
from ...registry.base import (Ayuda, Ayudante, CampoColumna, CampoColumnas, EspecNodo,
                              Puerto, registrar, registrar_ayudante)

registrar_ayudante(Ayudante(
    nombre="resolver_leontief",
    imports=[("numpy", "np"), ("pandas", "pd")],
    fuente='''
def resolver_leontief(datos, sectores_col, columnas_sectores, produccion_col,
                      demanda_col=None, empleo_col=None, remuneraciones_col=None):
    """Resuelve el sistema insumo-producto y devuelve todo lo que se deriva de el.

    A = Z / x        coeficientes tecnicos: cuanto insumo del sector i necesita
                     el sector j por cada peso que produce.
    L = (I - A)^-1   inversa de Leontief: requerimientos totales, directos e
                     indirectos.

    Si (I - A) es singular, el sistema no es productivo: casi siempre significa
    que la matriz de transacciones y el vector de produccion no son consistentes
    (unidades distintas, o produccion menor que los insumos).
    """
    sectores = datos[sectores_col].astype(str).tolist()
    Z = datos[columnas_sectores].to_numpy(float)
    x = datos[produccion_col].to_numpy(float)
    n = len(sectores)

    seguro = np.where(x == 0, np.nan, x)
    A = Z / seguro                       # se divide por la produccion del sector COMPRADOR (columna)
    A = np.nan_to_num(A, nan=0.0)

    I = np.eye(n)
    try:
        L = np.linalg.inv(I - A)
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "El sistema (I - A) no se puede invertir: revisa que la matriz de transacciones y "
            "la produccion total esten en las mismas unidades y en el mismo anio."
        ) from exc

    mult_produccion = L.sum(axis=0)      # suma por columna = multiplicador de produccion tipo I

    resultado = {
        "sectores": sectores,
        "A": pd.DataFrame(A, index=sectores, columns=sectores),
        "L": pd.DataFrame(L, index=sectores, columns=sectores),
        "produccion": pd.Series(x, index=sectores),
    }

    filas = [{"sector": s, "multiplicador_produccion": float(mult_produccion[i])}
             for i, s in enumerate(sectores)]

    if empleo_col is not None:
        e = datos[empleo_col].to_numpy(float) / seguro       # empleo por unidad de produccion
        e = np.nan_to_num(e, nan=0.0)
        mult_empleo = (e[:, None] * L).sum(axis=0)
        for i, f in enumerate(filas):
            f["coeficiente_empleo"] = float(e[i])
            f["multiplicador_empleo"] = float(mult_empleo[i])

    if remuneraciones_col is not None:
        v = datos[remuneraciones_col].to_numpy(float) / seguro
        v = np.nan_to_num(v, nan=0.0)
        mult_ingreso = (v[:, None] * L).sum(axis=0)
        for i, f in enumerate(filas):
            f["coeficiente_ingreso"] = float(v[i])
            f["multiplicador_ingreso"] = float(mult_ingreso[i])

    if demanda_col is not None:
        d = datos[demanda_col].to_numpy(float)
        for i, f in enumerate(filas):
            f["demanda_final"] = float(d[i])

    resultado["multiplicadores"] = pd.DataFrame(filas)
    return resultado
''',
))

registrar_ayudante(Ayudante(
    nombre="encadenamientos_rasmussen",
    imports=[("numpy", "np"), ("pandas", "pd")],
    fuente='''
def encadenamientos_rasmussen(sistema):
    """Encadenamientos hacia atras y hacia adelante, normalizados (Rasmussen 1956).

    Hacia atras (U_j)  : cuanto jala el sector j al resto cuando produce.
    Hacia adelante (U_i): cuanto lo jala el resto a el cuando ellos producen.

    Normalizados al promedio de la economia: por arriba de 1 significa "mas
    encadenado que el sector promedio". Un sector con los dos indices por
    encima de 1 es un sector clave: la politica industrial suele empezar ahi.
    """
    L = sistema["L"].to_numpy(float)
    n = L.shape[0]
    atras = L.sum(axis=0)
    adelante = L.sum(axis=1)
    u_atras = (atras / atras.mean())
    u_adelante = (adelante / adelante.mean())

    # Dispersion: un encadenamiento alto concentrado en un solo proveedor es
    # mas fragil que el mismo encadenamiento repartido.
    v_atras = L.std(axis=0, ddof=1) / (atras / n)

    filas = []
    for i, s in enumerate(sistema["sectores"]):
        if u_atras[i] > 1 and u_adelante[i] > 1:
            tipo = "Clave (jala y es jalado)"
        elif u_atras[i] > 1:
            tipo = "Impulsor (jala a sus proveedores)"
        elif u_adelante[i] > 1:
            tipo = "Base (insumo de muchos otros)"
        else:
            tipo = "Independiente"
        filas.append({
            "sector": s,
            "encadenamiento_atras": float(u_atras[i]),
            "encadenamiento_adelante": float(u_adelante[i]),
            "dispersion_atras": float(v_atras[i]),
            "tipo": tipo,
        })
    return pd.DataFrame(filas)
''',
))

registrar_ayudante(Ayudante(
    nombre="impacto_demanda",
    imports=[("numpy", "np"), ("pandas", "pd")],
    fuente='''
def impacto_demanda(sistema, choques):
    """Efecto total de un cambio en la demanda final: dx = L @ df.

    `choques` es {sector: monto}. El resultado separa el efecto directo (lo que
    el sector produce de mas para atender el pedido) del indirecto (lo que
    producen de mas sus proveedores, y los proveedores de sus proveedores).
    """
    sectores = sistema["sectores"]
    L = sistema["L"].to_numpy(float)
    df = np.zeros(len(sectores))
    for sector, monto in choques.items():
        if sector not in sectores:
            raise ValueError(f"El sector '{sector}' no esta en la matriz. Sectores: {sectores}")
        df[sectores.index(sector)] = float(monto)

    dx = L @ df
    filas = []
    for i, s in enumerate(sectores):
        filas.append({
            "sector": s,
            "choque_demanda": float(df[i]),
            "produccion_adicional": float(dx[i]),
            "efecto_directo": float(df[i]),
            "efecto_indirecto": float(dx[i] - df[i]),
        })
    tabla = pd.DataFrame(filas)
    mult = sistema.get("multiplicadores")
    for col, destino in [("coeficiente_empleo", "empleo_adicional"),
                         ("coeficiente_ingreso", "ingreso_adicional")]:
        if mult is not None and col in mult.columns:
            tabla[destino] = tabla["produccion_adicional"].to_numpy() * mult[col].to_numpy()
    return tabla
''',
))


@registrar
class SistemaInsumoProducto(EspecNodo):
    op = "macro.insumo_producto"
    familia = "macro"
    titulo = "Resolver matriz insumo-producto"
    prefijo_var = "mio"
    ayuda = Ayuda(
        que_hace="Calcula los coeficientes tecnicos y la inversa de Leontief, y de ahi los multiplicadores "
                 "de produccion, empleo e ingreso de cada sector.",
        cuando_usarlo="Cuando quieras saber que arrastra un sector al resto de la economia: cuanto "
                      "produccion, empleo e ingreso se generan por cada peso de demanda final.",
        interpretacion="Un multiplicador de produccion de 1.8 significa que por cada peso de demanda final "
                       "a ese sector, la economia produce 1.80 pesos en total: uno directo y 80 centavos "
                       "repartidos entre sus proveedores.",
        supuestos=["Coeficientes tecnicos fijos: la receta productiva no cambia con la escala ni con los precios.",
                   "Sin restricciones de capacidad: se supone que la oferta responde a cualquier demanda.",
                   "Rendimientos constantes a escala."],
        advertencias=["Estos supuestos hacen que los multiplicadores sean una COTA SUPERIOR del efecto real. "
                      "Sirven para ordenar sectores entre si, no para prometer empleos.",
                      "Una matriz insumo-producto vieja describe una estructura productiva que ya cambio."],
        referencia="Leontief (1936); Miller y Blair, «Input-Output Analysis», 2a ed.",
        equivalente={"r": "ioanalysis", "eviews": "—"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla", titulo="Matriz de transacciones")]
    salidas = [Puerto(nombre="sistema", tipo="mio", titulo="Sistema resuelto"),
               Puerto(nombre="multiplicadores", tipo="tabla", titulo="Multiplicadores"),
               Puerto(nombre="leontief", tipo="tabla", titulo="Inversa de Leontief", requerido=False)]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        columna_sectores: str = CampoColumna(default="sector")
        columnas_matriz: list[str] = CampoColumnas(default_factory=list)
        produccion_total: str = CampoColumna(default="produccion_total")
        demanda_final: str | None = CampoColumna(default="demanda_final")
        empleo: str | None = CampoColumna(default=None)
        remuneraciones: str | None = CampoColumna(default=None)

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("resolver_leontief")
        ctx.nota("A = Z / x son los coeficientes tecnicos; L = (I - A)⁻¹ es la inversa de Leontief.")
        ctx.nota("Los multiplicadores son las sumas por columna de L: efecto total, directo mas indirecto.")
        ctx.emitir("SIS = resolver_leontief(ENT, SECT, COLS, PROD, demanda_col=DEM, "
                   "empleo_col=EMP, remuneraciones_col=REM)",
                   SIS=ctx.salida("sistema"), ENT=ctx.entrada("datos"),
                   SECT=ctx.plit("columna_sectores"), COLS=ctx.plit("columnas_matriz"),
                   PROD=ctx.plit("produccion_total"), DEM=ctx.plit("demanda_final"),
                   EMP=ctx.plit("empleo"), REM=ctx.plit("remuneraciones"))
        ctx.emitir("MULT = SIS['multiplicadores']", MULT=ctx.salida("multiplicadores"),
                   SIS=ctx.ref_salida("sistema"))
        ctx.emitir("LEO = SIS['L'].round(4)", LEO=ctx.salida("leontief"), SIS=ctx.ref_salida("sistema"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        cols = [Columna(nombre="sector", tipo="texto"),
                Columna(nombre="multiplicador_produccion", tipo="numerica", es_estimado=True)]
        if params.empleo:            # type: ignore[attr-defined]
            cols += [Columna(nombre="coeficiente_empleo", tipo="numerica", es_estimado=True),
                     Columna(nombre="multiplicador_empleo", tipo="numerica", es_estimado=True)]
        if params.remuneraciones:    # type: ignore[attr-defined]
            cols += [Columna(nombre="coeficiente_ingreso", tipo="numerica", es_estimado=True),
                     Columna(nombre="multiplicador_ingreso", tipo="numerica", es_estimado=True)]
        if params.demanda_final:     # type: ignore[attr-defined]
            cols.append(Columna(nombre="demanda_final", tipo="numerica"))
        return {"multiplicadores": Esquema(columnas=cols), "leontief": Esquema()}

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        from ...runtime.artefactos import tabla_a_json

        out: dict[str, Any] = {}
        if (m := salidas.get("multiplicadores")) is not None:
            out["multiplicadores"] = tabla_a_json(
                m, titulo="Multiplicadores por sector",
                estimadas=[c for c in m.columns if c.startswith(("multiplicador", "coeficiente"))])
        if (l := salidas.get("leontief")) is not None:
            out["leontief"] = tabla_a_json(l, titulo="Inversa de Leontief (requerimientos totales)")
        return out


@registrar
class Encadenamientos(EspecNodo):
    op = "macro.encadenamientos"
    familia = "macro"
    titulo = "Encadenamientos (Rasmussen)"
    prefijo_var = "encadenamientos"
    terminal = True
    ayuda = Ayuda(
        que_hace="Ordena los sectores segun cuanto jalan al resto de la economia y cuanto son jalados por ella.",
        cuando_usarlo="Para identificar sectores clave: los que si crecen, arrastran; y que ademas son "
                      "insumo de muchos otros.",
        interpretacion="Los indices estan normalizados al promedio de la economia: por arriba de 1 "
                       "significa mas encadenado que el sector promedio. Un sector con los dos indices "
                       "arriba de 1 es «clave», y es donde la politica industrial rinde mas.",
        advertencias=["Un encadenamiento alto concentrado en un solo proveedor es mas fragil que el mismo "
                      "encadenamiento repartido. Por eso se reporta tambien la dispersion."],
        referencia="Rasmussen (1956); Hirschman (1958)",
    )
    entradas = [Puerto(nombre="sistema", tipo="mio")]
    salidas = [Puerto(nombre="encadenamientos", tipo="tabla")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("encadenamientos_rasmussen")
        ctx.emitir("SAL = encadenamientos_rasmussen(SIS)",
                   SAL=ctx.salida("encadenamientos"), SIS=ctx.entrada("sistema"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"encadenamientos": Esquema(columnas=[
            Columna(nombre="sector", tipo="texto"),
            Columna(nombre="encadenamiento_atras", tipo="numerica", es_estimado=True),
            Columna(nombre="encadenamiento_adelante", tipo="numerica", es_estimado=True),
            Columna(nombre="dispersion_atras", tipo="numerica", es_estimado=True),
            Columna(nombre="tipo", tipo="categorica")])}


@registrar
class ImpactoSectorial(EspecNodo):
    op = "macro.impacto"
    familia = "macro"
    titulo = "Impacto de un choque de demanda"
    prefijo_var = "impacto"
    terminal = True
    ayuda = Ayuda(
        que_hace="Simula que le pasa a toda la economia si sube la demanda final de uno o varios sectores.",
        cuando_usarlo="«Si se invierten 5,000 millones en construccion, ¿cuanta produccion, empleo e "
                      "ingreso se generan, y en que sectores?»",
        interpretacion="El efecto directo es lo que produce de mas el sector que recibe el choque. El "
                       "indirecto es lo que producen de mas sus proveedores, y los proveedores de estos, "
                       "hasta que la cadena se agota.",
        advertencias=["Esto es una COTA SUPERIOR. Supone capacidad ociosa, precios fijos y que la receta "
                      "productiva no cambia. En una economia cerca de su capacidad, el efecto real es menor "
                      "y parte se va a precios o a importaciones.",
                      "El resultado esta en las mismas unidades que la matriz. Si la matriz esta en miles "
                      "de pesos, el choque tambien."],
        referencia="Miller y Blair, cap. 6",
    )
    entradas = [Puerto(nombre="sistema", tipo="mio")]
    salidas = [Puerto(nombre="impacto", tipo="tabla")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        choques: dict[str, float] = Field(
            default_factory=dict,
            json_schema_extra={"abaco": {"control": "mapa_sectores"}},
        )

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("impacto_demanda")
        choques = ctx.p("choques")
        ctx.nota("Choque de demanda final: " + ", ".join(f"{k} = {v:,.0f}" for k, v in choques.items()) + ".")
        ctx.nota("Cota superior: supone capacidad ociosa, precios fijos y receta productiva constante.")
        ctx.emitir("SAL = impacto_demanda(SIS, CHOQUES)",
                   SAL=ctx.salida("impacto"), SIS=ctx.entrada("sistema"), CHOQUES=ctx.plit("choques"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"impacto": Esquema(columnas=[
            Columna(nombre="sector", tipo="texto"), Columna(nombre="choque_demanda", tipo="numerica"),
            Columna(nombre="produccion_adicional", tipo="numerica", es_estimado=True),
            Columna(nombre="efecto_directo", tipo="numerica", es_estimado=True),
            Columna(nombre="efecto_indirecto", tipo="numerica", es_estimado=True)])}

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        from ...runtime.artefactos import tabla_a_json

        i = salidas.get("impacto")
        if i is None:
            return {}
        return {"impacto": tabla_a_json(
            i, titulo="Impacto sobre la economia",
            estimadas=[c for c in i.columns if c not in ("sector", "choque_demanda")])}
