"""Conectores de fuentes oficiales.

No se puede llamar a Banxico ni a INEGI desde una prueba: además de que sería
frágil, las dos instituciones bloquean IPs de centros de datos, que es
exactamente el problema que estos nodos existen para resolver.

Lo que sí se prueba es todo lo demás, que es donde de verdad se rompen las
cosas: que la caché se use en vez de la red, que el formato de cada API se
interprete bien (fechas invertidas, «N/E», separadores de miles, periodos
trimestrales), que una clave hostil no llegue a la URL, y que el token no se
filtre al análisis ni al código exportado.
"""

import json
import os
from pathlib import Path

import pytest

from abak_core import a_texto, compilar, ejecutar, emitir
from abak_core.nodes.fuentes.http import dir_fuentes
from abak_core.registry import obtener

from .conftest import grafo

# --- respuestas reales, con sus rarezas ------------------------------------

RESPUESTA_BANXICO = {
    "bmx": {"series": [
        {"idSerie": "SF43718", "titulo": "Tipo de cambio pesos por dólar E.U.A.",
         "datos": [
             {"fecha": "02/01/2024", "dato": "16.9761"},
             {"fecha": "03/01/2024", "dato": "17.0251"},
             {"fecha": "04/01/2024", "dato": "N/E"},          # día sin dato
             {"fecha": "05/01/2024", "dato": "17.1130"},
         ]},
        {"idSerie": "SP1", "titulo": "Índice Nacional de Precios al Consumidor",
         "datos": [
             {"fecha": "02/01/2024", "dato": "1,234.56"},     # separador de miles
             {"fecha": "03/01/2024", "dato": "1,240.10"},
             {"fecha": "04/01/2024", "dato": "1,245.00"},
             {"fecha": "05/01/2024", "dato": "1,250.44"},
         ]},
    ]}
}

RESPUESTA_INEGI = {
    "Header": {"name": "INEGI", "email": ""},
    "Series": [
        {"INDICADOR": "628194", "FREQ": "8", "UNIT": "Índice",
         "OBSERVATIONS": [
             {"TIME_PERIOD": "2023/01", "OBS_VALUE": "101.4"},
             {"TIME_PERIOD": "2023/02", "OBS_VALUE": "102.0"},
             {"TIME_PERIOD": "2023/03", "OBS_VALUE": "103.7"},
         ]},
        {"INDICADOR": "493621", "FREQ": "6", "UNIT": "Millones de pesos",
         "OBSERVATIONS": [
             {"TIME_PERIOD": "2023/Q1", "OBS_VALUE": "20500.5"},   # trimestral
             {"TIME_PERIOD": "2023/Q2", "OBS_VALUE": "20880.1"},
         ]},
    ],
}

RESPUESTA_DENUE = [
    {"Id": "1", "Nombre": "Farmacia del centro", "Razon_social": "",
     "Clase_actividad": "Comercio al por menor de productos farmacéuticos",
     "Estrato": "6 a 10 personas", "Latitud": "19.4331", "Longitud": "-99.1350"},
    {"Id": "2", "Nombre": "Cafetería", "Razon_social": "Café SA de CV",
     "Clase_actividad": "Cafeterías", "Estrato": "0 a 5 personas",
     "Latitud": "19.4340", "Longitud": "-99.1361"},
]


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """Una caché de fuentes vacía, aislada de la del desarrollador."""
    destino = tmp_path / "fuentes"
    destino.mkdir(parents=True)
    monkeypatch.setenv("ABAK_FUENTES", str(destino))
    monkeypatch.setenv("ABAK_DATOS", str(tmp_path))
    return destino


def _sembrar(cache: Path, op: str, params: dict, respuesta) -> Path:
    """Deja en la caché la respuesta que la API habría devuelto."""
    spec = obtener(op)
    nombre = spec()._archivo(spec.Params.model_validate(params))
    archivo = cache / nombre
    archivo.write_text(json.dumps(respuesta), encoding="utf-8")
    return archivo


# --- Banxico ----------------------------------------------------------------

PARAMS_BANXICO = {"series": ["SF43718", "SP1"]}


