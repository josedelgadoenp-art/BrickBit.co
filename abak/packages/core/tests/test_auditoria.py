"""Auditoria: TODA herramienta del registro se ejecuta al menos una vez.

Habia 67 herramientas y 20 de ellas no aparecian en ninguna prueba ni en ningun
ejemplo: nunca se habian ejecutado. Un `emit()` que compila no prueba nada — el
codigo que genera puede reventar en la primera fila de datos reales, y hasta que
alguien lo pusiera en un lienzo nadie se enteraba.

Esta prueba cierra esa puerta de dos maneras:

  · `FLUJOS_AUDITORIA` ejercita las que faltaban, con datos de verdad.
  · `test_ninguna_herramienta_queda_sin_ejecutar` compara el registro con lo que
    de verdad corrio, asi que una herramienta NUEVA sin cobertura falla aqui el
    dia que se agrega, no meses despues.
"""

import pytest

from abak_core import compilar, ejecutar
from abak_core.registry import REGISTRO

from .conftest import grafo
from .test_nodos import FLUJOS, SECTORES

pytest.importorskip("statsmodels")

ESTADOS = ("d", "datos.ejemplo", "Entidades", {"conjunto": "mexico_estados"})
HOGARES = ("d", "datos.ejemplo", "Hogares", {"conjunto": "hogares"})
MACRO = ("d", "datos.ejemplo", "Macro", {"conjunto": "mexico_macro"})
PANEL = ("d", "datos.ejemplo", "Panel", {"conjunto": "panel_estados"})

