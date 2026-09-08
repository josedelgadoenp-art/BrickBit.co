"""La afirmación central del producto, puesta a prueba.

«El código que exportas es el mismo que se ejecutó» no es una promesa de
mercadotecnia si se puede comprobar. Aquí se comprueba: se exporta el paquete,
se descomprime en una carpeta temporal y se corre en un proceso donde
`abak_core` NO existe. Los coeficientes tienen que salir idénticos.
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

from abak_core import a_texto, compilar, ejecutar, emitir
from abak_core.runtime.exportar import paquete

from .conftest import grafo

FLUJO = grafo("Precio por m2 y sus determinantes", [
    ("d", "datos.ejemplo", "Entidades", {"conjunto": "mexico_estados"}),
    ("t", "transformar.calcular", "Log precio", {"operacion": "log", "columna_a": "precio_m2"}),
    ("u", "transformar.calcular", "Log ingreso",
     {"operacion": "log", "columna_a": "ingreso_hogar_mensual"}),
    ("m", "econometria.mco", "Modelo hedonico",
     {"y": "log_precio_m2", "x": ["log_ingreso_hogar_mensual", "escolaridad_anios"],
      "errores": "HC3"}),
], [("d", "datos", "t", "datos"), ("t", "datos", "u", "datos"), ("u", "datos", "m", "datos")],
    semilla=7)


def test_el_script_exportado_es_python_valido():
    import ast

    ast.parse(a_texto(emitir(compilar(FLUJO))))


def test_el_paquete_trae_todo_lo_necesario():
    contenido = set(zipfile.ZipFile(io.BytesIO(paquete(compilar(FLUJO)))).namelist())
    assert {"analisis.py", "metodologia.md", "requisitos.txt", "LEEME.md"} <= contenido
    assert any(n.startswith("datos/") for n in contenido), "sin datos no es reproducible"


def test_los_requisitos_no_mencionan_abak():
    """El script tiene que correr sin instalar Abak. Si aparece aquí, no corre."""
    with zipfile.ZipFile(io.BytesIO(paquete(compilar(FLUJO)))) as z:
        requisitos = z.read("requisitos.txt").decode("utf-8")
        script = z.read("analisis.py").decode("utf-8")
    assert "abak" not in requisitos.lower().replace("generado por abak", "")
    assert "import abak" not in script


@pytest.mark.slow
def test_el_script_exportado_reproduce_el_resultado_sin_abak():
    """Se corre el .zip en un proceso limpio y se comparan los coeficientes."""
    programa = compilar(FLUJO)
    dentro = ejecutar(programa)
    assert dentro.ok, [n.error for n in dentro.nodos if n.error]
    coefs_dentro = {
        c["variable"]: c["coeficiente"]
        for c in dentro.por_nodo()["m"].artefactos["modelo"]["coeficientes"]
    }
    variable = programa.instrucciones[-1].salidas["modelo"]

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(io.BytesIO(paquete(programa))) as z:
            z.extractall(tmp)
        (Path(tmp) / "sonda.py").write_text(
            "import json, runpy\n"
            "ns = runpy.run_path('analisis.py')\n"
            f"m = ns[{variable!r}]\n"
            "print('__COEFS__' + json.dumps({k: float(v) for k, v in m.params.items()}))\n",
            encoding="utf-8",
        )
        entorno = {k: v for k, v in os.environ.items() if k != "ABAK_DATOS"}
        entorno["PYTHONPATH"] = ""      # abak_core NO está disponible ahí
        proceso = subprocess.run([sys.executable, "sonda.py"], cwd=tmp, env=entorno,
                                 capture_output=True, text=True, timeout=600)

    assert proceso.returncode == 0, proceso.stderr[-3000:]
    linea = next(l for l in proceso.stdout.splitlines() if l.startswith("__COEFS__"))
    coefs_fuera = json.loads(linea[len("__COEFS__"):])

    # `coefs_dentro` viene del artefacto JSON, que redondea a 10 decimales para
    # poder serializarse. Se aplica el MISMO redondeo del otro lado: comparar un
    # valor de presentación contra uno crudo mediría el redondeo, no la
    # reproducibilidad.
    from abak_core.runtime.artefactos import _limpio

    assert set(coefs_dentro) == set(coefs_fuera)
    for variable_, valor in coefs_dentro.items():
        assert valor == _limpio(coefs_fuera[variable_]), (
            f"«{variable_}» difiere entre Abak y el script exportado"
        )


# ---------------------------------------------------------------------------
# Lo mismo, pero con los ayudantes nuevos
# ---------------------------------------------------------------------------

# `FLUJO` cubre MCO, que es el camino mas viejo y mas pisado. Los ayudantes
# recientes —la rejilla de escenarios, el indice hedonico encadenado, el
# criterio de puerta trasera, el muestreo con correccion de poblacion finita—
# viajan al script exportado como funciones sueltas, y ahi es donde un `import`
# olvidado o una dependencia de `abak_core` no se nota: dentro de Abak todo
# existe. Este flujo los saca a los cuatro del edificio a la vez.
FLUJO_NUEVO = grafo("Los ayudantes nuevos, fuera de casa", [
    ("d", "datos.ejemplo", "Hogares", {"conjunto": "hogares"}),
    ("s", "datos.muestra", "Muestra honesta",
     {"n": 1200, "metodo": "estratificado", "estrato": "urbano"}),
    ("c", "causal.efecto", "Efecto de la escolaridad",
     {"arcos": ["escolaridad_anios->gasto_vivienda", "ingreso_mensual->gasto_vivienda",
                "ingreso_mensual->escolaridad_anios", "edad_jefe->ingreso_mensual"],
      "tratamiento": "escolaridad_anios", "resultado": "gasto_vivienda", "errores": "HC1"}),
    ("m", "econometria.mco", "Gasto en vivienda",
     {"y": "gasto_vivienda", "x": ["ingreso_mensual", "escolaridad_anios"], "errores": "HC3"}),
    ("e", "escenarios.simular", "Que pasa si",
     {"variable": "escolaridad_anios", "mover": "ingreso_mensual",
      "puntos": 11, "puntos_mover": 3}),
], [("d", "datos", "s", "datos"), ("s", "datos", "c", "datos"),
    ("s", "datos", "m", "datos"), ("s", "datos", "e", "datos"),
    ("m", "modelo", "e", "modelo")], semilla=11)


def test_los_ayudantes_nuevos_tambien_corren_sin_abak():
    """El .zip de un analisis moderno, en un proceso donde `abak_core` no existe.

    Se comparan numeros de DOS bloques distintos: el efecto causal (que depende
    del ayudante de puerta trasera) y un punto de la rejilla de escenarios. Si
    cualquiera de los dos ayudantes no fuera autosuficiente, el proceso muere
    con un ImportError en vez de dar un numero distinto — y eso tambien falla.
    """
    programa = compilar(FLUJO_NUEVO)
    dentro = ejecutar(programa)
    assert dentro.ok, [n.error for n in dentro.nodos if n.error]
    por_nodo = dentro.por_nodo()

    efecto_dentro = {
        c["variable"]: c["coeficiente"]
        for c in por_nodo["c"].artefactos["modelo"]["coeficientes"]
    }
    proyeccion = por_nodo["e"].artefactos["proyeccion"]
    punto_dentro = proyeccion["series"][0]["y"][5]

    instrucciones = {i.nodo_id: i for i in programa.instrucciones}
    var_efecto = instrucciones["c"].salidas["modelo"]
    var_escenarios = instrucciones["e"].salidas["escenarios"]

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(io.BytesIO(paquete(programa))) as z:
            z.extractall(tmp)
        (Path(tmp) / "sonda.py").write_text(
            "import json, runpy\n"
            "ns = runpy.run_path('analisis.py')\n"
            f"efecto = ns[{var_efecto!r}]\n"
            f"esc = ns[{var_escenarios!r}]\n"
            "primero = esc[esc['escenario'] == esc['escenario'].iloc[0]]\n"
            "print('__SALIDA__' + json.dumps({\n"
            "    'efecto': {k: float(v) for k, v in efecto.params.items()},\n"
            "    'punto': float(primero['prediccion'].iloc[5]),\n"
            "}))\n",
            encoding="utf-8",
        )
        entorno = {k: v for k, v in os.environ.items() if k != "ABAK_DATOS"}
        entorno["PYTHONPATH"] = ""
        proceso = subprocess.run([sys.executable, "sonda.py"], cwd=tmp, env=entorno,
                                 capture_output=True, text=True, timeout=900)

    assert proceso.returncode == 0, proceso.stderr[-3000:]
    linea = next(l for l in proceso.stdout.splitlines() if l.startswith("__SALIDA__"))
    fuera = json.loads(linea[len("__SALIDA__"):])

    from abak_core.runtime.artefactos import _limpio

    assert set(efecto_dentro) == set(fuera["efecto"])
    for variable_, valor in efecto_dentro.items():
        assert valor == _limpio(fuera["efecto"][variable_]), (
            f"el efecto causal de «{variable_}» difiere fuera de Abak")
    assert punto_dentro == _limpio(fuera["punto"]), (
        "la proyección que se ve en pantalla no es la que produce el script exportado")
