"""Econometria espacial: vecindad, autocorrelacion y modelos SAR/SEM.

La idea que organiza toda la familia: en economia urbana y regional, lo que pasa
en un lugar depende de lo que pasa al lado. Si eso es cierto y lo ignoras, MCO
da errores estandar demasiado chicos (y a veces coeficientes sesgados), y todo
parece mas significativo de lo que es.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...graph.spec import Columna, Esquema
from ...registry.base import (Ayuda, Ayudante, CampoColumna, CampoColumnas, EspecNodo,
                              Puerto, registrar, registrar_ayudante)

registrar_ayudante(Ayudante(
    nombre="construir_pesos",
    imports=[("numpy", "np")],
    fuente='''
def construir_pesos(datos, lat="lat", lng="lng", metodo="knn", k=5,
                    umbral_km=None, estandarizar="r"):
    """Matriz de pesos espaciales W a partir de coordenadas.

    W dice quien es vecino de quien y con cuanto peso. Es la decision mas
    importante de todo el analisis espacial y la que menos se justifica en los
    articulos publicados: los resultados dependen de ella, asi que conviene
    probar mas de una y reportar si la conclusion aguanta.

    metodo:
      knn       cada punto tiene exactamente k vecinos. Nunca deja islas.
      distancia todos los puntos dentro de un radio. Puede dejar islas.
      kernel    peso decreciente con la distancia, con ancho de banda adaptativo.

    estandarizar='r' hace que los pesos de cada fila sumen 1, que es lo que
    permite leer el rezago espacial como "el promedio de los vecinos".
    """
    from libpysal import weights

    coords = np.column_stack([datos[lat].to_numpy(float), datos[lng].to_numpy(float)])

    if metodo == "knn":
        w = weights.KNN(coords, k=int(k))
    elif metodo == "distancia":
        if umbral_km is None:
            umbral_km = weights.min_threshold_distance(coords) * 111.32
        w = weights.DistanceBand(coords, threshold=float(umbral_km) / 111.32, binary=True, silence_warnings=True)
    elif metodo == "kernel":
        w = weights.Kernel(coords, fixed=False, k=int(k), function="triangular")
    else:
        raise ValueError(f"Metodo de vecindad desconocido: {metodo}")

    if estandarizar:
        w.transform = estandarizar
    return w
''',
))

registrar_ayudante(Ayudante(
    nombre="resumen_pesos",
    imports=[("pandas", "pd"), ("numpy", "np")],
    fuente='''
def resumen_pesos(w):
    """Ficha de la matriz de pesos: es lo que hay que reportar en la metodologia."""
    cardinalidades = np.array(list(w.cardinalities.values()), dtype=float)
    n = w.n
    return pd.DataFrame([{
        "observaciones": n,
        "vecinos_promedio": float(cardinalidades.mean()),
        "vecinos_minimo": int(cardinalidades.min()),
        "vecinos_maximo": int(cardinalidades.max()),
        "islas": int(len(w.islands)),
        "densidad_pct": float(100.0 * cardinalidades.sum() / (n * (n - 1))) if n > 1 else 0.0,
        "transformacion": str(w.transform),
    }])
''',
))

registrar_ayudante(Ayudante(
    nombre="tabla_moran",
    imports=[("pandas", "pd")],
    fuente='''
def tabla_moran(datos, columnas, w, permutaciones=999):
    """I de Moran global para varias columnas, con su lectura en espanol."""
    from esda.moran import Moran

    filas = []
    for col in columnas:
        m = Moran(datos[col].to_numpy(float), w, permutations=int(permutaciones))
        if m.p_sim > 0.05:
            lectura = "Sin patron espacial detectable: la ubicacion no parece importar aqui."
        elif m.I > m.EI:
            lectura = "Los valores parecidos se agrupan: hay conglomerados espaciales."
        else:
            lectura = "Los valores se alternan con sus vecinos (patron de tablero de ajedrez)."
        filas.append({
            "variable": col, "I": float(m.I), "esperado_bajo_azar": float(m.EI),
            "desviacion_estandar": float(m.seI_sim), "z": float(m.z_sim),
            "p_valor": float(m.p_sim), "lectura": lectura,
        })
    return pd.DataFrame(filas)
''',
))

registrar_ayudante(Ayudante(
    nombre="tabla_lisa",
    imports=[("pandas", "pd"), ("numpy", "np")],
    fuente='''
def tabla_lisa(datos, columna, w, permutaciones=999, alpha=0.05):
    """Moran local (LISA): clasifica cada punto en su tipo de conglomerado.

    Alto-Alto  : valor alto rodeado de altos  -> nucleo caliente
    Bajo-Bajo  : valor bajo rodeado de bajos  -> nucleo frio
    Alto-Bajo  : valor alto rodeado de bajos  -> atipico (una isla cara)
    Bajo-Alto  : valor bajo rodeado de altos  -> atipico (rezago rodeado)

    Los p-valores son por permutacion y NO estan corregidos por multiplicidad:
    con 2,400 puntos, ~120 saldran significativos por puro azar al 5%. Para
    decisiones serias conviene bajar alpha o aplicar FDR.
    """
    from esda.moran import Moran_Local
    from libpysal.weights import lag_spatial

    y = datos[columna].to_numpy(float)
    lisa = Moran_Local(y, w, permutations=int(permutaciones))
    etiquetas = {0: "No significativo", 1: "Alto-Alto", 2: "Bajo-Alto", 3: "Bajo-Bajo", 4: "Alto-Bajo"}
    cuadrante = np.where(lisa.p_sim <= alpha, lisa.q, 0)
    salida = datos.copy()
    salida["lisa_i"] = lisa.Is
    salida["lisa_p"] = lisa.p_sim
    salida["lisa_tipo"] = [etiquetas[int(c)] for c in cuadrante]
    salida["rezago_espacial"] = lag_spatial(w, y)
    return salida
''',
))


@registrar
class MatrizPesos(EspecNodo):
    op = "espacial.pesos"
    familia = "espacial"
    titulo = "Matriz de vecindad (W)"
    prefijo_var = "pesos"
    ayuda = Ayuda(
        que_hace="Define quien es vecino de quien y con cuanto peso. Es el punto de partida de todo el "
                 "analisis espacial.",
        cuando_usarlo="Antes de Moran, LISA o cualquier modelo SAR/SEM.",
        interpretacion="Con pesos estandarizados por fila, el «rezago espacial» de una variable es el "
                       "promedio de esa variable entre los vecinos de cada punto. Ese promedio es la "
                       "variable que entra en los modelos espaciales.",
        supuestos=["Vecinos mas cercanos (KNN) nunca deja puntos aislados, que es lo que suele romper "
                   "una estimacion espacial.",
                   "Por distancia es mas facil de justificar teoricamente, pero puede dejar islas."],
        advertencias=["W es la decision mas importante y la menos justificada del analisis espacial "
                      "publicado. Los resultados dependen de ella: prueba al menos dos y reporta si la "
                      "conclusion aguanta el cambio."],
        referencia="Anselin, «Spatial Econometrics: Methods and Models» (1988), cap. 3",
        equivalente={"stata": "spmatrix create knn", "r": "spdep::knearneigh()"},
    )
    entradas = [Puerto(nombre="datos", tipo="geotabla", descripcion="Pasa antes por «Definir ubicacion»")]
    salidas = [Puerto(nombre="pesos", tipo="pesos", titulo="Matriz W"),
               Puerto(nombre="resumen", tipo="tabla", titulo="Ficha de la matriz", requerido=False)]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        latitud: str = CampoColumna(default="lat")
        longitud: str = CampoColumna(default="lng")
        metodo: Literal["knn", "distancia", "kernel"] = "knn"
        k: int = Field(default=5, ge=1, le=50)
        umbral_km: float | None = Field(default=None, gt=0)
        estandarizar_filas: bool = True

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("construir_pesos")
        ctx.usar_ayudante("resumen_pesos")
        metodo = ctx.p("metodo")
        ctx.nota({
            "knn": f"Cada punto se conecta con sus {ctx.p('k')} vecinos mas cercanos.",
            "distancia": (f"Vecinos dentro de {ctx.p('umbral_km')} km."
                          if ctx.p("umbral_km") else
                          "Vecinos dentro del radio minimo que deja a todos con al menos un vecino."),
            "kernel": f"Peso triangular decreciente con la distancia, ancho adaptativo a {ctx.p('k')} vecinos.",
        }[metodo])
        if ctx.p("estandarizar_filas"):
            ctx.nota("Pesos estandarizados por fila: cada fila suma 1, y el rezago espacial se lee como "
                     "el promedio de los vecinos.")
        ctx.emitir("W = construir_pesos(ENT, lat=LAT, lng=LNG, metodo=MET, k=K, "
                   "umbral_km=UMB, estandarizar=EST)",
                   W=ctx.salida("pesos"), ENT=ctx.entrada("datos"),
                   LAT=ctx.plit("latitud"), LNG=ctx.plit("longitud"), MET=ctx.plit("metodo"),
                   K=ctx.plit("k"), UMB=ctx.plit("umbral_km"),
                   EST=ctx.lit("r" if ctx.p("estandarizar_filas") else None))
        ctx.emitir("RES = resumen_pesos(W)", RES=ctx.salida("resumen"), W=ctx.ref_salida("pesos"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"resumen": Esquema(columnas=[
            Columna(nombre="observaciones", tipo="numerica"),
            Columna(nombre="vecinos_promedio", tipo="numerica"),
            Columna(nombre="vecinos_minimo", tipo="numerica"),
            Columna(nombre="vecinos_maximo", tipo="numerica"),
            Columna(nombre="islas", tipo="numerica"), Columna(nombre="densidad_pct", tipo="numerica"),
            Columna(nombre="transformacion", tipo="texto")])}

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        from ...runtime.artefactos import tabla_a_json

        out: dict[str, Any] = {}
        if (r := salidas.get("resumen")) is not None:
            out["resumen"] = tabla_a_json(r, titulo="Ficha de la matriz de vecindad")
        if (w := salidas.get("pesos")) is not None:
            islas = len(getattr(w, "islands", []) or [])
            out["pesos"] = {"tipo": "detalle", "titulo": "Matriz W",
                            "datos": {"observaciones": getattr(w, "n", None),
                                      "islas": islas,
                                      "aviso": ("Hay puntos sin vecinos: los modelos espaciales van a "
                                                "fallar. Cambia a vecinos mas cercanos o sube el radio."
                                                if islas else "Ningun punto quedo aislado.")}}
        return out


@registrar
class MoranGlobal(EspecNodo):
    op = "espacial.moran"
    familia = "espacial"
    titulo = "Autocorrelacion espacial (I de Moran)"
    prefijo_var = "moran"
    terminal = True
    ayuda = Ayuda(
        que_hace="Mide si los valores parecidos tienden a estar cerca unos de otros.",
        cuando_usarlo="Es la primera pregunta del analisis espacial: ¿la ubicacion importa, si o no? "
                      "Tambien sobre los residuos de un MCO, para ver si te quedo estructura espacial sin modelar.",
        interpretacion="I cerca de +1: los valores altos se agrupan con altos y los bajos con bajos. "
                       "Cerca de 0: distribucion sin patron. Negativo: tablero de ajedrez, cada valor "
                       "rodeado de sus opuestos. El p-valor por permutacion dice si el patron se distingue del azar.",
        supuestos=["Depende por completo de la matriz W que elegiste."],
        advertencias=["Moran significativo en los residuos de un MCO significa que el modelo esta mal "
                      "especificado: los errores estandar estan mal y hay que pasar a un modelo espacial."],
        referencia="Moran (1950); Anselin (1995)",
        equivalente={"stata": "moran", "r": "spdep::moran.test()"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla"), Puerto(nombre="pesos", tipo="pesos")]
    salidas = [Puerto(nombre="resultado", tipo="tabla", titulo="I de Moran")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        columnas: list[str] = CampoColumnas(tipo="numerica", default_factory=list)
        permutaciones: int = Field(default=999, ge=99, le=9999)

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("tabla_moran")
        ctx.nota(f"I de Moran con {ctx.p('permutaciones')} permutaciones aleatorias como referencia: "
                 "el p-valor compara el patron observado contra reordenamientos al azar de los mismos datos.")
        ctx.emitir("SAL = tabla_moran(ENT, COLS, W, permutaciones=PERM)",
                   SAL=ctx.salida("resultado"), ENT=ctx.entrada("datos"), W=ctx.entrada("pesos"),
                   COLS=ctx.plit("columnas"), PERM=ctx.plit("permutaciones"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"resultado": Esquema(columnas=[
            Columna(nombre="variable", tipo="texto"), Columna(nombre="I", tipo="numerica"),
            Columna(nombre="esperado_bajo_azar", tipo="numerica"),
            Columna(nombre="desviacion_estandar", tipo="numerica"), Columna(nombre="z", tipo="numerica"),
            Columna(nombre="p_valor", tipo="numerica"), Columna(nombre="lectura", tipo="texto")])}


@registrar
class LISA(EspecNodo):
    op = "espacial.lisa"
    familia = "espacial"
    titulo = "Conglomerados locales (LISA)"
    prefijo_var = "lisa"
    ayuda = Ayuda(
        que_hace="Dice, punto por punto, si forma parte de un conglomerado de valores altos, de uno de "
                 "valores bajos, o si es una anomalia rodeada de lo contrario.",
        cuando_usarlo="Cuando Moran global dice que hay patron y ahora quieres saber DONDE esta.",
        interpretacion="Alto-Alto = nucleo caliente. Bajo-Bajo = nucleo frio. Alto-Bajo y Bajo-Alto son "
                       "atipicos: una zona cara rodeada de baratas, o al reves. En mercados inmobiliarios "
                       "los Bajo-Alto suelen ser justo las oportunidades.",
        advertencias=["Los p-valores no estan corregidos por comparaciones multiples: con 2,400 puntos, "
                      "unos 120 saldran «significativos» por azar al 5%. Para decisiones serias, baja alpha."],
        referencia="Anselin, «Local Indicators of Spatial Association» (1995)",
        equivalente={"r": "spdep::localmoran()", "stata": "lisa"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla"), Puerto(nombre="pesos", tipo="pesos")]
    salidas = [Puerto(nombre="datos", tipo="tabla", titulo="Tabla con la clasificacion")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        columna: str = CampoColumna(tipo="numerica")
        permutaciones: int = Field(default=999, ge=99, le=9999)
        alpha: float = Field(default=0.05, gt=0.0, lt=0.5)

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("tabla_lisa")
        ctx.nota(f"LISA sobre «{ctx.p('columna')}», significancia al {ctx.p('alpha'):g}.")
        ctx.emitir("SAL = tabla_lisa(ENT, COL, W, permutaciones=PERM, alpha=ALPHA)",
                   SAL=ctx.salida("datos"), ENT=ctx.entrada("datos"), W=ctx.entrada("pesos"),
                   COL=ctx.plit("columna"), PERM=ctx.plit("permutaciones"), ALPHA=ctx.plit("alpha"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        base = entradas.get("datos", Esquema())
        return {"datos": base.con(
            Columna(nombre="lisa_i", tipo="numerica", es_estimado=True),
            Columna(nombre="lisa_p", tipo="numerica", es_estimado=True),
            Columna(nombre="lisa_tipo", tipo="categorica", es_estimado=True),
            Columna(nombre="rezago_espacial", tipo="numerica", es_estimado=True))}
