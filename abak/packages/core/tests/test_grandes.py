"""Volúmenes grandes: que quepa, que sea rápido y —sobre todo— que sea igual.

La pregunta que manda aquí no es «¿aguanta?» sino «¿da lo mismo?». Toda
optimización de memoria es una oportunidad de cambiar un resultado en silencio,
y un resultado que cambia sin avisar es peor que un análisis que no corre.
"""

import numpy as np
import pandas as pd
import pytest

from abak_core import AristaSpec, GrafoSpec, NodoSpec, a_texto, compilar, ejecutar, emitir

pytest.importorskip("pyarrow")

from abak_core.runtime.ingesta import (  # noqa: E402
    csv_a_parquet, deducir_tipos, estimar_memoria, revisar_memoria,
)


@pytest.fixture(scope="module")
def csv_mixto(tmp_path_factory):
    """Un CSV con la trampa clásica: una columna que parece entera al principio
    y trae decimales mucho después."""
    ruta = tmp_path_factory.mktemp("datos") / "mixto.csv"
    n = 30_000
    rng = np.random.default_rng(11)
    valores = np.arange(n, dtype=float)
    valores[25_000:] += 0.5           # los decimales aparecen tarde
    pd.DataFrame({
        "id": np.arange(n),
        "traicionera": valores,
        "entidad": rng.choice([f"E{i:02d}" for i in range(20)], n),
        "ingreso": np.round(np.exp(rng.normal(9.5, 0.6, n)), 2),
        "edad": rng.integers(18, 80, n),
        **{f"relleno_{i}": rng.normal(0, 1, n) for i in range(10)},
    }).to_csv(ruta, index=False)
    return ruta


def test_los_tipos_se_fijan_antes_de_leer(csv_mixto):
    """El bug que este diseño existe para evitar.

    Si los tipos se dedujeran trozo por trozo, «traicionera» saldría int64 en
    los primeros trozos y float64 en los últimos: una columna de tipo mixto
    que falla raro y sin avisar. Al fijarlos con una muestra, sale float en
    todos.
    """
    dtypes, _fechas, _avisos = deducir_tipos(csv_mixto, filas=30_000)
    assert dtypes["traicionera"] == "float64"
    assert dtypes["edad"] in ("Int8", "Int16"), "un rango 18-80 no necesita 64 bits"
    assert dtypes["entidad"] == "category", "20 valores distintos en 30 mil filas"


def test_los_flotantes_no_se_reducen(csv_mixto):
    """float32 tiene ~7 dígitos: cambiar precisión por memoria es un mal canje
    en un sistema que va a hacer econometría."""
    dtypes, _f, _a = deducir_tipos(csv_mixto)
    for nombre, tipo in dtypes.items():
        assert tipo != "float32", f"{nombre} se redujo a float32"


def test_parquet_conserva_los_valores_exactos(csv_mixto, tmp_path):
    """La conversión no puede mover ni un dígito."""
    destino = tmp_path / "salida.parquet"
    info = csv_a_parquet(csv_mixto, destino)
    original = pd.read_csv(csv_mixto)
    convertido = pd.read_parquet(destino)

    assert info.n_filas == len(original)
    assert set(convertido.columns) == set(original.columns)
    for columna in ("traicionera", "ingreso", *[f"relleno_{i}" for i in range(10)]):
        np.testing.assert_array_equal(
            convertido[columna].to_numpy(float), original[columna].to_numpy(float),
            err_msg=f"la columna {columna} cambió al convertir")
    assert (convertido["edad"].astype("int64").to_numpy()
            == original["edad"].to_numpy()).all()
    assert (convertido["entidad"].astype(str).to_numpy()
            == original["entidad"].astype(str).to_numpy()).all()


def _grafo(archivo_id: str, columnas: list[dict], n_filas: int) -> GrafoSpec:
    return GrafoSpec(titulo="Ingreso y edad", semilla=3, nodos=[
        NodoSpec(id="d", op="datos.csv", etiqueta="Microdatos",
                 params={"archivo_id": archivo_id, "nombre": "mixto.csv",
                         "columnas": columnas, "n_filas": n_filas}),
        NodoSpec(id="t", op="transformar.calcular", etiqueta="Log ingreso",
                 params={"operacion": "log", "columna_a": "ingreso"}, posicion={"x": 0, "y": 1}),
        NodoSpec(id="m", op="econometria.mco", etiqueta="Modelo",
                 params={"y": "log_ingreso", "x": ["edad"], "errores": "HC1"},
                 posicion={"x": 0, "y": 2}),
    ], aristas=[
        AristaSpec(origen="d", puerto_origen="datos", destino="t", puerto_destino="datos"),
        AristaSpec(origen="t", puerto_origen="datos", destino="m", puerto_destino="datos"),
    ])


@pytest.fixture
def preparado(csv_mixto, tmp_path, monkeypatch):
    """El archivo ya convertido y el entorno apuntando ahí."""
    from abak_core.runtime.almacen import Almacen

    monkeypatch.setenv("ABAK_INICIO", str(tmp_path / "abak"))
    almacen = Almacen(tmp_path / "abak")
    parquet = almacen.dir_subidas() / "a_prueba.parquet"
    info = csv_a_parquet(csv_mixto, parquet)
    monkeypatch.setenv("ABAK_DATOS", str(almacen.dir_subidas()))
    return info