FLUJOS_AUDITORIA = {
    # --- Preparacion de datos: la familia entera estaba sin ejecutar ---------
    "preparar": (
        [ESTADOS,
         ("f", "datos.filtrar", "Filtrar",
          {"condiciones": [{"columna": "precio_m2", "operador": "mayor", "valor": "10000"}]}),
        ("o", "datos.ordenar", "Ordenar", {"por": ["precio_m2"], "descendente": True}),
         ("s", "datos.seleccionar", "Elegir",
          {"columnas": ["entidad", "precio_m2", "ciclo", "ingreso_hogar_mensual"],
           "modo": "conservar"}),
         ("g", "datos.agrupar", "Agrupar",
          {"por": ["ciclo"], "columnas": ["precio_m2"], "funcion": "mean"}),
         ("n", "datos.faltantes", "Faltantes", {"metodo": "mediana"}),
         ("r", "datos.remodelar", "A largo",
          {"direccion": "a_largo", "identificadores": ["entidad"],
           "columnas": ["precio_m2", "ingreso_hogar_mensual"]}),
         ("u", "datos.unir", "Unir",
          {"llave_izquierda": ["ciclo"], "llave_derecha": ["ciclo"], "tipo": "izquierda"})],
        [("d", "datos", "f", "datos"), ("f", "datos", "o", "datos"),
         ("o", "datos", "s", "datos"), ("s", "datos", "g", "datos"),
         ("s", "datos", "n", "datos"), ("n", "datos", "r", "datos"),
         ("s", "datos", "u", "izquierda"), ("g", "datos", "u", "derecha")],
    ),
    # --- Transformaciones ----------------------------------------------------
    "transformar": (
        [PANEL,
         ("z", "transformar.estandarizar", "Estandarizar",
          {"columnas": ["pib_per_capita"], "metodo": "z"}),
         ("w", "transformar.winsorizar", "Winsorizar",
          {"columnas": ["inversion_pc"], "percentil": 1.0}),
         ("l", "transformar.rezago", "Rezago",
          {"columnas": ["pib_per_capita"], "periodos": 1, "por_entidad": "entidad"}),
         ("i", "transformar.dummies", "Dummies",
          {"columnas": ["entidad"], "quitar_primera": True})],
        [("d", "datos", "z", "datos"), ("z", "datos", "w", "datos"),
         ("w", "datos", "l", "datos"), ("l", "datos", "i", "datos")],
    ),
    "deflactar": (
        [MACRO,
         ("f", "transformar.deflactar", "A precios constantes",
          {"columnas": ["pib_indice"], "indice_precios": "inflacion_anual", "base": 100.0})],
        [("d", "datos", "f", "datos")],
    ),
    # --- Econometria que faltaba --------------------------------------------
    "econometria_faltante": (
        [HOGARES,
         ("b", "econometria.eleccion_discreta", "Logit",
          {"y": "tiene_credito_hipotecario", "x": ["ingreso_mensual", "escolaridad_anios"],
           "familia": "logit", "errores": "HC1"}),
         ("p", "econometria.eleccion_discreta", "Probit",
          {"y": "tiene_credito_hipotecario", "x": ["ingreso_mensual"], "familia": "probit"}),
         ("q", "econometria.cuantilica", "Mediana condicional",
          {"y": "gasto_vivienda", "x": ["ingreso_mensual", "tamano_hogar"], "cuantil": 0.5}),
         ("v", "econometria.iv", "MC2E",
          {"y": "gasto_vivienda", "endogenas": ["ingreso_mensual"],
           "instrumentos": ["escolaridad_anios"], "exogenas": ["tamano_hogar"]})],
        [("d", "datos", "b", "datos"), ("d", "datos", "p", "datos"),
         ("d", "datos", "q", "datos"), ("d", "datos", "v", "datos")],
    ),
    # --- SEM espacial --------------------------------------------------------
    "sem": (
        [ESTADOS,
         ("t", "transformar.calcular", "Log precio",
          {"operacion": "log", "columna_a": "precio_m2"}),
         ("u", "datos.ubicacion", "Ubicadas", {"latitud": "lat", "longitud": "lng"}),
         ("w", "espacial.pesos", "Vecinos", {"metodo": "knn", "k": 4}),
         ("s", "espacial.sem", "SEM",
          {"y": "log_precio_m2", "x": ["escolaridad_anios", "empleo_formal_pct"]})],
        [("d", "datos", "t", "datos"), ("t", "datos", "u", "datos"),
         ("u", "datos", "w", "datos"), ("u", "datos", "s", "datos"),
         ("w", "pesos", "s", "pesos")],
    ),
    # --- Ciclo y crecimiento -------------------------------------------------
    "ciclo": (
        [MACRO,
         ("g", "transformar.crecimiento", "Crecimiento",
          {"columnas": ["pib_indice"], "tipo": "porcentaje", "periodos": 4}),
         ("s", "datos.serie_temporal", "Serie",
          {"columna_fecha": "fecha", "frecuencia": "QS"}),
         ("h", "series.ciclo", "Hodrick-Prescott",
          {"variable": "pib_indice", "metodo": "hp", "lamb": 1600.0}),
         ("m", "series.ciclo", "Hamilton",
          {"variable": "pib_indice", "metodo": "hamilton"})],
        [("d", "datos", "g", "datos"), ("g", "datos", "s", "datos"),
         ("s", "datos", "h", "datos"), ("s", "datos", "m", "datos")],
    ),
    # --- Validacion temporal -------------------------------------------------
    "validacion_temporal": (
        [MACRO,
         ("s", "datos.serie_temporal", "Serie",
          {"columna_fecha": "fecha", "frecuencia": "QS"}),
         ("v", "ml.validacion_temporal", "Origen movil",
          {"y": "pib_indice", "x": ["inflacion_anual", "tasa_objetivo"],
           "n_cortes": 3, "horizonte": 2, "n_arboles": 40})],
        [("d", "datos", "s", "datos"), ("s", "datos", "v", "datos")],
    ),
    # --- Capas de grafico que faltaban --------------------------------------
    "graficos_faltantes": (
        [ESTADOS,
         ("c", "graficos.lienzo", "Lienzo",
          {"x": "escolaridad_anios", "y": "precio_m2", "color": "ciclo"}),
         ("p", "graficos.puntos", "+ Puntos", {}),
         ("r", "graficos.referencia", "+ Referencia", {"eje": "y", "valor": 15000.0}),
         ("e", "graficos.escala", "+ Escala", {"eje": "y", "tipo": "log"}),
         ("f", "graficos.facetas", "+ Facetas", {"por": "ciclo"}),
         ("t", "graficos.tema", "Títulos", {"titulo": "Auditoría", "modo": "oscuro"}),
         ("z", "graficos.dibujar", "Dibujar", {})],
        [("d", "datos", "c", "datos"), ("c", "grafico", "p", "grafico"),
         ("p", "grafico", "r", "grafico"), ("r", "grafico", "e", "grafico"),
         ("e", "grafico", "f", "grafico"), ("f", "grafico", "t", "grafico"),
         ("t", "grafico", "z", "grafico")],
    ),
}


