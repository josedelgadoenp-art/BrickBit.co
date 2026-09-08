"""Dar forma a la tabla: filtrar, elegir columnas, unir, agrupar, ordenar."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...graph.spec import Columna, Esquema
from ...registry.base import (Ayuda, CampoColumna, CampoColumnas, EspecNodo, Puerto,
                              control, registrar)

OPERADORES = {
    "igual": "==", "distinto": "!=", "mayor": ">", "mayor_igual": ">=",
    "menor": "<", "menor_igual": "<=",
}


@registrar
class Filtrar(EspecNodo):
    op = "datos.filtrar"
    familia = "datos"
    titulo = "Filtrar filas"
    prefijo_var = "filtrado"
    ayuda = Ayuda(
        que_hace="Se queda solo con las filas que cumplen las condiciones que pongas.",
        cuando_usarlo="Para analizar un subconjunto: un periodo, una region, un rango de precios.",
        interpretacion="Revisa cuantas filas quedaron. Si quedaron muy pocas, cualquier modelo que "
                       "estimes despues va a tener errores estandar enormes.",
        advertencias=["Filtrar por una variable relacionada con lo que quieres explicar introduce "
                      "sesgo de seleccion: los resultados dejan de aplicar a la poblacion completa."],
        equivalente={"stata": "keep if", "r": "dplyr::filter()", "spss": "Seleccionar casos"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="datos", tipo="tabla")]

    class Condicion(BaseModel):
        model_config = ConfigDict(extra="forbid")
        columna: str = CampoColumna()
        operador: Literal["igual", "distinto", "mayor", "mayor_igual", "menor",
                          "menor_igual", "contiene", "en_lista", "no_nulo"] = "mayor"
        valor: Any = None

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        # Sin esta pista el formulario cae al control genérico de listas —una
        # caja de texto separada por comas— y el bloque queda inservible desde
        # la pantalla: nadie va a escribir ahí un objeto con columna, operador
        # y valor. Pasó, y filtrar filas es de las primeras cosas que alguien
        # quiere hacer.
        condiciones: list["Filtrar.Condicion"] = Field(
            default_factory=list, json_schema_extra=control("condiciones"))
        unir_con: Literal["y", "o"] = Field(
            default="y", title="Las condiciones se cumplen…")

    def columnas_requeridas(self, params: BaseModel) -> set[str] | None:
        # Las columnas van anidadas dentro de cada condición: la deducción
        # genérica lee pistas de primer nivel y no las vería.
        return {c.columna for c in params.condiciones if c.columna}  # type: ignore[attr-defined]

    def emit(self, ctx: Any) -> Any:
        ctx.importar("pandas", "pd")
        ent, sal = ctx.entrada("datos"), ctx.salida("datos")
        condiciones = ctx.p("condiciones")
        if not condiciones:
            ctx.nota("Sin condiciones: la tabla pasa completa.")
            ctx.emitir("SAL = ENT", SAL=sal, ENT=ent)
            return ctx.fin()

        # Cada condicion se arma como una mascara con nombre propio. Es mas
        # largo que una sola linea, y es lo que hace que el script se lea.
        mascaras = []
        for i, cond in enumerate(condiciones, start=1):
            m = ctx.temporal(f"cond{i}")
            mascaras.append(m)
            plantilla = {
                "contiene": "M = ENT[COL].astype('string').str.contains(VAL, na=False)",
                "en_lista": "M = ENT[COL].isin(VAL)",
                "no_nulo": "M = ENT[COL].notna()",
            }.get(cond.operador, f"M = ENT[COL] {OPERADORES.get(cond.operador, '==')} VAL")
            huecos = {"M": m, "ENT": ent, "COL": ctx.lit(cond.columna)}
            if "VAL" in plantilla:
                huecos["VAL"] = ctx.lit(_valor_tipado(ctx, cond))
            ctx.emitir(plantilla, **huecos)

        operador = "&" if ctx.p("unir_con") == "y" else "|"
        combinada = mascaras[0]
        if len(mascaras) > 1:
            total = ctx.temporal("filtro")
            expr = f" {operador} ".join(f"M{i}" for i in range(len(mascaras)))
            ctx.emitir(f"T = {expr}", T=total, **{f"M{i}": m for i, m in enumerate(mascaras)})
            combinada = total
        ctx.emitir("SAL = ENT[M].copy()", SAL=sal, ENT=ent, M=combinada)
        ctx.nota(f"Se conservan las filas que cumplen {'todas' if ctx.p('unir_con') == 'y' else 'alguna'} "
                 f"de {len(condiciones)} condicion(es).")
        return ctx.fin()


def _valor_tipado(ctx: Any, cond: Any) -> Any:
    """El valor de la condicion, en el tipo de SU columna.

    El formulario entrega texto —una caja de texto entrega texto— y comparar
    `columna_int64 > "10000"` revienta en pandas con «Invalid comparison
    between dtype=int64 and str». Es el filtro mas comun que existe.

    Se resuelve aqui y no en el navegador porque aqui es donde se conoce el
    esquema de la tabla que ENTRA al bloque, y porque asi tambien queda bien
    para un grafo que arme la IA o que alguien escriba a mano. El literal que
    acaba en el script exportado es un numero de verdad, no una cadena.
    """
    valor = cond.valor
    if cond.operador in ("contiene", "en_lista", "no_nulo") or not isinstance(valor, str):
        return valor
    columna = next((c for c in ctx.esquema("datos").columnas if c.nombre == cond.columna), None)
    if columna is None or columna.tipo not in ("numerica", "booleana"):
        return valor
    texto = valor.strip().replace(",", "")     # «1,500» se escribe asi en México
    if columna.tipo == "booleana":
        if texto.lower() in ("true", "verdadero", "si", "sí", "1"):
            return True
        if texto.lower() in ("false", "falso", "no", "0"):
            return False
        return valor
    try:
        numero = float(texto)
    except ValueError:
        # No es un numero: se deja tal cual y el error de pandas dira que la
        # comparacion no se puede hacer, que es la verdad.
        return valor
    return int(numero) if numero.is_integer() and "." not in texto else numero


@registrar
class Seleccionar(EspecNodo):
    op = "datos.seleccionar"
    familia = "datos"
    titulo = "Elegir columnas"
    prefijo_var = "columnas"
    ayuda = Ayuda(
        que_hace="Se queda solo con las columnas que elijas, o quita las que no quieras.",
        cuando_usarlo="Para aligerar la tabla y para que los desplegables de los siguientes pasos no sean un mar.",
        interpretacion="No cambia ninguna cifra: solo reduce el ancho de la tabla.",
        equivalente={"stata": "keep varlist", "r": "dplyr::select()"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="datos", tipo="tabla")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        columnas: list[str] = CampoColumnas(default_factory=list)
        modo: Literal["conservar", "quitar"] = "conservar"

    def columnas_requeridas(self, params: BaseModel) -> set[str] | None:
        # «Quitar» conserva todo lo demás: lo que se usa no está en la lista.
        if params.modo == "quitar":  # type: ignore[attr-defined]
            return None
        return super().columnas_requeridas(params)

    def emit(self, ctx: Any) -> Any:
        ent, sal = ctx.entrada("datos"), ctx.salida("datos")
        if ctx.p("modo") == "conservar":
            ctx.emitir("SAL = ENT[COLS].copy()", SAL=sal, ENT=ent, COLS=ctx.plit("columnas"))
        else:
            ctx.emitir("SAL = ENT.drop(columns=COLS)", SAL=sal, ENT=ent, COLS=ctx.plit("columnas"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        base = entradas.get("datos", Esquema())
        pedidas = set(params.columnas)  # type: ignore[attr-defined]
        if params.modo == "conservar":  # type: ignore[attr-defined]
            cols = [c for c in base.columnas if c.nombre in pedidas]
        else:
            cols = [c for c in base.columnas if c.nombre not in pedidas]
        return {"datos": base.con(*cols, quitar=base.nombres())}


@registrar
class Unir(EspecNodo):
    op = "datos.unir"
    familia = "datos"
    titulo = "Unir dos tablas"
    prefijo_var = "unido"
    ayuda = Ayuda(
        que_hace="Pega dos tablas usando una o varias columnas en comun (una llave).",
        cuando_usarlo="Cuando tus datos vienen en pedazos: precios en una tabla, poblacion en otra.",
        interpretacion="Fijate en cuantas filas quedaron. Si crecieron mucho, la llave no es unica en "
                       "alguna de las dos tablas y estas multiplicando filas sin querer.",
        advertencias=["Con «solo las que coinciden» pierdes en silencio las filas que no encuentran pareja. "
                      "Usa «todas las de la izquierda» si quieres ver cuales se quedaron sin match."],
        equivalente={"stata": "merge", "r": "dplyr::left_join()"},
    )
    entradas = [Puerto(nombre="izquierda", tipo="tabla"), Puerto(nombre="derecha", tipo="tabla")]
    salidas = [Puerto(nombre="datos", tipo="tabla")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        llave_izquierda: list[str] = CampoColumnas(puerto="izquierda", default_factory=list)
        llave_derecha: list[str] = CampoColumnas(puerto="derecha", default_factory=list)
        tipo: Literal["izquierda", "interna", "externa"] = "izquierda"

    def emit(self, ctx: Any) -> Any:
        como = {"izquierda": "left", "interna": "inner", "externa": "outer"}[ctx.p("tipo")]
        der = ctx.p("llave_derecha") or ctx.p("llave_izquierda")
        ctx.emitir("SAL = IZQ.merge(DER, left_on=LI, right_on=LD, how=COMO, validate=None)",
                   SAL=ctx.salida("datos"), IZQ=ctx.entrada("izquierda"), DER=ctx.entrada("derecha"),
                   LI=ctx.plit("llave_izquierda"), LD=ctx.lit(der), COMO=ctx.lit(como))
        ctx.nota({"izquierda": "Se conservan todas las filas de la tabla izquierda.",
                  "interna": "Solo quedan las filas que aparecen en ambas tablas.",
                  "externa": "Se conservan todas las filas de las dos tablas."}[ctx.p("tipo")])
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        izq = entradas.get("izquierda", Esquema())
        der = entradas.get("derecha", Esquema())
        nuevas = [c for c in der.columnas if c.nombre not in set(izq.nombres())]
        return {"datos": izq.con(*nuevas)}


@registrar
class Agrupar(EspecNodo):
    op = "datos.agrupar"
    familia = "datos"
    titulo = "Agrupar y resumir"
    prefijo_var = "resumen"
    ayuda = Ayuda(
        que_hace="Junta las filas por una o varias columnas y calcula un resumen por grupo.",
        cuando_usarlo="Para pasar de microdatos a agregados: de hogares a entidades, de dias a meses.",
        interpretacion="Cada fila del resultado es un grupo. Ojo con el numero de observaciones por "
                       "grupo: un promedio de tres casos no es un promedio.",
        advertencias=["Agregar destruye la variabilidad dentro del grupo. Si tu pregunta es sobre "
                      "individuos, no la respondas con datos agregados (falacia ecologica)."],
        equivalente={"stata": "collapse", "r": "dplyr::group_by() %>% summarise()"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="datos", tipo="tabla")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        por: list[str] = CampoColumnas(default_factory=list)
        columnas: list[str] = CampoColumnas(default_factory=list)
        funcion: Literal["mean", "sum", "median", "min", "max", "std", "count"] = "mean"

    def columnas_requeridas(self, params: BaseModel) -> set[str] | None:
        # Sin lista de columnas, agrupa TODAS las numéricas.
        if not params.columnas:  # type: ignore[attr-defined]
            return None
        return super().columnas_requeridas(params)

    def emit(self, ctx: Any) -> Any:
        por, cols, fn = ctx.p("por"), ctx.p("columnas"), ctx.p("funcion")
        nombre = {"mean": "promedio", "sum": "suma", "median": "mediana", "min": "minimo",
                  "max": "maximo", "std": "desviacion estandar", "count": "conteo"}[fn]
        ctx.nota(f"Por cada combinacion de {', '.join(por)} se calcula el {nombre}.")
        # `.agg(FN)` y no `.FN()`. La plantilla sustituye huecos que son NOMBRES
        # del arbol de sintaxis, y en `x.FN()` el `FN` es el atributo de una
        # llamada: nunca es un `Name`, asi que nunca se sustituia y el emisor
        # reventaba con «la plantilla no usa los huecos ['FN']». Este bloque no
        # habia corrido nunca — ninguna prueba ni ningun ejemplo lo usaba.
        #
        # `agg` con el nombre de la funcion en una cadena hace exactamente lo
        # mismo, y de paso mantiene la regla del emisor: un hueco solo puede
        # ocupar el lugar de un nombre, nunca el de un metodo cualquiera.
        if cols:
            ctx.emitir("SAL = ENT.groupby(POR, as_index=False, observed=True)[COLS].agg(FN)",
                       SAL=ctx.salida("datos"), ENT=ctx.entrada("datos"),
                       POR=ctx.lit(por), COLS=ctx.lit(cols), FN=ctx.lit(fn))
        elif fn == "count":
            # `count` cuenta cualquier columna, tambien las de texto, y por eso
            # es la unica que NO admite `numeric_only`.
            ctx.emitir("SAL = ENT.groupby(POR, as_index=False, observed=True).agg(FN)",
                       SAL=ctx.salida("datos"), ENT=ctx.entrada("datos"),
                       POR=ctx.lit(por), FN=ctx.lit(fn))
        else:
            ctx.emitir("SAL = ENT.groupby(POR, as_index=False, observed=True)"
                       ".agg(FN, numeric_only=True)",
                       SAL=ctx.salida("datos"), ENT=ctx.entrada("datos"),
                       POR=ctx.lit(por), FN=ctx.lit(fn))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        base = entradas.get("datos", Esquema())
        por = list(params.por)          # type: ignore[attr-defined]
        cols = list(params.columnas)    # type: ignore[attr-defined]
        conservar = por + (cols or base.numericas())
        quedan = [c for c in base.columnas if c.nombre in set(conservar)]
        return {"datos": base.con(*quedan, quitar=base.nombres(), n_filas=None)}


@registrar
class Ordenar(EspecNodo):
    op = "datos.ordenar"
    familia = "datos"
    titulo = "Ordenar filas"
    prefijo_var = "ordenado"
    ayuda = Ayuda(
        que_hace="Acomoda las filas por el valor de una o varias columnas.",
        cuando_usarlo="Para ver los extremos, o antes de calcular rezagos y diferencias en datos con fecha.",
        interpretacion="No cambia ninguna cifra: cambia el orden en que las ves.",
        advertencias=["En series de tiempo y panel el orden SI importa: un rezago sobre filas "
                      "desordenadas produce numeros sin sentido y sin ningun aviso."],
        equivalente={"stata": "sort", "r": "dplyr::arrange()"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="datos", tipo="tabla")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        por: list[str] = CampoColumnas(default_factory=list)
        descendente: bool = False

    def emit(self, ctx: Any) -> Any:
        # `reset_index(drop=True)` SOLO cuando el indice no significa nada.
        #
        # Con una serie o un panel ya declarados, el indice ES la fecha (o la
        # pareja entidad-periodo), y tirarlo deja la tabla sin el eje que la
        # define mientras el esquema sigue anunciandolo. Todo lo que viene
        # despues —un rezago, un ARIMA, un pronostico— se queda buscando una
        # columna que ya no existe, o peor, trabaja sobre el orden equivocado.
        esquema = ctx.esquema("datos")
        con_indice = bool(getattr(esquema, "indice_temporal", None)
                          or getattr(esquema, "id_entidad", None))
        if con_indice:
            ctx.nota("Se conserva el índice de la serie o del panel: ordenar cambia el orden "
                     "de las filas, no el eje que las identifica.")
            ctx.emitir("SAL = ENT.sort_values(POR, ascending=ASC)",
                       SAL=ctx.salida("datos"), ENT=ctx.entrada("datos"),
                       POR=ctx.plit("por"), ASC=ctx.lit(not ctx.p("descendente")))
        else:
            ctx.emitir("SAL = ENT.sort_values(POR, ascending=ASC).reset_index(drop=True)",
                       SAL=ctx.salida("datos"), ENT=ctx.entrada("datos"),
                       POR=ctx.plit("por"), ASC=ctx.lit(not ctx.p("descendente")))
        return ctx.fin()


Filtrar.Params.model_rebuild()
