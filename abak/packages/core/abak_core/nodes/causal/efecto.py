"""Inferencia causal: declarar el grafo y dejar que decida los controles.

La pregunta «¿que variables meto de control?» no la contesta ningun programa
estadistico. R, Stata, EViews y SPSS obedecen: meten lo que les pidas. Y meter
de mas es tan grave como meter de menos — un mediador borra el efecto, un
colisionador inventa uno — sin que el R², el p-valor ni ningun diagnostico se
enteren.

Aqui el lienzo YA es un grafo dirigido, asi que declarar quien causa a quien es
el gesto natural de la casa. Con eso, el criterio de puerta trasera decide.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...graph.spec import Columna, Esquema
from ...registry.base import (Ayuda, Ayudante, CampoColumna, EspecNodo, Puerto,
                              control, registrar, registrar_ayudante)

registrar_ayudante(Ayudante(
    nombre="puerta_trasera",
    imports=[],
    fuente='''
def puerta_trasera(arcos, tratamiento, resultado, disponibles):
    """Criterio de puerta trasera de Pearl: que controlar y por que.

    Devuelve (ajuste, papeles). `ajuste` es None cuando NO se puede identificar
    el efecto con las columnas que hay: eso no es un fallo del programa, es la
    respuesta, y ninguna regresion la arregla.
    """
    padres, hijos, variables = {}, {}, set()
    for causa, efecto in arcos:
        variables.add(causa); variables.add(efecto)
        padres.setdefault(efecto, set()).add(causa)
        hijos.setdefault(causa, set()).add(efecto)
    padres = {v: padres.get(v, set()) for v in variables}
    hijos = {v: hijos.get(v, set()) for v in variables}

    def alcanzar(v, vecinos, evitar=None):
        vistos, pila = set(), [v]
        while pila:
            for w in vecinos[pila.pop()]:
                if w != evitar and w not in vistos:
                    vistos.add(w); pila.append(w)
        return vistos

    def caminos(a, b):
        salida = []
        def andar(actual, camino, vistos):
            if actual == b:
                salida.append(camino); return
            for vecino in sorted(padres[actual] | hijos[actual]):
                if vecino not in vistos:
                    andar(vecino, camino + [vecino], vistos | {vecino})
        andar(a, [a], {a})
        return salida

    def colisiona(camino, i):
        v = camino[i]
        return camino[i - 1] in padres[v] and camino[i + 1] in padres[v]

    def cerrado(camino, z):
        for i in range(1, len(camino) - 1):
            v = camino[i]
            if colisiona(camino, i):
                # Un colisionador libre cierra el camino; controlarlo lo ABRE.
                if v not in z and not (alcanzar(v, hijos) & z):
                    return True
            elif v in z:
                return True
        return False

    traseros = [c for c in caminos(tratamiento, resultado)
                if len(c) > 1 and c[1] in padres[tratamiento]]
    desc_t = alcanzar(tratamiento, hijos)

    def sirve(z):
        if z & desc_t or tratamiento in z or resultado in z:
            return False
        return all(cerrado(c, z) for c in traseros)

    candidatas = (variables - {tratamiento, resultado} - desc_t) & set(disponibles)
    ajuste = None
    if sirve(candidatas):
        ajuste = set(candidatas)
        for v in sorted(candidatas):          # minimizar, en orden estable
            if sirve(ajuste - {v}):
                ajuste.discard(v)

    anc_t = alcanzar(tratamiento, padres)
    anc_y_alterno = alcanzar(resultado, padres, evitar=tratamiento)
    anc_y = alcanzar(resultado, padres)
    colisionadores = {c[i] for c in traseros for i in range(1, len(c) - 1) if colisiona(c, i)}

    papeles = {}
    for v in sorted(variables - {tratamiento, resultado}):
        if v in desc_t:
            papeles[v] = "mediador" if v in anc_y else "descendiente"
        elif ajuste and v in ajuste:
            papeles[v] = "confusor"
        elif v in colisionadores:
            papeles[v] = "colisionador"
        elif v in anc_t and v in anc_y_alterno:
            papeles[v] = "confusor"
        elif v in anc_y_alterno:
            papeles[v] = "predictor"
        elif v in anc_t:
            papeles[v] = "causa_del_tratamiento"
        else:
            papeles[v] = "irrelevante"
    return ajuste, papeles
''',
))

registrar_ayudante(Ayudante(
    nombre="tabla_controles",
    imports=[("pandas", "pd")],
    depende_de=["puerta_trasera"],
    fuente='''
CONSEJO_CAUSAL = {
    "confusor": ("Incluida", "Causa al tratamiento y al resultado. Sin ella, su efecto se cuela "
                             "en el coeficiente que te interesa."),
    "mediador": ("Fuera", "El tratamiento la afecta y ella afecta al resultado. Controlarla te "
                          "quita justo la parte del efecto que querias medir."),
    "colisionador": ("Fuera", "Es un efecto comun. Controlarla ABRE un camino cerrado e inventa "
                              "una correlacion que no existe."),
    "descendiente": ("Fuera", "Ocurre despues del tratamiento y depende de el."),
    "predictor": ("Opcional", "Explica al resultado, no al tratamiento. No sesga; suele apretar "
                              "los intervalos."),
    "causa_del_tratamiento": ("Opcional", "Explica al tratamiento, no al resultado. No sesga, "
                                          "pero ensancha los intervalos."),
    "irrelevante": ("Fuera", "Segun tu grafo no conecta con esta pregunta."),
}


def tabla_controles(papeles, ajuste):
    """Una fila por variable: que es, que se hizo con ella y por que."""
    filas = []
    for variable, papel in sorted(papeles.items()):
        decision, motivo = CONSEJO_CAUSAL[papel]
        filas.append({
            "variable": variable,
            "papel": papel.replace("_", " "),
            "decision": "Incluida" if (ajuste and variable in ajuste) else decision,
            "por_que": motivo,
        })
    return pd.DataFrame(filas)
''',
))


@registrar
class EfectoCausal(EspecNodo):
    op = "causal.efecto"
    version = "1.0.0"
    familia = "causal"
    titulo = "Efecto causal (puerta trasera)"
    prefijo_var = "causal"
    terminal = True
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [
        Puerto(nombre="modelo", tipo="modelo", titulo="Efecto estimado"),
        Puerto(nombre="controles", tipo="tabla", titulo="Que se controlo y por que"),
    ]
    ayuda = Ayuda(
        que_hace="Dibujas que causa que, y Abak decide que variables hay que controlar para medir "
                 "el efecto de una sobre otra. Despues estima la regresion con exactamente esos "
                 "controles, ni uno mas ni uno menos.",
        cuando_usarlo="Cuando la pregunta es CAUSAL y no descriptiva: «¿el metro subio los precios?», "
                      "«¿la remodelacion aumento la renta?». Si solo quieres describir o predecir, "
                      "usa MCO o XGBoost.",
        interpretacion="El coeficiente del tratamiento es el efecto causal SI el grafo que dibujaste "
                       "es correcto. La tabla de controles dice que entro, que se quedo fuera y por "
                       "que; leerla es la mitad del valor de esta herramienta.",
        supuestos=["El grafo lo pones tu y no se puede verificar con los datos: es un argumento, "
                   "no un resultado",
                   "No hay confusion por variables que no dibujaste u observaste",
                   "El efecto es lineal en los parametros (lo estima MCO)"],
        advertencias=["Meter todas las variables «por si acaso» es un error, no una precaucion: un "
                      "mediador borra el efecto y un colisionador lo inventa. Esta herramienta existe "
                      "justo para no hacer eso.",
                      "Si dice que el efecto NO se puede identificar, ninguna regresion lo arregla. "
                      "Hace falta otro dato o otro diseno."],
        referencia="Pearl, «Causality» (2009), cap. 3. Version corta: Cunningham, «The Mixtape», cap. 3",
        equivalente={"r": "dagitty::adjustmentSets() + lm()", "stata": "dagitty (fuera de Stata)",
                     "eviews": "—", "spss": "—"},
    )

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        arcos: list[str] = Field(
            default_factory=list,
            json_schema_extra=control("arcos"),
            description="Las flechas del grafo, como «causa->efecto».")
        tratamiento: str = CampoColumna(descripcion="La causa cuyo efecto quieres medir.")
        resultado: str = CampoColumna(tipo="numerica", descripcion="Lo que quieres explicar.")
        errores: Literal["clasicos", "HC1", "HC3"] = "HC1"

    def columnas_requeridas(self, params: BaseModel) -> set[str] | None:
        usadas = {params.tratamiento, params.resultado}
        for arco in params.arcos:
            if "->" in arco:
                causa, efecto = arco.split("->", 1)
                usadas.add(causa.strip())
                usadas.add(efecto.strip())
        return {c for c in usadas if c}

    def emit(self, ctx: Any) -> None:
        ctx.importar("statsmodels.api", "sm")
        ctx.importar("pandas", "pd")
        ctx.usar_ayudante("puerta_trasera")
        ctx.usar_ayudante("tabla_controles")

        pares = []
        for arco in ctx.p("arcos"):
            if "->" in arco:
                causa, efecto = arco.split("->", 1)
                if causa.strip() and efecto.strip():
                    pares.append([causa.strip(), efecto.strip()])

        ajuste = ctx.temporal("ajuste")
        papeles = ctx.temporal("papeles")
        listos = ctx.temporal("controles_usados")
        X = ctx.temporal("X")

        ctx.nota("El criterio de puerta trasera decide los controles a partir del grafo causal.")
        ctx.emitir("AJU, PAP = puerta_trasera(ARCOS, TRAT, RES, list(ENT.columns))",
                   AJU=ajuste, PAP=papeles, ARCOS=ctx.lit(pares),
                   TRAT=ctx.plit("tratamiento"), RES=ctx.plit("resultado"),
                   ENT=ctx.entrada("datos"))
        ctx.emitir(
            "if AJU is None:\n"
            "    raise ValueError(\n"
            "        'Con las columnas que hay, el efecto no se puede identificar: queda '\n"
            "        'confusion abierta que ninguna regresion cierra. Hace falta observar otra '\n"
            "        'variable o usar otro diseno (variables instrumentales, diferencias en '\n"
            "        'diferencias, discontinuidad).')",
            AJU=ajuste)
        ctx.emitir("USADOS = sorted(AJU)", USADOS=listos, AJU=ajuste)
        ctx.emitir("X = sm.add_constant(ENT[[TRAT] + USADOS], has_constant='add')",
                   X=X, ENT=ctx.entrada("datos"), TRAT=ctx.plit("tratamiento"), USADOS=listos)
        ctx.emitir("MOD = sm.OLS(ENT[RES], X, missing='drop').fit(cov_type=TIPO)",
                   MOD=ctx.salida("modelo"), ENT=ctx.entrada("datos"),
                   RES=ctx.plit("resultado"), X=X, TIPO=ctx.lit(ctx.p("errores")))
        ctx.emitir("CTRL = tabla_controles(PAP, AJU)",
                   CTRL=ctx.salida("controles"), PAP=papeles, AJU=ajuste)

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"controles": Esquema(columnas=[
            Columna(nombre="variable", tipo="texto"),
            Columna(nombre="papel", tipo="texto"),
            Columna(nombre="decision", tipo="texto"),
            Columna(nombre="por_que", tipo="texto"),
        ])}

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        from ...runtime.artefactos import modelo_a_json, tabla_a_json

        salida: dict[str, Any] = {}
        if (mod := salidas.get("modelo")) is not None:
            salida["modelo"] = modelo_a_json(mod, titulo=f"Efecto de «{params.tratamiento}»")
        if (ctrl := salidas.get("controles")) is not None:
            salida["controles"] = tabla_a_json(ctrl, titulo="Que se controlo y por que")
        return salida