@pytest.mark.parametrize("nombre", list(FLUJOS_AUDITORIA))
def test_el_flujo_de_auditoria_corre_sin_errores(nombre):
    nodos, aristas = FLUJOS_AUDITORIA[nombre]
    resultado = ejecutar(compilar(grafo(nombre, nodos, aristas)))

    # Lo PRIMERO es que haya corrido algo. Un parametro invalido detiene la
    # compilacion entera y `resultado.nodos` llega vacio; sin esta linea, las
    # dos aserciones de abajo se cumplen sobre una lista vacia y el flujo pasa
    # en verde sin haber ejecutado una sola herramienta. Paso de verdad, con
    # dos de estos flujos, y es exactamente el tipo de agujero que esta
    # auditoria existe para cerrar.
    assert resultado.ok and len(resultado.nodos) == len(nodos), (
        f"corrieron {len(resultado.nodos)} de {len(nodos)} bloques. "
        f"Bitacora: {resultado.bitacora[-2:]}")

    fallidos = {n.nodo_id: n.error for n in resultado.nodos if n.error}
    assert not fallidos, "\n".join(
        f"{k}: {getattr(v, 'titulo', '')} — {getattr(v, 'detalle', '')}"
        for k, v in fallidos.items())
    omitidos = [n.nodo_id for n in resultado.nodos if n.estado == "omitido"]
    assert not omitidos, f"se omitieron por depender de un fallo: {omitidos}"


@pytest.mark.parametrize("nombre", list(FLUJOS_AUDITORIA))
def test_los_artefactos_de_auditoria_son_json_estricto(nombre):
    import json

    nodos, aristas = FLUJOS_AUDITORIA[nombre]
    resultado = ejecutar(compilar(grafo(nombre, nodos, aristas)))
    for n in resultado.nodos:
        json.dumps(n.artefactos or {}, allow_nan=False)


def _ops_ejercitadas() -> set[str]:
    ops = set()
    for nodos, _ in list(FLUJOS.values()) + list(FLUJOS_AUDITORIA.values()):
        ops.update(op for _, op, _, _ in nodos)
    # Las que viven en sus propias pruebas, fuera de los flujos parametrizados.
    ops.update({
        "econometria.mco", "econometria.diagnosticos", "econometria.colinealidad",
        "escenarios.simular", "causal.efecto", "inmobiliario.indice_hedonico",
        "datos.muestra", "datos.csv", "salida.tabla_publicacion", "salida.exportar",
        "graficos.linea", "graficos.barras", "graficos.area", "graficos.banda",
        "graficos.tendencia", "macro.multiplicador_keynesiano",
    })
    return ops


# Estas no se pueden ejecutar en una prueba y se dice por que, una por una.
# La lista es corta a proposito: cada nombre aqui es una herramienta que nadie
# esta probando, y tiene que doler agregarle uno.
SIN_EJECUTAR = {
    "fuentes.banxico": "pega la API del SIE de Banxico; se prueba con su cache y su doble",
    "fuentes.inegi": "pega la API del INEGI (BIE/BISE); igual que arriba",
    "fuentes.denue": "el INEGI bloquea IPs de nube; no se puede ejercitar en una corrida",
}


