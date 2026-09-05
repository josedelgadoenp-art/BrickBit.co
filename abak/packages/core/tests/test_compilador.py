"""El compilador: tipos, ciclos, poda, nombres y propagación de esquema."""

import pytest

from abak_core import a_texto, compilar, ejecutar, emitir
from abak_core.graph.compilador import identificador
from abak_core.graph.tipos import acepta

from .conftest import grafo


def codigos(programa):
    return {d.codigo for d in programa.diagnosticos if d.severidad == "error"}


# --- tipos de puerto --------------------------------------------------------

def test_subsuncion_de_tipos():
    """Una serie ES una tabla; una tabla NO es una serie."""
    assert acepta("tabla", "serie")
    assert acepta("tabla", "panel")
    assert acepta("cualquiera", "modelo")
    assert not acepta("serie", "tabla")
    assert not acepta("pesos", "tabla")


def test_conexion_de_tipos_incompatibles_se_rechaza():
    """Una tabla cruda a un VAR: el error apunta al nodo que falta en medio."""
    g = grafo("tipos", [
        ("d", "datos.ejemplo", "Datos", {"conjunto": "mexico_macro"}),
        ("v", "series.var", "VAR", {"variables": ["pib_indice"]}),
    ], [("d", "datos", "v", "datos")])
    p = compilar(g)
    assert "tipos_incompatibles" in codigos(p)
    mensaje = next(d.mensaje for d in p.diagnosticos if d.codigo == "tipos_incompatibles")
    assert "Definir serie temporal" in mensaje


def test_promocion_a_serie_desbloquea_la_conexion():
    g = grafo("promocion", [
        ("d", "datos.ejemplo", "Datos", {"conjunto": "mexico_macro"}),
        ("s", "datos.serie_temporal", "Serie", {"columna_fecha": "fecha", "frecuencia": "QS"}),
        ("v", "series.var", "VAR", {"variables": ["pib_indice", "inflacion_anual"]}),
    ], [("d", "datos", "s", "datos"), ("s", "datos", "v", "datos")])
    assert not compilar(g).hay_errores


# --- estructura del grafo ---------------------------------------------------

def test_ciclo_se_detecta_y_se_nombra_completo():
    g = grafo("ciclo", [
        ("a", "transformar.calcular", "A", {"operacion": "log", "columna_a": "x"}),
        ("b", "transformar.calcular", "B", {"operacion": "log", "columna_a": "x"}),
    ], [("a", "datos", "b", "datos"), ("b", "datos", "a", "datos")])
    p = compilar(g)
    assert "ciclo" in codigos(p)
    mensaje = next(d.mensaje for d in p.diagnosticos if d.codigo == "ciclo")
    assert "→" in mensaje, "el error debe mostrar el ciclo, no sólo decir que existe"


def test_entrada_obligatoria_faltante():
    g = grafo("sin entrada", [("m", "econometria.mco", "MCO", {"y": "a", "x": ["b"]})], [])
    assert "entrada_faltante" in codigos(compilar(g))


def test_poda_de_ramas_muertas():
    """Lo que no alimenta un resultado no se compila."""
    g = grafo("poda", [
        ("d", "datos.ejemplo", "Datos", {"conjunto": "mexico_estados"}),
        ("t", "transformar.calcular", "Rama muerta", {"operacion": "log", "columna_a": "precio_m2"}),
        ("e", "explorar.descriptivos", "Descriptivos", {"columnas": ["precio_m2"]}),
    ], [("d", "datos", "t", "datos"), ("d", "datos", "e", "datos")])
    p = compilar(g)
    assert "t" in p.podados
    assert [i.nodo_id for i in p.instrucciones] == ["d", "e"]


def test_objetivo_compila_solo_el_cono_ancestral():
    g = grafo("objetivo", [
        ("d", "datos.ejemplo", "Datos", {"conjunto": "mexico_estados"}),
        ("t", "transformar.calcular", "Log", {"operacion": "log", "columna_a": "precio_m2"}),
        ("e", "explorar.descriptivos", "Descriptivos", {"columnas": ["precio_m2"]}),
    ], [("d", "datos", "t", "datos"), ("t", "datos", "e", "datos")])
    p = compilar(g, objetivo="t")
    assert [i.nodo_id for i in p.instrucciones] == ["d", "t"]


# --- validación de columnas -------------------------------------------------

