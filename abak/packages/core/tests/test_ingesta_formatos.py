"""Los archivos como llegan de verdad, no como uno querría que llegaran.

El camino de un clic —«Subir datos»— no puede pedirle a nadie que sepa de
antemano si su CSV trae punto y coma o coma decimal. Antes de detectar el
formato pasaban dos cosas, y las dos son de las peores que puede hacer un
programa:

  · Un CSV exportado por un Excel en español (punto y coma + coma decimal), que
    es EL formato más común en México, se leía como UNA sola columna llamada
    «entidad;precio_m2;escolaridad», con basura dentro y **sin ningún error**.
  · Un archivo en latin-1 moría con «'utf-8' codec can't decode byte 0xe9 in
    position 4», que no le dice nada a nadie.
"""

import zipfile
from pathlib import Path

import pytest

from abak_core.runtime.ingesta import ErrorIngesta, csv_a_parquet, detectar_formato

pytest.importorskip("pyarrow")

FILAS = [("Querétaro", "12500.50", "9.8"),
         ("Ciudad de México", "31200.75", "11.2"),
         ("Mérida", "14800.00", "10.1")]
ENCABEZADO = ("entidad", "precio_m2", "escolaridad")


def _csv(tmp_path: Path, nombre: str, sep: str, decimal_coma: bool, codificacion: str) -> Path:
    def campo(x: str) -> str:
        return x.replace(".", ",") if decimal_coma else x
    texto = (sep.join(ENCABEZADO) + "\n"
             + "\n".join(sep.join(campo(c) for c in fila) for fila in FILAS))
    ruta = tmp_path / nombre
    ruta.write_bytes(texto.encode(codificacion))
    return ruta


# --- Detección --------------------------------------------------------------

@pytest.mark.parametrize("sep,nombre", [(",", "coma"), (";", "puntoycoma"),
                                        ("\t", "tab"), ("|", "barra")])
def test_se_detecta_cada_separador(tmp_path, sep, nombre):
    ruta = _csv(tmp_path, f"{nombre}.csv", sep, decimal_coma=False, codificacion="utf-8")
    d = detectar_formato(ruta)
    assert d["separador"] == sep
    assert d["columnas_detectadas"] == 3


def test_el_csv_de_un_excel_en_espanol_se_detecta_entero(tmp_path):
    """Punto y coma Y coma decimal a la vez: el caso que se leía como basura."""
    ruta = _csv(tmp_path, "excel.csv", ";", decimal_coma=True, codificacion="utf-8")
    d = detectar_formato(ruta)
    assert d["separador"] == ";"
    assert d["decimal"] == ","
    assert d["columnas_detectadas"] == 3


@pytest.mark.parametrize("codificacion", ["utf-8", "cp1252", "latin-1"])
def test_se_detecta_la_codificacion(tmp_path, codificacion):
    ruta = _csv(tmp_path, "acentos.csv", ",", decimal_coma=False, codificacion=codificacion)
    d = detectar_formato(ruta)
    # Se acepta cualquiera que decodifique los acentos sin romperlos.
    texto = ruta.read_bytes().decode(d["codificacion"])
    assert "Querétaro" in texto and "Mérida" in texto


def test_una_coma_dentro_de_comillas_no_cuenta_como_separador(tmp_path):
    ruta = tmp_path / "comillas.csv"
    ruta.write_text('nombre;monto\n"Torres, Juan";1500\n"Díaz, Ana";2300\n', encoding="utf-8")
    d = detectar_formato(ruta)
    assert d["separador"] == ";", "la coma de dentro de las comillas se contó como separador"
    assert d["columnas_detectadas"] == 2


def test_un_archivo_vacio_lo_dice(tmp_path):
    ruta = tmp_path / "vacio.csv"
    ruta.write_bytes(b"")
    with pytest.raises(ErrorIngesta):
        detectar_formato(ruta)


# --- De punta a punta: detectar y convertir ---------------------------------

def _leer(tmp_path, ruta):
    import pandas as pd

    d = detectar_formato(ruta)
    destino = tmp_path / "salida.parquet"
    csv_a_parquet(ruta, destino, separador=d["separador"], decimal=d["decimal"],
                  codificacion=d["codificacion"])
    return pd.read_parquet(destino)


def test_el_excel_en_espanol_acaba_con_numeros_de_verdad(tmp_path):
    """Lo que importa no es que se lea: es que el precio sea un NÚMERO.

    Con el separador mal, «precio_m2» acababa siendo texto y cualquier regresión
    posterior fallaba o —peor— trataba la columna como categoría.
    """
    ruta = _csv(tmp_path, "excel.csv", ";", decimal_coma=True, codificacion="utf-8")
    df = _leer(tmp_path, ruta)
    assert list(df.columns) == list(ENCABEZADO)
    assert len(df) == 3
    assert df["precio_m2"].dtype.kind == "f", f"precio_m2 quedó como {df['precio_m2'].dtype}"
    assert df["precio_m2"].iloc[0] == pytest.approx(12500.50)
    assert df["escolaridad"].iloc[2] == pytest.approx(10.1)


def test_latin1_conserva_los_acentos(tmp_path):
    ruta = _csv(tmp_path, "latin.csv", ",", decimal_coma=False, codificacion="latin-1")
    df = _leer(tmp_path, ruta)
    assert df["entidad"].tolist() == ["Querétaro", "Ciudad de México", "Mérida"]


def test_el_bom_de_windows_no_se_pega_al_primer_encabezado(tmp_path):
    """Excel guarda «UTF-8 con BOM» y sin quitarlo la primera columna se llama
    «\\ufeffentidad», que luego no coincide con nada de lo que uno elige."""
    ruta = _csv(tmp_path, "bom.csv", ",", decimal_coma=False, codificacion="utf-8-sig")
    df = _leer(tmp_path, ruta)
    assert list(df.columns)[0] == "entidad"


def test_un_zip_con_dos_tablas_no_se_adivina(tmp_path):
    """Está en el router, pero la regla es de producto: analizar el archivo
    equivocado en silencio es peor que fallar."""
    uno = _csv(tmp_path, "a.csv", ",", decimal_coma=False, codificacion="utf-8")
    z = tmp_path / "dos.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("a.csv", uno.read_text(encoding="utf-8"))
        f.writestr("b.csv", uno.read_text(encoding="utf-8"))
    with zipfile.ZipFile(z) as f:
        tabulares = [n for n in f.namelist() if n.endswith(".csv")]
    assert len(tabulares) == 2
