"""Subir un .zip: el caso normal y los tres que muerden.

Las fuentes oficiales mexicanas (DENUE, SHF, casi todo el INEGI) se publican
comprimidas, así que el .zip es un formato de entrada de verdad, no una
comodidad. Y un .zip que llega de fuera es un archivo hostil hasta que se
demuestre lo contrario.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from abak_api.main import app

CLIENTE = TestClient(app)
CSV = b"ciudad,precio_m2,anio\nMonterrey,12700,2026\nLeon,12500,2026\nColima,11500,2026\n"


def _zip(archivos: dict[str, bytes]) -> bytes:
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, contenido in archivos.items():
            z.writestr(nombre, contenido)
    return memoria.getvalue()


def _subir(datos: bytes, nombre: str = "datos.zip"):
    return CLIENTE.post("/api/v1/datos/subir",
                        files={"archivo": (nombre, datos, "application/zip")})


def test_un_zip_con_un_csv_adentro_se_sube_igual_que_el_csv():
    r = _subir(_zip({"precios.csv": CSV}))
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["n_filas"] == 3
    assert "ciudad" in [c["nombre"] for c in cuerpo["columnas"]]


def test_se_ignora_la_basura_que_meten_mac_y_windows():
    r = _subir(_zip({
        "__MACOSX/._precios.csv": b"basura",
        ".DS_Store": b"basura",
        "precios.csv": CSV,
    }))
    assert r.status_code == 200, r.text
    assert r.json()["n_filas"] == 3


def test_con_varios_archivos_no_se_adivina_cual():
    """Analizar el archivo equivocado en silencio es peor que fallar."""
    r = _subir(_zip({"2025.csv": CSV, "2026.csv": CSV}))
    assert r.status_code == 422
    detalle = r.json()["detail"]
    assert "2025.csv" in detalle and "2026.csv" in detalle


def test_un_zip_sin_datos_lo_dice():
    r = _subir(_zip({"leeme.pdf": b"%PDF-1.4", "notas.docx": b"PK"}))
    assert r.status_code == 422
    assert "ningún archivo de datos" in r.json()["detail"]


def test_un_zip_roto_no_tumba_nada():
    r = _subir(b"esto no es un zip, ni de lejos")
    assert r.status_code == 422
    assert "zip" in r.json()["detail"].lower()


def test_zip_slip_no_escribe_fuera_de_su_carpeta(tmp_path):
    """Un nombre como «../../robado.csv» no puede sacar el archivo de su sitio."""
    centinela = Path("/tmp/abak_zip_slip_centinela.csv")
    centinela.unlink(missing_ok=True)
    r = _subir(_zip({"../../../../../../tmp/abak_zip_slip_centinela.csv": CSV}))
    # Se acepta —el nombre final es válido— pero escrito en SU carpeta.
    assert r.status_code == 200, r.text
    assert not centinela.exists(), "el zip escribió fuera de su carpeta"


def test_una_bomba_de_descompresion_se_corta():
    """Un zip chico que se infla a gigas se detiene al escribir, no al leer
    el tamaño que el propio zip declara (ése puede mentir)."""
    import os

    from abak_api.routers import datos as modulo

    enorme = b"a,b\n" + b"1,2\n" * 400_000          # ~2 MB de texto
    paquete = _zip({"gigante.csv": enorme})
    assert len(paquete) < len(enorme) / 4, "el caso no comprime, no prueba nada"

    original = modulo.TOPE_BYTES
    modulo.TOPE_BYTES = 100_000                     # tope chiquito a propósito
    try:
        r = _subir(paquete)
        assert r.status_code == 422
        assert "MB" in r.json()["detail"]
    finally:
        modulo.TOPE_BYTES = original