def test_la_poda_de_columnas_se_calcula_y_se_usa(preparado):
    """De 15 columnas, el análisis usa dos: se leen dos."""
    programa = compilar(_grafo("a_prueba", preparado.columnas, preparado.n_filas))
    assert not programa.hay_errores, [d.mensaje for d in programa.diagnosticos]
    assert programa.proyeccion is not None
    assert {"ingreso", "edad"} <= programa.proyeccion
    assert "relleno_0" not in programa.proyeccion

    codigo = a_texto(emitir(programa))
    assert "columns=['ingreso', 'edad']" in codigo or "columns=['edad', 'ingreso']" in codigo
    assert "relleno_0" not in codigo


def test_la_poda_NO_cambia_el_resultado(preparado, monkeypatch):
    """La prueba que justifica toda la optimización.

    Se corre el mismo análisis con poda y sin poda, y los coeficientes tienen
    que salir bit a bit iguales. Si difieren, la poda no sirve por rápida que
    sea.
    """
    grafo = _grafo("a_prueba", preparado.columnas, preparado.n_filas)

    con_poda = ejecutar(compilar(grafo))
    assert con_poda.ok, [n.error.excepcion for n in con_poda.nodos if n.error]

    # Se desactiva la poda del mismo modo que lo haría un nodo que usa todas
    # las columnas, y se vuelve a correr.
    programa_sin = compilar(grafo)
    programa_sin.proyeccion = None
    sin_poda = ejecutar(programa_sin)
    assert sin_poda.ok, [n.error.excepcion for n in sin_poda.nodos if n.error]

    def coefs(resultado):
        return {c["variable"]: c["coeficiente"]
                for c in resultado.por_nodo()["m"].artefactos["modelo"]["coeficientes"]}

    assert coefs(con_poda) == coefs(sin_poda), "leer menos columnas cambió el resultado"


def test_un_nodo_que_usa_todas_las_columnas_apaga_la_poda(preparado):
    """Basta con uno para que dejar de podar sea lo correcto."""
    grafo = _grafo("a_prueba", preparado.columnas, preparado.n_filas)
    grafo.nodos.append(NodoSpec(id="e", op="explorar.descriptivos", etiqueta="Todo",
                                params={"columnas": []}, posicion={"x": 1, "y": 3}))
    grafo.aristas.append(AristaSpec(origen="t", puerto_origen="datos",
                                    destino="e", puerto_destino="datos"))
    assert compilar(grafo).proyeccion is None


def test_exportar_tabla_apaga_la_poda(preparado):
    """Exportar escribe la tabla completa: podar la dejaría incompleta y nadie
    se enteraría hasta abrir el archivo."""
    grafo = _grafo("a_prueba", preparado.columnas, preparado.n_filas)
    grafo.nodos.append(NodoSpec(id="x", op="salida.exportar", etiqueta="A CSV",
                                params={"nombre_archivo": "salida"}, posicion={"x": 1, "y": 3}))
    grafo.aristas.append(AristaSpec(origen="t", puerto_origen="datos",
                                    destino="x", puerto_destino="datos"))
    assert compilar(grafo).proyeccion is None


# --- barandal de memoria ----------------------------------------------------

def test_la_estimacion_distingue_por_tipo():
    """Una columna de texto pesa mucho más que una de enteros de 16 bits.
    Estimar con un promedio es como se llega a un OOM después de decir que sí."""
    filas = 1_000_000
    enteros = [{"nombre": "a", "tipo_arrow": "int16"}]
    textos = [{"nombre": "a", "tipo_arrow": "string"}]
    assert estimar_memoria(filas, textos) > 8 * estimar_memoria(filas, enteros)


def test_el_barandal_avisa_antes_de_tronar(monkeypatch):
    monkeypatch.setenv("ABAK_LIMITE_MEMORIA_GB", "1")
    columnas = [{"nombre": f"c{i}", "tipo_arrow": "double"} for i in range(50)]
    aviso = revisar_memoria(50_000_000, columnas)
    assert aviso is not None
    assert "GB" in aviso and "columnas" in aviso, "el aviso debe decir cuánto y qué hacer"
    assert revisar_memoria(1_000, columnas) is None


def test_sin_limite_configurado_no_estorba(monkeypatch):
    monkeypatch.delenv("ABAK_LIMITE_MEMORIA_GB", raising=False)
    assert revisar_memoria(10**9, [{"nombre": "c", "tipo_arrow": "double"}]) is None


def _comentarios(codigo: str) -> str:
    """Los comentarios del script, unidos: van envueltos a 78 columnas."""
    return " ".join(l.lstrip("# ").strip() for l in codigo.splitlines() if l.lstrip().startswith("#"))


def test_un_tope_de_filas_se_declara_en_el_codigo(preparado):
    """Leer sólo una parte cambia los resultados: tiene que quedar escrito."""
    grafo = _grafo("a_prueba", preparado.columnas, preparado.n_filas)
    grafo.nodos[0].params["tope_filas"] = 1000
    codigo = a_texto(emitir(compilar(grafo)))
    assert "head(1000)" in codigo
    assert "NO son los de la tabla completa" in _comentarios(codigo)


def test_la_poda_se_explica_en_el_codigo(preparado):
    """Si el script lee 2 de 15 columnas, tiene que decir por qué: quien lo lea
    después no puede quedarse con la duda de si se perdió algo."""
    codigo = a_texto(emitir(compilar(_grafo("a_prueba", preparado.columnas, preparado.n_filas))))
    comentarios = _comentarios(codigo)
    assert "columnas del archivo se leen" in comentarios
    assert "unicas que este analisis usa" in comentarios