def test_columna_inexistente_con_sugerencia():
    g = grafo("columnas", [
        ("d", "datos.ejemplo", "Datos", {"conjunto": "mexico_estados"}),
        ("m", "econometria.mco", "MCO", {"y": "precio_m3", "x": ["escolaridad_anios"]}),
    ], [("d", "datos", "m", "datos")])
    p = compilar(g)
    d = next(x for x in p.diagnosticos if x.codigo == "columna_inexistente")
    assert "precio_m2" in (d.sugerencia or ""), "debe proponer la columna parecida"


def test_esquema_se_propaga_por_el_grafo():
    """La columna que crea un nodo existe para los de aguas abajo."""
    g = grafo("propagacion", [
        ("d", "datos.ejemplo", "Datos", {"conjunto": "mexico_estados"}),
        ("t", "transformar.calcular", "Log", {"operacion": "log", "columna_a": "precio_m2"}),
        ("m", "econometria.mco", "MCO", {"y": "log_precio_m2", "x": ["escolaridad_anios"]}),
    ], [("d", "datos", "t", "datos"), ("t", "datos", "m", "datos")])
    p = compilar(g)
    assert not p.hay_errores
    assert "log_precio_m2" in p.esquemas["t"]["datos"].nombres()


def test_marca_de_estimado_viaja_por_el_grafo():
    """Un dato estimado contamina lo que toca, sin que nadie tenga que marcarlo."""
    g = grafo("ambar", [
        ("d", "datos.ejemplo", "Datos", {"conjunto": "mexico_estados"}),
        ("t", "transformar.calcular", "Log del precio estimado",
         {"operacion": "log", "columna_a": "precio_m2"}),
    ], [("d", "datos", "t", "datos")])
    p = compilar(g)
    nueva = p.esquemas["t"]["datos"].get("log_precio_m2")
    assert nueva is not None and nueva.es_estimado, (
        "precio_m2 viene marcado como estimación; su logaritmo también lo es"
    )


# --- nombres de variable ----------------------------------------------------

@pytest.mark.parametrize("entrada,esperado", [
    ("Precios CDMX 2020", "precios_cdmx_2020"),
    ("Análisis de inversión", "analisis_de_inversion"),
    ("  espacios   raros  ", "espacios_raros"),
    ("2020", "resultado_2020"),
    ("class", "class_"),
    ("", "resultado"),
])
def test_identificador(entrada, esperado):
    assert identificador(entrada) == esperado


def test_nombres_de_variable_vienen_de_la_etiqueta():
    """El script exportado lo lee una persona: nada de var_0, var_1, var_2."""
    g = grafo("nombres", [
        ("d", "datos.ejemplo", "Entidades", {"conjunto": "mexico_estados"}),
        ("t", "transformar.calcular", "Log precio", {"operacion": "log", "columna_a": "precio_m2"}),
    ], [("d", "datos", "t", "datos")])
    codigo = a_texto(emitir(compilar(g)))
    assert "entidades = pd.read_csv" in codigo
    assert "log_precio = entidades.copy()" in codigo


def test_etiquetas_repetidas_no_colisionan():
    g = grafo("colision", [
        ("d", "datos.ejemplo", "Datos", {"conjunto": "mexico_estados"}),
        ("a", "transformar.calcular", "Log", {"operacion": "log", "columna_a": "precio_m2"}),
        ("b", "transformar.calcular", "Log", {"operacion": "log", "columna_a": "plusvalia_pct"}),
        ("e", "explorar.descriptivos", "Fin", {"columnas": ["precio_m2"]}),
    ], [("d", "datos", "a", "datos"), ("a", "datos", "b", "datos"), ("b", "datos", "e", "datos")])
    p = compilar(g)
    variables = [v for i in p.instrucciones for v in i.salidas.values()]
    assert len(variables) == len(set(variables))


# --- huellas y caché --------------------------------------------------------

def test_mover_un_nodo_no_invalida_nada():
    """La posición no entra en la huella: mover no debe recalcular."""
    g1 = grafo("huella", [("d", "datos.ejemplo", "Datos", {"conjunto": "mexico_estados"})], [])
    g2 = g1.model_copy(deep=True)
    g2.nodos[0].posicion.x = 999
    assert compilar(g1).instrucciones[0].huella == compilar(g2).instrucciones[0].huella


