"""Crear variables nuevas a partir de las que ya hay.

Ningun nodo de esta familia recibe una expresion libre del usuario. Las
operaciones son un conjunto cerrado: es lo que permite generar codigo sin
ninguna ruta por la que texto del usuario se vuelva codigo, y de paso es lo que
hace que la herramienta se pueda usar sin saber programar.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...graph.spec import Columna, Esquema
from ...registry.base import Ayuda, CampoColumna, CampoColumnas, EspecNodo, Puerto, registrar

UNARIAS: dict[str, tuple[str, str]] = {
    "log":        ("np.log(ENT[A])",        "logaritmo natural"),
    "log10":      ("np.log10(ENT[A])",      "logaritmo base 10"),
    "exp":        ("np.exp(ENT[A])",        "exponencial"),
    "raiz":       ("np.sqrt(ENT[A])",       "raiz cuadrada"),
    "cuadrado":   ("ENT[A] ** 2",           "al cuadrado"),
    "inverso":    ("1 / ENT[A]",            "inverso (1/x)"),
    "absoluto":   ("ENT[A].abs()",          "valor absoluto"),
}
BINARIAS: dict[str, tuple[str, str]] = {
    "suma":     ("ENT[A] + ENT[B]",  "suma"),
    "resta":    ("ENT[A] - ENT[B]",  "resta"),
    "producto": ("ENT[A] * ENT[B]",  "producto"),
    "razon":    ("ENT[A] / ENT[B]",  "razon (division)"),
    "porciento":("100 * ENT[A] / ENT[B]", "porcentaje que A representa de B"),
}


@registrar
class Calcular(EspecNodo):
    op = "transformar.calcular"
    familia = "transformar"
    titulo = "Calcular variable"
    prefijo_var = "datos"
    ayuda = Ayuda(
        que_hace="Crea una columna nueva aplicando una operacion a una o dos columnas existentes.",
        cuando_usarlo="El logaritmo es el caso mas comun en economia: convierte un efecto multiplicativo "
                      "en uno aditivo y hace que los coeficientes se lean como elasticidades.",
        interpretacion="En un modelo log-log, el coeficiente es la elasticidad: si sube 1% la explicativa, "
                       "la dependiente cambia ese porcentaje.",
        advertencias=["El logaritmo de cero o de un numero negativo no existe: esas filas quedan como huecos.",
                      "Dividir entre una columna que tiene ceros produce infinitos."],
        equivalente={"stata": "gen lny = log(y)", "r": "mutate(lny = log(y))"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="datos", tipo="tabla")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        operacion: Literal[tuple(UNARIAS) + tuple(BINARIAS)] = "log"  # type: ignore[valid-type]
        columna_a: str = CampoColumna(tipo="numerica")
        columna_b: str | None = CampoColumna(tipo="numerica", default=None)
        nombre_nuevo: str = Field(default="", description="Si lo dejas vacio, Abak propone un nombre")

    def _nombre(self, params: BaseModel) -> str:
        if params.nombre_nuevo:              # type: ignore[attr-defined]
            return params.nombre_nuevo       # type: ignore[attr-defined]
        op, a, b = params.operacion, params.columna_a, params.columna_b  # type: ignore[attr-defined]
        if op in UNARIAS:
            return f"{op}_{a}"
        return f"{a}_{op}_{b}" if b else f"{op}_{a}"

    def emit(self, ctx: Any) -> Any:
        ctx.importar("numpy", "np")
        op = ctx.p("operacion")
        nuevo = self._nombre(ctx.params)
        plantilla, humano = (UNARIAS | BINARIAS)[op]
        ctx.nota(f"«{nuevo}» = {humano} de «{ctx.p('columna_a')}»"
                 + (f" y «{ctx.p('columna_b')}»" if op in BINARIAS else "") + ".")
        ctx.emitir("SAL = ENT.copy()", SAL=ctx.salida("datos"), ENT=ctx.entrada("datos"))
        huecos = {"SAL": ctx.ref_salida("datos"), "ENT": ctx.entrada("datos"),
                  "NUEVO": ctx.lit(nuevo), "A": ctx.lit(ctx.p("columna_a"))}
        if op in BINARIAS:
            huecos["B"] = ctx.lit(ctx.p("columna_b"))
        ctx.emitir(f"SAL[NUEVO] = {plantilla}", **huecos)
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        base = entradas.get("datos", Esquema())
        fuentes = [params.columna_a, params.columna_b]  # type: ignore[attr-defined]
        hereda = base.hay_estimados([c for c in fuentes if c])
        return {"datos": base.con(Columna(nombre=self._nombre(params), tipo="numerica",
                                          es_estimado=hereda))}


@registrar
class Rezago(EspecNodo):
    op = "transformar.rezago"
    familia = "transformar"
    titulo = "Rezago o adelanto"
    prefijo_var = "datos"
    ayuda = Ayuda(
        que_hace="Crea una columna con el valor de periodos anteriores (rezago) o posteriores (adelanto).",
        cuando_usarlo="Cuando el efecto tarda en aparecer: la tasa de hoy afecta la inversion del trimestre "
                      "que entra, no la de hoy.",
        interpretacion="Un coeficiente sobre el rezago 1 dice cuanto responde la variable a lo que paso "
                       "un periodo antes.",
        supuestos=["Los datos deben estar ordenados por fecha. Si es panel, el rezago se calcula dentro de cada entidad."],
        advertencias=["Cada rezago te cuesta observaciones al principio de la serie.",
                      "Meter un adelanto como explicativa suele ser un error: estarias explicando el pasado con el futuro."],
        equivalente={"stata": "L.y / F.y", "r": "dplyr::lag()", "eviews": "y(-1)"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="datos", tipo="tabla")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        columnas: list[str] = CampoColumnas(tipo="numerica", default_factory=list)
        periodos: int = Field(default=1, ge=-24, le=24)
        por_entidad: str | None = CampoColumna(default=None)

    def _nombres(self, params: BaseModel) -> list[tuple[str, str]]:
        k = params.periodos  # type: ignore[attr-defined]
        pre = f"rez{abs(k)}" if k > 0 else f"ade{abs(k)}"
        return [(c, f"{pre}_{c}") for c in params.columnas]  # type: ignore[attr-defined]

    def emit(self, ctx: Any) -> Any:
        k, ent = ctx.p("periodos"), ctx.entrada("datos")
        ctx.nota(f"{'Rezago' if k > 0 else 'Adelanto'} de {abs(k)} periodo(s)."
                 + (f" Calculado dentro de cada «{ctx.p('por_entidad')}»." if ctx.p("por_entidad") else ""))
        ctx.emitir("SAL = ENT.copy()", SAL=ctx.salida("datos"), ENT=ent)
        for origen, nuevo in self._nombres(ctx.params):
            if ctx.p("por_entidad"):
                ctx.emitir("SAL[NUEVO] = SAL.groupby(GRP, observed=True)[COL].shift(K)",
                           SAL=ctx.ref_salida("datos"), NUEVO=ctx.lit(nuevo),
                           GRP=ctx.plit("por_entidad"), COL=ctx.lit(origen), K=ctx.lit(k))
            else:
                ctx.emitir("SAL[NUEVO] = SAL[COL].shift(K)",
                           SAL=ctx.ref_salida("datos"), NUEVO=ctx.lit(nuevo),
                           COL=ctx.lit(origen), K=ctx.lit(k))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        base = entradas.get("datos", Esquema())
        nuevas = [Columna(nombre=n, tipo="numerica",
                          es_estimado=base.hay_estimados([o])) for o, n in self._nombres(params)]
        return {"datos": base.con(*nuevas)}


@registrar
class Crecimiento(EspecNodo):
    op = "transformar.crecimiento"
    familia = "transformar"
    titulo = "Tasa de crecimiento o diferencia"
    prefijo_var = "datos"
    ayuda = Ayuda(
        que_hace="Calcula el cambio de una variable entre periodos: en diferencia, en porcentaje o en log-diferencia.",
        cuando_usarlo="Casi todas las series economicas en niveles tienen raiz unitaria. Diferenciarlas es "
                      "el paso que las vuelve estacionarias y evita una regresion espuria.",
        interpretacion="La log-diferencia multiplicada por 100 es, para cambios chicos, casi igual al "
                       "crecimiento porcentual, y tiene la ventaja de ser simetrica: subir 10% y bajar 10% se cancelan.",
        supuestos=["Los periodos deben estar ordenados y completos."],
        advertencias=["Diferenciar de mas convierte una serie estacionaria en ruido con autocorrelacion negativa."],
        equivalente={"stata": "D.y", "r": "diff()", "eviews": "d(y) / dlog(y)"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="datos", tipo="tabla")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        columnas: list[str] = CampoColumnas(tipo="numerica", default_factory=list)
        tipo: Literal["diferencia", "porcentaje", "log_diferencia"] = "porcentaje"
        periodos: int = Field(default=1, ge=1, le=24)
        por_entidad: str | None = CampoColumna(default=None)

    PREFIJO = {"diferencia": "d", "porcentaje": "g", "log_diferencia": "dln"}

    def _nombres(self, params: BaseModel) -> list[tuple[str, str]]:
        p = self.PREFIJO[params.tipo]  # type: ignore[attr-defined]
        k = params.periodos            # type: ignore[attr-defined]
        suf = "" if k == 1 else str(k)
        return [(c, f"{p}{suf}_{c}") for c in params.columnas]  # type: ignore[attr-defined]

    def emit(self, ctx: Any) -> Any:
        ctx.importar("numpy", "np")
        tipo, k = ctx.p("tipo"), ctx.p("periodos")
        grupo = ctx.p("por_entidad")
        ctx.nota({
            "diferencia": f"Cambio absoluto contra {k} periodo(s) atras.",
            "porcentaje": f"Cambio porcentual contra {k} periodo(s) atras.",
            "log_diferencia": f"Log-diferencia contra {k} periodo(s) atras (crecimiento continuo).",
        }[tipo] + (f" Dentro de cada «{grupo}»." if grupo else ""))
        ctx.emitir("SAL = ENT.copy()", SAL=ctx.salida("datos"), ENT=ctx.entrada("datos"))
        for origen, nuevo in self._nombres(ctx.params):
            base = {"diferencia": "S[COL].diff(K)",
                    "porcentaje": "100 * S[COL].pct_change(K)",
                    "log_diferencia": "100 * (np.log(S[COL]) - np.log(S[COL].shift(K)))"}[tipo]
            if grupo:
                plantilla = f"SAL[NUEVO] = SAL.groupby(GRP, observed=True, group_keys=False).apply(lambda S: {base})"
                ctx.emitir(plantilla, SAL=ctx.ref_salida("datos"), NUEVO=ctx.lit(nuevo),
                           GRP=ctx.lit(grupo), COL=ctx.lit(origen), K=ctx.lit(k))
            else:
                ctx.emitir(f"SAL[NUEVO] = {base.replace('S[COL]', 'SAL[COL]')}",
                           SAL=ctx.ref_salida("datos"), NUEVO=ctx.lit(nuevo),
                           COL=ctx.lit(origen), K=ctx.lit(k))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        base = entradas.get("datos", Esquema())
        nuevas = [Columna(nombre=n, tipo="numerica",
                          es_estimado=base.hay_estimados([o])) for o, n in self._nombres(params)]
        return {"datos": base.con(*nuevas)}


@registrar
class Deflactar(EspecNodo):
    op = "transformar.deflactar"
    familia = "transformar"
    titulo = "Deflactar (pasar a precios constantes)"
    prefijo_var = "datos"
    ayuda = Ayuda(
        que_hace="Divide una variable nominal entre un indice de precios para dejarla en valores reales.",
        cuando_usarlo="Siempre que compares cantidades de dinero de anios distintos. Comparar pesos "
                      "corrientes de 2010 con los de 2025 no dice nada.",
        interpretacion="El resultado esta en pesos del periodo base que elijas. Si el valor real baja "
                       "mientras el nominal sube, el poder de compra cayo.",
        supuestos=["El indice de precios debe corresponder a la misma cobertura geografica y de canasta que la variable."],
        equivalente={"stata": "gen real = nominal / inpc * 100"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="datos", tipo="tabla")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        columnas: list[str] = CampoColumnas(tipo="numerica", default_factory=list)
        indice_precios: str = CampoColumna(tipo="numerica")
        base: float = Field(default=100.0, gt=0)

    def emit(self, ctx: Any) -> Any:
        idx = ctx.p("indice_precios")
        ctx.nota(f"Se divide entre «{idx}» y se multiplica por {ctx.p('base')}: "
                 f"el resultado queda en precios del periodo donde ese indice vale {ctx.p('base')}.")
        ctx.emitir("SAL = ENT.copy()", SAL=ctx.salida("datos"), ENT=ctx.entrada("datos"))
        for col in ctx.p("columnas"):
            ctx.emitir("SAL[NUEVO] = SAL[COL] / SAL[IDX] * BASE",
                       SAL=ctx.ref_salida("datos"), NUEVO=ctx.lit(f"real_{col}"),
                       COL=ctx.lit(col), IDX=ctx.lit(idx), BASE=ctx.plit("base"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        base = entradas.get("datos", Esquema())
        nuevas = [Columna(nombre=f"real_{c}", tipo="numerica",
                          es_estimado=base.hay_estimados([c, params.indice_precios]))  # type: ignore[attr-defined]
                  for c in params.columnas]  # type: ignore[attr-defined]
        return {"datos": base.con(*nuevas)}


@registrar
class Estandarizar(EspecNodo):
    op = "transformar.estandarizar"
    familia = "transformar"
    titulo = "Estandarizar variables"
    prefijo_var = "datos"
    ayuda = Ayuda(
        que_hace="Pone las variables en una escala comun: z (media 0, desviacion 1) o de 0 a 1.",
        cuando_usarlo="Para comparar coeficientes de variables medidas en unidades distintas, y porque "
                      "muchos metodos de machine learning lo necesitan.",
        interpretacion="Con z, un coeficiente dice cuanto cambia la dependiente si la explicativa sube "
                       "una desviacion estandar. Es la forma honesta de decir «cual pesa mas».",
        advertencias=["Si vas a partir en entrenamiento y prueba, estandariza DESPUES de partir, o el "
                      "conjunto de prueba se filtra en el de entrenamiento."],
        equivalente={"stata": "egen z = std(x)", "r": "scale()"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="datos", tipo="tabla")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        columnas: list[str] = CampoColumnas(tipo="numerica", default_factory=list)
        metodo: Literal["z", "min_max"] = "z"
        reemplazar: bool = False

    def _nombres(self, params: BaseModel) -> list[tuple[str, str]]:
        pre = "z" if params.metodo == "z" else "esc"  # type: ignore[attr-defined]
        return [(c, c if params.reemplazar else f"{pre}_{c}")  # type: ignore[attr-defined]
                for c in params.columnas]                       # type: ignore[attr-defined]

    def emit(self, ctx: Any) -> Any:
        metodo = ctx.p("metodo")
        ctx.nota("Media 0 y desviacion estandar 1." if metodo == "z"
                 else "Escalado al rango 0-1, con el minimo en 0 y el maximo en 1.")
        ctx.emitir("SAL = ENT.copy()", SAL=ctx.salida("datos"), ENT=ctx.entrada("datos"))
        plantilla = ("SAL[NUEVO] = (SAL[COL] - SAL[COL].mean()) / SAL[COL].std(ddof=0)" if metodo == "z"
                     else "SAL[NUEVO] = (SAL[COL] - SAL[COL].min()) / (SAL[COL].max() - SAL[COL].min())")
        for origen, nuevo in self._nombres(ctx.params):
            ctx.emitir(plantilla, SAL=ctx.ref_salida("datos"),
                       NUEVO=ctx.lit(nuevo), COL=ctx.lit(origen))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        base = entradas.get("datos", Esquema())
        nuevas = [Columna(nombre=n, tipo="numerica", es_estimado=base.hay_estimados([o]))
                  for o, n in self._nombres(params) if n != o]
        return {"datos": base.con(*nuevas)}


@registrar
class Indicadoras(EspecNodo):
    op = "transformar.dummies"
    familia = "transformar"
    titulo = "Crear indicadoras (dummies)"
    prefijo_var = "datos"
    ayuda = Ayuda(
        que_hace="Convierte una columna de categorias en varias columnas de ceros y unos.",
        cuando_usarlo="Cuando quieres meter una variable cualitativa (region, sector, tipo) en una regresion.",
        interpretacion="Cada coeficiente compara esa categoria contra la que se dejo fuera (la base). "
                       "No hay una categoria «neutral»: siempre se lee contra la base.",
        supuestos=["Hay que quitar una categoria, o el modelo cae en la trampa de las dummies "
                   "(colinealidad perfecta con la constante)."],
        equivalente={"stata": "i.region", "r": "factor()", "spss": "Recodificar en distintas variables"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="datos", tipo="tabla")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        columnas: list[str] = CampoColumnas(default_factory=list)
        quitar_primera: bool = True

    def emit(self, ctx: Any) -> Any:
        ctx.importar("pandas", "pd")
        ctx.nota("Se deja fuera una categoria como base." if ctx.p("quitar_primera")
                 else "ATENCION: al conservar todas las categorias, no metas tambien una constante en el modelo.")
        ctx.emitir("SAL = pd.get_dummies(ENT, columns=COLS, drop_first=PRIM, dtype=float)",
                   SAL=ctx.salida("datos"), ENT=ctx.entrada("datos"),
                   COLS=ctx.plit("columnas"), PRIM=ctx.plit("quitar_primera"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        # Los nombres dependen de los VALORES, que no se conocen sin ejecutar.
        # Se declara honestamente que el esquema cambia y no se inventan columnas.
        base = entradas.get("datos", Esquema())
        return {"datos": base.con(quitar=list(params.columnas))}  # type: ignore[attr-defined]


@registrar
class Winsorizar(EspecNodo):
    op = "transformar.winsorizar"
    familia = "transformar"
    titulo = "Recortar valores extremos"
    prefijo_var = "datos"
    ayuda = Ayuda(
        que_hace="Aplasta los valores mas altos y mas bajos hasta un percentil que tu elijas.",
        cuando_usarlo="Cuando unos pocos valores extremos dominan la estimacion, sobre todo en datos de "
                      "ingreso, riqueza o precios.",
        interpretacion="Compara el modelo con y sin recorte. Si los resultados cambian mucho, tu conclusion "
                       "descansaba en un punado de observaciones.",
        advertencias=["Recortar cambia los datos. Se reporta SIEMPRE en la nota metodologica, con el percentil usado.",
                      "Un valor extremo puede ser un error de captura o el dato mas informativo de la muestra. "
                      "Vale la pena mirarlo antes de aplastarlo."],
        equivalente={"stata": "winsor2", "r": "DescTools::Winsorize()"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="datos", tipo="tabla")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        columnas: list[str] = CampoColumnas(tipo="numerica", default_factory=list)
        percentil: float = Field(default=1.0, ge=0.1, le=25.0)

    def emit(self, ctx: Any) -> Any:
        p = ctx.p("percentil") / 100.0
        ctx.nota(f"Los valores por debajo del percentil {ctx.p('percentil')} y por encima del "
                 f"{100 - ctx.p('percentil')} se sustituyen por esos limites. Reportalo en tu metodologia.")
        ctx.emitir("SAL = ENT.copy()", SAL=ctx.salida("datos"), ENT=ctx.entrada("datos"))
        for col in ctx.p("columnas"):
            ctx.emitir("SAL[COL] = SAL[COL].clip(lower=SAL[COL].quantile(P), upper=SAL[COL].quantile(Q))",
                       SAL=ctx.ref_salida("datos"), COL=ctx.lit(col),
                       P=ctx.lit(round(p, 6)), Q=ctx.lit(round(1 - p, 6)))
        return ctx.fin()