def test_banxico_lee_de_la_cache_sin_tocar_la_red(cache, monkeypatch):
    """Sin token y sin red: si el archivo está, el análisis corre igual."""
    monkeypatch.delenv("BANXICO_TOKEN", raising=False)
    _sembrar(cache, "fuentes.banxico", PARAMS_BANXICO, RESPUESTA_BANXICO)

    g = grafo("banxico", [("b", "fuentes.banxico", "Tipo de cambio", PARAMS_BANXICO),
                          ("d", "explorar.descriptivos", "Descriptivos",
                           {"columnas": ["SF43718", "SP1"]})],
              [("b", "datos", "d", "datos")])
    programa = compilar(g)
    assert not programa.hay_errores, [d.mensaje for d in programa.diagnosticos]

    # El worker copia la caché al directorio de la corrida; aquí se simula.
    (Path(os.environ["ABAK_DATOS"]) / "fuentes").mkdir(exist_ok=True)
    for archivo in cache.glob("*.json"):
        (Path(os.environ["ABAK_DATOS"]) / "fuentes" / archivo.name).write_bytes(archivo.read_bytes())

    resultado = ejecutar(programa)
    assert resultado.ok, [n.error.excepcion for n in resultado.nodos if n.error]

    tabla = resultado.por_nodo()["b"].artefactos["datos"]
    assert [c["nombre"] for c in tabla["columnas"]] == ["fecha", "SF43718", "SP1"]
    assert tabla["n_filas"] == 4


def test_banxico_interpreta_las_rarezas_del_formato(cache, monkeypatch):
    """Fecha dd/mm/aaaa, «N/E» como faltante y separador de miles."""
    monkeypatch.delenv("BANXICO_TOKEN", raising=False)
    _sembrar(cache, "fuentes.banxico", PARAMS_BANXICO, RESPUESTA_BANXICO)
    (Path(os.environ["ABAK_DATOS"]) / "fuentes").mkdir(exist_ok=True)
    for archivo in cache.glob("*.json"):
        (Path(os.environ["ABAK_DATOS"]) / "fuentes" / archivo.name).write_bytes(archivo.read_bytes())

    g = grafo("banxico", [("b", "fuentes.banxico", "Series", PARAMS_BANXICO)], [])
    espacio: dict = {}
    emision = emitir(compilar(g))
    exec(compile(emision.preludio, "<t>", "exec"), espacio)
    exec(compile(emision.bloques[0].arbol, "<t>", "exec"), espacio)
    marco = espacio["series"]

    assert str(marco.index[0].date()) == "2024-01-02", "la fecha viene dd/mm/aaaa, no mm/dd/aaaa"
    assert marco["SF43718"].isna().sum() == 1, "«N/E» tiene que quedar como faltante"
    assert marco["SP1"].iloc[0] == pytest.approx(1234.56), "el separador de miles se quita"
    assert marco.attrs["titulos"]["SF43718"].startswith("Tipo de cambio")


def test_el_token_de_banxico_no_aparece_en_el_codigo_exportado(cache, monkeypatch):
    """Una credencial personal no puede viajar en un archivo que se comparte."""
    monkeypatch.setenv("BANXICO_TOKEN", "TOKEN-SECRETO-DE-PRUEBA-123")
    _sembrar(cache, "fuentes.banxico", PARAMS_BANXICO, RESPUESTA_BANXICO)
    g = grafo("banxico", [("b", "fuentes.banxico", "Series", PARAMS_BANXICO)], [])
    codigo = a_texto(emitir(compilar(g)))
    assert "TOKEN-SECRETO" not in codigo
    assert "BANXICO_TOKEN" in codigo, "el script debe LEER la variable, no llevar el valor"


def test_una_clave_hostil_no_llega_a_la_url():
    """Las claves entran a una URL: una con '/' o '?' redirigiría la petición."""
    from pydantic import ValidationError

    spec = obtener("fuentes.banxico")
    for hostil in ["SF43718/../../otro", "SF43718?x=1", "a b", "SF43718&y=2"]:
        with pytest.raises(ValidationError):
            spec.Params.model_validate({"series": [hostil]})


def test_el_esquema_se_conoce_sin_descargar():
    """Los desplegables de aguas abajo funcionan antes de tocar la red."""
    g = grafo("banxico", [
        ("b", "fuentes.banxico", "Series", PARAMS_BANXICO),
        ("d", "explorar.descriptivos", "Descriptivos", {"columnas": ["SF43718"]}),
    ], [("b", "datos", "d", "datos")])
    programa = compilar(g)
    assert not programa.hay_errores
    assert programa.esquemas["b"]["datos"].nombres() == ["SF43718", "SP1"]


def test_una_columna_inexistente_se_detecta_antes_de_descargar():
    g = grafo("banxico", [
        ("b", "fuentes.banxico", "Series", PARAMS_BANXICO),
        ("d", "explorar.descriptivos", "Descriptivos", {"columnas": ["SF99999"]}),
    ], [("b", "datos", "d", "datos")])
    codigos = {d.codigo for d in compilar(g).diagnosticos if d.severidad == "error"}
    assert "columna_inexistente" in codigos


# --- INEGI ------------------------------------------------------------------

PARAMS_INEGI = {"indicadores": ["628194", "493621"], "area": "0700", "banco": "BIE"}