def test_cambiar_un_parametro_invalida_aguas_abajo():
    def construir(columna):
        return grafo("huella", [
            ("d", "datos.ejemplo", "Datos", {"conjunto": "mexico_estados"}),
            ("t", "transformar.calcular", "Log", {"operacion": "log", "columna_a": columna}),
        ], [("d", "datos", "t", "datos")])

    a = compilar(construir("precio_m2"))
    b = compilar(construir("plusvalia_pct"))
    assert a.instrucciones[0].huella == b.instrucciones[0].huella, "el nodo de datos no cambió"
    assert a.instrucciones[1].huella != b.instrucciones[1].huella, "el nodo cambiado sí"


# --- seguridad --------------------------------------------------------------

HOSTILES = [
    'x"); import os; os.system("rm -rf /"); ("',
    "x'\n import os\n os.system('rm -rf /')\n#",
    'x") or __import__("os").system("id") or ("',
    "x\n\"\"\"\nimport socket\n",
]


def _esqueleto(codigo: str) -> str:
    """El árbol del script con TODAS las constantes borradas.

    Es la forma precisa de decir «los parámetros son datos, no código»: si un
    valor del usuario sólo puede acabar como constante o como comentario, el
    esqueleto no cambia al cambiar ese valor. Si el esqueleto cambia, el
    parámetro se convirtió en estructura, y eso es inyección.
    """
    import ast as _ast

    class _Borrar(_ast.NodeTransformer):
        def visit_Constant(self, nodo):
            return _ast.copy_location(_ast.Constant(value="·"), nodo)

    arbol = _Borrar().visit(_ast.parse(codigo))
    _ast.fix_missing_locations(arbol)
    return _ast.dump(arbol)


def _script(columna: str, etiqueta: str = "Calcular", notas: str | None = None) -> str:
    from abak_core import NodoSpec

    g = grafo("inyeccion", [
        ("d", "datos.ejemplo", "Datos", {"conjunto": "mexico_estados"}),
        ("t", "transformar.calcular", etiqueta, {"operacion": "log", "columna_a": columna}),
        ("e", "explorar.descriptivos", "Fin", {"columnas": ["precio_m2"]}),
    ], [("d", "datos", "t", "datos"), ("t", "datos", "e", "datos")])
    if notas is not None:
        g.nodos[1] = NodoSpec(**{**g.nodos[1].model_dump(), "notas": notas})
    return a_texto(emitir(compilar(g)))


@pytest.mark.parametrize("hostil", HOSTILES)
def test_un_parametro_hostil_no_cambia_el_programa(hostil):
    """Un nombre de columna hostil produce el MISMO programa, con otra constante.

    La comprobación no puede ser «la cadena no aparece en el texto»: aparece,
    escapada, dentro de un literal y de un comentario, y así debe ser. Lo que
    no puede pasar es que cambie la estructura del programa.
    """
    assert _esqueleto(_script(hostil)) == _esqueleto(_script("precio_m2"))


@pytest.mark.parametrize("hostil", HOSTILES)
def test_una_etiqueta_hostil_no_rompe_el_script(hostil):
    """La etiqueta del usuario acaba en un comentario de sección Y en el nombre
    de la variable. Lo primero se sanea; lo segundo se translitera a un
    identificador válido. El script sigue siendo Python legal y con la misma
    cantidad de sentencias que el benigno."""
    import ast as _ast

    hostil_arbol = _ast.parse(_script("precio_m2", etiqueta=hostil))
    benigno_arbol = _ast.parse(_script("precio_m2", etiqueta="Calcular"))
    assert len(hostil_arbol.body) == len(benigno_arbol.body)
    assert [type(n).__name__ for n in hostil_arbol.body] == \
           [type(n).__name__ for n in benigno_arbol.body]


@pytest.mark.parametrize("hostil", HOSTILES)
def test_una_nota_del_usuario_no_se_sale_del_comentario(hostil):
    """El texto libre va a comentarios; un salto de línea sin sanear cerraría el
    comentario y lo que siguiera sería código."""
    assert _esqueleto(_script("precio_m2", notas=hostil)) == _esqueleto(_script("precio_m2"))


def test_el_compilador_rechaza_la_columna_hostil_antes_de_ejecutar():
    g = grafo("inyeccion", [
        ("d", "datos.ejemplo", "Datos", {"conjunto": "mexico_estados"}),
        ("t", "transformar.calcular", "Calcular", {"operacion": "log", "columna_a": HOSTILES[0]}),
        ("e", "explorar.descriptivos", "Fin", {"columnas": ["precio_m2"]}),
    ], [("d", "datos", "t", "datos"), ("t", "datos", "e", "datos")])
    assert "columna_inexistente" in codigos(compilar(g))