def test_ninguna_herramienta_queda_sin_ejecutar():
    """El registro completo, contra lo que de verdad corre.

    Falla el dia que se agrega una herramienta nueva sin cobertura, que es el
    dia en que hay que enterarse.
    """
    ejercitadas = _ops_ejercitadas()
    huerfanas = sorted(set(REGISTRO) - ejercitadas - set(SIN_EJECUTAR))
    assert not huerfanas, (
        "estas herramientas no las ejecuta ninguna prueba:\n  "
        + "\n  ".join(f"{op} — {REGISTRO[op].titulo}" for op in huerfanas))


def test_las_excusas_siguen_siendo_ciertas():
    """Ninguna herramienta de `SIN_EJECUTAR` puede haber desaparecido o cambiado."""
    for op in SIN_EJECUTAR:
        assert op in REGISTRO, f"«{op}» ya no existe: quita su excusa de SIN_EJECUTAR"


def test_hay_sectores_para_los_flujos_de_insumo_producto():
    assert len(SECTORES) == 12


# ---------------------------------------------------------------------------
# Glosario: nada que Abak nombre puede quedarse sin explicacion
# ---------------------------------------------------------------------------

def _normalizar(clave: str) -> str:
    """La MISMA normalizacion del frontend (`store/lienzo.ts`).

    Si estas dos se separan, el glosario se ve completo aqui y vacio alla.
    """
    import re
    import unicodedata

    s = unicodedata.normalize("NFKD", clave)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("²", "2").lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


# Rotulos que describen la ESTRUCTURA de un resultado, no un indicador: no hay
# nada que explicar en «filas» o «eje horizontal», y el boton correctamente no
# aparece. Todo lo demas que Abak nombre tiene que traer su ficha.
SIN_FICHA_A_PROPOSITO = {
    "aviso", "capas_apiladas", "eje_horizontal", "eje_vertical", "falta", "filas",
    "facetas_por", "una_serie_por", "entidades", "conclusion", "conjunto", "causa",
    "variable", "prueba", "lectura", "metodo", "titulo", "periodo",
}


def test_todo_indicador_en_pantalla_tiene_su_ficha():
    """De todo lo que el motor nombra, ¿que queda sin explicar?

    La prueba de navegador comprueba que las fichas que HAY se vean bien. Esta
    hace la pregunta contraria, que es la que importa: un R² sin ficha no rompe
    nada, sólo deja a la persona sola justo donde le prometimos compañia.

    Se miran los artefactos que ABAK bautiza (diagnosticos de un modelo, campos
    de un detalle, titulos de un escalar). Las columnas de una tabla son nombres
    de datos del usuario —«entidad», «precio_m2»— y ahi no toca ficha.
    """
    from abak_core.registry.glosario import GLOSARIO

    fichas = {_normalizar(k) for k in GLOSARIO}
    huecos: dict[str, str] = {}
    for nombre, (nodos, aristas) in {**FLUJOS, **FLUJOS_AUDITORIA}.items():
        resultado = ejecutar(compilar(grafo(nombre, nodos, aristas)))
        for n in resultado.nodos:
            for art in (n.artefactos or {}).values():
                claves: list[str] = []
                if art.get("tipo") == "modelo":
                    claves += list(art.get("diagnosticos") or {})
                elif art.get("tipo") == "detalle":
                    claves += list(art.get("datos") or {})
                elif art.get("tipo") == "escalar":
                    claves.append(art.get("titulo") or "")
                for c in claves:
                    clave = _normalizar(c)
                    if clave and clave not in fichas and clave not in SIN_FICHA_A_PROPOSITO:
                        huecos.setdefault(c, f"{nombre}/{n.nodo_id}")
    assert not huecos, "estos indicadores salen en pantalla sin ficha:\n  " + "\n  ".join(
        f"{c!r} (en {donde})" for c, donde in sorted(huecos.items()))


def test_las_excepciones_del_glosario_no_tapan_indicadores_de_verdad():
    """Ninguna excepcion puede coincidir con una ficha que si existe.

    Si alguien agrega la ficha de algo que estaba en la lista de excepciones, la
    excepcion sobra y hay que quitarla; si no, la lista crece hasta volverse el
    lugar donde se esconden los huecos.
    """
    from abak_core.registry.glosario import GLOSARIO

    fichas = {_normalizar(k) for k in GLOSARIO}
    sobran = sorted(SIN_FICHA_A_PROPOSITO & fichas)
    assert not sobran, f"estas excepciones ya tienen ficha, quitalas de la lista: {sobran}"