def test_inegi_normaliza_los_periodos(cache, monkeypatch):
    """TIME_PERIOD viene como '2023/01' o como '2023/Q1'."""
    monkeypatch.delenv("INEGI_TOKEN", raising=False)
    _sembrar(cache, "fuentes.inegi", PARAMS_INEGI, RESPUESTA_INEGI)
    destino = Path(os.environ["ABAK_DATOS"]) / "fuentes"
    destino.mkdir(exist_ok=True)
    for archivo in cache.glob("*.json"):
        (destino / archivo.name).write_bytes(archivo.read_bytes())

    g = grafo("inegi", [("i", "fuentes.inegi", "Indicadores", PARAMS_INEGI)], [])
    espacio: dict = {}
    emision = emitir(compilar(g))
    exec(compile(emision.preludio, "<t>", "exec"), espacio)
    exec(compile(emision.bloques[0].arbol, "<t>", "exec"), espacio)
    marco = espacio["indicadores"]

    fechas = [str(f.date()) for f in marco.index]
    assert "2023-01-01" in fechas and "2023-03-01" in fechas, "mensual"
    assert "2023-04-01" in fechas, "'2023/Q2' es el inicio del segundo trimestre"
    assert marco["628194"].dropna().iloc[0] == pytest.approx(101.4)


@pytest.mark.parametrize("crudo,esperado", [
    ("2020", "2020-01-01"), ("2020/03", "2020-03-01"), ("2020/Q2", "2020-04-01"),
    ("2020/T4", "2020-10-01"), ("2020/03/15", "2020-03-15"), ("", None),
])
def test_periodo_inegi(crudo, esperado):
    from abak_core.registry import AYUDANTES

    espacio: dict = {}
    exec(AYUDANTES["_periodo_inegi"].fuente, espacio)
    assert espacio["_periodo_inegi"](crudo) == esperado


def test_area_geografica_validada():
    from pydantic import ValidationError

    spec = obtener("fuentes.inegi")
    with pytest.raises(ValidationError):
        spec.Params.model_validate({"indicadores": ["628194"], "area": "../etc"})


# --- DENUE ------------------------------------------------------------------

PARAMS_DENUE = {"condicion": "farmacia", "latitud": 19.4326, "longitud": -99.1332, "metros": 500}


def test_denue_lee_de_la_cache(cache, monkeypatch):
    monkeypatch.delenv("INEGI_TOKEN", raising=False)
    _sembrar(cache, "fuentes.denue", PARAMS_DENUE, RESPUESTA_DENUE)
    destino = Path(os.environ["ABAK_DATOS"]) / "fuentes"
    destino.mkdir(exist_ok=True)
    for archivo in cache.glob("*.json"):
        (destino / archivo.name).write_bytes(archivo.read_bytes())

    g = grafo("denue", [("d", "fuentes.denue", "Establecimientos", PARAMS_DENUE)], [])
    resultado = ejecutar(compilar(g))
    assert resultado.ok, [n.error.excepcion for n in resultado.nodos if n.error]
    tabla = resultado.por_nodo()["d"].artefactos["datos"]
    assert tabla["n_filas"] == 2


def test_denue_rechaza_coordenadas_invertidas(cache):
    """En México la longitud es negativa. Invertidas, el punto cae en China."""
    from abak_core.registry import AYUDANTES
    from abak_core.codegen.contexto import resolver_ayudantes

    espacio: dict = {}
    for ayudante in resolver_ayudantes(["traer_denue"]):
        for modulo, alias in ayudante.imports:
            espacio[alias or modulo.split(".")[0]] = __import__(modulo)
        exec(ayudante.fuente, espacio)
    with pytest.raises(ValueError, match="fuera de rango"):
        espacio["traer_denue"]("todos", 199.0, -99.0, 500, cache)


# --- el paquete exportado ---------------------------------------------------

def test_el_paquete_lleva_la_cache_de_fuentes(cache, monkeypatch):
    """Sin los datos dentro, un análisis con fuentes en vivo no es reproducible."""
    import io
    import zipfile

    from abak_core.runtime.exportar import paquete

    monkeypatch.delenv("BANXICO_TOKEN", raising=False)
    _sembrar(cache, "fuentes.banxico", PARAMS_BANXICO, RESPUESTA_BANXICO)
    g = grafo("banxico", [("b", "fuentes.banxico", "Series", PARAMS_BANXICO)], [])
    contenido = set(zipfile.ZipFile(io.BytesIO(paquete(compilar(g)))).namelist())
    assert any(n.startswith("datos/fuentes/") for n in contenido), (
        "el .zip tiene que llevar la caché o el script no reproduce los mismos números"
    )
