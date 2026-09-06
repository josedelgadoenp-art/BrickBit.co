"""El informe en PDF.

Lo que hay que verificar aquí no es que «se vea bonito» sino tres cosas que se
pueden afirmar: que el archivo es un PDF válido, que dice lo que tiene que
decir (incluido el aviso de datos estimados), y sobre todo que **se genera
igual cuando falta Chrome**, porque de otro modo una dependencia opcional
tumbaría el entregable completo.
"""

import pytest

from abak_core import a_texto, compilar, ejecutar, emitir
from abak_core.runtime.informe import informe_pdf
from abak_core.runtime.metodologia import nota_metodologica

from .conftest import grafo

pytest.importorskip("fpdf")

FLUJO = grafo("Informe de prueba", [
    ("d", "datos.ejemplo", "Entidades", {"conjunto": "mexico_estados"}),
    ("t", "transformar.calcular", "Log precio", {"operacion": "log", "columna_a": "precio_m2"}),
    ("m", "econometria.mco", "Modelo",
     {"y": "log_precio_m2", "x": ["escolaridad_anios", "empleo_formal_pct"]}),
    ("e", "explorar.descriptivos", "Descriptivos", {"columnas": ["precio_m2"]}),
], [("d", "datos", "t", "datos"), ("t", "datos", "m", "datos"), ("t", "datos", "e", "datos")])


@pytest.fixture(scope="module")
def corrida():
    programa = compilar(FLUJO)
    resultado = ejecutar(programa)
    assert resultado.ok, [n.error for n in resultado.nodos if n.error]
    nodos = {
        n.nodo_id: {"etiqueta": n.etiqueta, "estado": n.estado, "ms": n.ms,
                    "artefactos": n.artefactos, "error": None}
        for n in resultado.nodos
    }
    return programa, nodos


def _pdf(programa, nodos, **kw) -> bytes:
    return informe_pdf(titulo=programa.titulo, huella=programa.huella_grafo,
                       semilla=programa.semilla, nodos=nodos, orden=programa.orden, **kw)


def _texto(pdf: bytes) -> str:
    pypdf = pytest.importorskip("pypdf")
    import io

    lector = pypdf.PdfReader(io.BytesIO(pdf))
    return "\n".join((p.extract_text() or "") for p in lector.pages)


def test_es_un_pdf_valido(corrida):
    pdf = _pdf(*corrida)
    assert pdf.startswith(b"%PDF-"), "no es un PDF"
    assert pdf.rstrip().endswith(b"%%EOF"), "el PDF quedó truncado"
    assert len(pdf) > 5000


def test_el_informe_lleva_lo_que_hay_que_poder_citar(corrida):
    programa, nodos = corrida
    texto = _texto(_pdf(programa, nodos, metodologia=nota_metodologica(programa)))
    assert programa.titulo in texto.replace("\n", " ")
    assert programa.huella_grafo[:12] in texto, "sin huella no se puede rastrear de dónde salió"
    assert str(programa.semilla) in texto, "sin semilla no se puede repetir"
    assert "Modelo" in texto and "escolaridad_anios" in texto


def test_avisa_de_los_datos_estimados(corrida):
    """El principio de la casa también en papel: lo estimado se marca."""
    texto = _texto(_pdf(*corrida))
    assert "estimados" in texto or "est." in texto
    assert "precio_m2" in texto, "debe nombrar las columnas afectadas"


def test_el_apendice_trae_el_codigo_que_corrio(corrida):
    programa, nodos = corrida
    codigo = a_texto(emitir(programa))
    texto = _texto(_pdf(programa, nodos, codigo=codigo))
    assert "sm.OLS" in texto.replace(" ", "") or "OLS" in texto


def test_un_bloque_solo(corrida):
    programa, nodos = corrida
    completo = _pdf(programa, nodos)
    parcial = _pdf(programa, nodos, solo_nodo="m")
    assert len(parcial) < len(completo)
    assert "Descriptivos" not in _texto(parcial)


def test_bloque_inexistente_es_un_error_claro(corrida):
    from abak_core.runtime.informe import ErrorInforme

    programa, nodos = corrida
    with pytest.raises(ErrorInforme, match="no tiene resultados"):
        _pdf(programa, nodos, solo_nodo="no_existe")


def test_el_informe_se_genera_aunque_no_haya_chrome(corrida, monkeypatch):
    """La prueba que más importa.

    Convertir una gráfica a imagen necesita Chrome. En un contenedor sin
    navegador eso falla, y el informe TIENE que salir igual: con sus tablas, su
    metodología y, en el lugar de cada figura, la explicación de por qué falta.
    Si una dependencia opcional tumbara el entregable completo, sería el peor
    canje posible.
    """
    import abak_core.runtime.informe as modulo

    monkeypatch.setattr(modulo, "_figura_a_png",
                        lambda _fig: (None, "Chrome no está instalado en este servidor."))

    programa, nodos = corrida
    con_figura = dict(nodos)
    con_figura["fig"] = {
        "etiqueta": "Una gráfica", "estado": "listo", "ms": 4, "error": None,
        "artefactos": {"figura": {"tipo": "figura", "titulo": "Gráfica de prueba",
                                  "figura": {"data": [], "layout": {}}}},
    }
    pdf = informe_pdf(titulo=programa.titulo, huella=programa.huella_grafo,
                      semilla=programa.semilla, nodos=con_figura,
                      orden=list(programa.orden) + ["fig"])
    texto = _texto(pdf)
    assert pdf.startswith(b"%PDF-")
    assert "Chrome" in texto, "el informe debe decir POR QUÉ falta la figura"
    assert "no se ven afectadas" in texto
    assert "escolaridad_anios" in texto, "y las tablas tienen que seguir ahí"


def test_una_tabla_muy_ancha_se_recorta_y_lo_dice(corrida):
    """Una tabla de 40 columnas no cabe en A4: mejor menos columnas legibles
    que cuarenta ilegibles, y hay que decir cuántas quedaron fuera."""
    programa, _ = corrida
    columnas = [{"nombre": f"columna_{i}", "tipo": "numerica", "estimada": False}
                for i in range(40)]
    filas = [[float(i * j) for j in range(40)] for i in range(5)]
    nodos = {"x": {"etiqueta": "Tabla ancha", "estado": "listo", "ms": 1, "error": None,
                   "artefactos": {"datos": {"tipo": "tabla", "titulo": "Ancha",
                                            "columnas": columnas, "filas": filas,
                                            "n_filas": 5, "truncada": False}}}}
    texto = _texto(informe_pdf(titulo="Ancha", huella="a" * 24, semilla=1,
                               nodos=nodos, orden=["x"]))
    assert "columnas" in texto and "40" in texto


def test_los_titulos_con_acentos_no_rompen_el_pdf():
    """El título llega de un campo de texto: puede traer lo que sea."""
    nodos = {"x": {"etiqueta": "Análisis · 2024", "estado": "listo", "ms": 1, "error": None,
                   "artefactos": {"v": {"tipo": "escalar", "titulo": "Valor", "valor": 3.14}}}}
    pdf = informe_pdf(titulo="Precio por m² — «Análisis» ½ 2024", huella="b" * 24,
                      semilla=1, nodos=nodos, orden=["x"], autor="Ünïcode")
    assert pdf.startswith(b"%PDF-")