# ---------------------------------------------------------------------------
# Controles: ningun parametro puede caer en un control que no lo pueda capturar
# ---------------------------------------------------------------------------

# El formulario se genera del JSON Schema. Para un `list[str]` cae bien en una
# caja separada por comas; para un `list[objeto]` esa caja es papel mojado —
# nadie va a escribir ahi «columna, operador, valor». Le paso a «Filtrar filas»,
# que es de lo primero que alguien quiere hacer y no se podia usar.
CONTROLES_CONOCIDOS = {"columna", "columnas", "opcion", "archivo", "mapa_sectores",
                       "claves", "arcos", "condiciones"}

# `datos.csv/columnas` no lleva pista de control porque el formulario lo trata
# aparte: no es un campo que se llene, es el esquema del archivo que se subio, y
# se ensena como resumen de solo lectura.
CONTROL_APARTE = {("datos.csv", "columnas")}


def test_ningun_parametro_cae_en_un_control_que_no_le_sirve():
    from abak_core.registry import catalogo

    sospechosos = []
    for n in catalogo()["nodos"]:
        esquema = n.get("params_schema") or {}
        for clave, campo in (esquema.get("properties") or {}).items():
            if (n["op"], clave) in CONTROL_APARTE:
                continue
            if ((campo.get("abak") or {}).get("control")) in CONTROLES_CONOCIDOS:
                continue
            items = campo.get("items") or {}
            anidado = bool(items.get("$ref") or campo.get("$ref")) or items.get("type") == "object"
            if campo.get("type") == "array" and anidado:
                sospechosos.append(f"{n['op']}.{clave}: lista de objetos sin control propio")
            elif campo.get("type") == "object" and not campo.get("additionalProperties"):
                sospechosos.append(f"{n['op']}.{clave}: objeto sin control propio")
    assert not sospechosos, "\n  ".join(["estos parámetros no se pueden llenar:"] + sospechosos)


def test_filtrar_convierte_el_valor_al_tipo_de_su_columna():
    """Una caja de texto entrega texto; la columna es numerica. Se convierte.

    `columna_int64 > "10000"` revienta en pandas con «Invalid comparison between
    dtype=int64 and str», y es el filtro mas comun que existe.
    """
    nodos = [ESTADOS,
             ("f", "datos.filtrar", "Caras",
              {"condiciones": [{"columna": "precio_m2", "operador": "mayor",
                                "valor": "15,000"}]})]
    r = ejecutar(compilar(grafo("filtro", nodos, [("d", "datos", "f", "datos")])))
    assert r.ok, r.bitacora[-2:]
    tabla = {n.nodo_id: n for n in r.nodos}["f"].artefactos["datos"]
    assert tabla["n_filas"] > 0, "el filtro no dejó ninguna fila"
    columnas = [c["nombre"] for c in tabla["columnas"]]
    i = columnas.index("precio_m2")
    assert all(float(f[i]) > 15000 for f in tabla["filas"]), "pasaron filas que no cumplen"

    # Y el literal que va al script tiene que ser un NUMERO, no una cadena.
    from abak_core import a_texto, emitir

    texto = a_texto(emitir(compilar(grafo("filtro", nodos, [("d", "datos", "f", "datos")]))))
    assert "> 15000" in texto, f"el valor no salió tipado:\n{texto}"


def test_agrupar_emite_y_corre():
    """`.agg('mean')` y no `.FN()`: el emisor sólo sustituye NOMBRES.

    Este bloque reventaba al compilar con «la plantilla no usa los huecos
    ['FN']» y nunca habia corrido en ninguna prueba ni ejemplo.
    """
    for funcion in ("mean", "sum", "median", "min", "max", "std", "count"):
        con_columnas = [ESTADOS,
                        ("g", "datos.agrupar", "Agrupar",
                         {"por": ["ciclo"], "columnas": ["precio_m2"], "funcion": funcion})]
        sin_columnas = [ESTADOS,
                        ("g", "datos.agrupar", "Agrupar",
                         {"por": ["ciclo"], "columnas": [], "funcion": funcion})]
        for nodos in (con_columnas, sin_columnas):
            r = ejecutar(compilar(grafo(f"agrupar-{funcion}", nodos,
                                        [("d", "datos", "g", "datos")])))
            assert r.ok, f"«{funcion}»: {r.bitacora[-2:]}"
            tabla = {n.nodo_id: n for n in r.nodos}["g"].artefactos["datos"]
            assert tabla["n_filas"] > 0, f"«{funcion}» no devolvió filas"


# ---------------------------------------------------------------------------
# La semilla tiene que MANDAR
# ---------------------------------------------------------------------------

def test_la_semilla_del_grafo_llega_al_codigo():
    """«Con la misma semilla el resultado se repite» exige que la semilla exista.

    Estaba escrita a mano como 42 en los nodos que sortean algo, asi que mover
    el control de la barra no cambiaba nada: la promesa se cumplia porque el
    numero nunca cambiaba. Y el unico nodo que sí pedia `ctx.semilla` reventaba
    al compilar, porque el contexto de emision no la tenia.
    """
    from abak_core import a_texto, emitir

    nodos = [("d", "datos.ejemplo", "Hogares", {"conjunto": "hogares"}),
             ("s", "datos.muestra", "Muestra", {"n": 500, "metodo": "aleatorio"}),
             ("p", "ml.particion", "Partición", {"proporcion_prueba": 0.2, "aleatoria": True}),
             ("x", "ml.xgboost", "XGBoost",
              {"y": "gasto_vivienda", "x": ["ingreso_mensual"], "n_arboles": 20})]
    aristas = [("d", "datos", "s", "datos"), ("s", "datos", "p", "datos"),
               ("p", "entrenamiento", "x", "entrenamiento"), ("p", "prueba", "x", "prueba")]

    for semilla in (7, 1234):
        texto = a_texto(emitir(compilar(grafo("semillas", nodos, aristas, semilla=semilla))))
        assert f"semilla={semilla}" in texto or f"{semilla}" in texto, (
            f"la semilla {semilla} no aparece en el script")
        assert "random_state=42" not in texto, "quedó una semilla escrita a mano"


def test_cambiar_la_semilla_cambia_la_muestra():
    """Y no basta con que aparezca: tiene que cambiar el resultado."""
    nodos = [("d", "datos.ejemplo", "Hogares", {"conjunto": "hogares"}),
             ("s", "datos.muestra", "Muestra", {"n": 300, "metodo": "aleatorio"})]
    aristas = [("d", "datos", "s", "datos")]

    def medias(semilla):
        r = ejecutar(compilar(grafo("muestra", nodos, aristas, semilla=semilla)))
        assert r.ok, r.bitacora[-2:]
        precision = {n.nodo_id: n for n in r.nodos}["s"].artefactos["precision"]
        columnas = [c["nombre"] for c in precision["columnas"]]
        i = columnas.index("media_en_muestra")
        return [f[i] for f in precision["filas"]]

    assert medias(7) != medias(1234), "dos semillas distintas dieron la misma muestra"


def test_la_misma_semilla_da_la_misma_muestra():
    nodos = [("d", "datos.ejemplo", "Hogares", {"conjunto": "hogares"}),
             ("s", "datos.muestra", "Muestra", {"n": 300, "metodo": "aleatorio"})]
    aristas = [("d", "datos", "s", "datos")]
    corridas = []
    for _ in range(2):
        r = ejecutar(compilar(grafo("muestra", nodos, aristas, semilla=99)))
        precision = {n.nodo_id: n for n in r.nodos}["s"].artefactos["precision"]
        corridas.append(precision["filas"])
    assert corridas[0] == corridas[1], "la misma semilla dio resultados distintos"
