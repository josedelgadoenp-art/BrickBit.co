"""Traer datos de fuentes oficiales, con cache de contenido.

El problema real de este modulo no es la API: es que **Banxico e INEGI
rechazan las peticiones que vienen de IPs de centros de datos**. Ya le pasaba
al resto del proyecto (por eso `tools/macro_local.py` y `tools/riesgos_local.py`
se corren en la maquina de uno). Un conector que solo sepa pedir por red se cae
en produccion el primer dia.

Por eso hay UNA sola ruta de codigo, y empieza por la cache:

    1. ¿esta el archivo en `RUTA_DATOS/fuentes/`?  -> se usa, sin tocar la red
    2. si no  -> se pide a la API y se guarda ahi
    3. si la red falla -> se explica que hacer, no se muere con un stacktrace

Consecuencias que valen la pena:

  · el paquete exportado lleva la cache dentro, asi que el script reproduce
    EXACTAMENTE los mismos numeros aunque la serie se revise despues;
  · `python tools/traer_datos.py` puede llenar la cache desde una maquina con
    IP domestica, y a partir de ahi el worker en la nube ya no necesita red;
  · nadie tiene que escribir dos versiones del nodo.

Los tokens NUNCA entran al grafo ni al script: se leen del entorno.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from ...registry.base import Ayudante, registrar_ayudante

#: Cache de fuentes que sobrevive entre ejecuciones. El worker la sincroniza
#: con el directorio de cada corrida antes y despues de ejecutar.
def dir_fuentes() -> Path:
    ruta = os.environ.get("ABAK_FUENTES")
    if ruta:
        return Path(ruta)
    return Path(os.environ.get("ABAK_INICIO", ".abak")) / "fuentes"


def clave_cache(fuente: str, *partes: object) -> str:
    """Nombre de archivo estable y legible para una peticion.

    Se deriva del contenido de la peticion, nunca del token: dos personas con
    tokens distintos comparten la misma cache, que es lo correcto — los datos
    son los mismos.
    """
    crudo = "|".join(str(p) for p in partes)
    return f"{fuente}_{hashlib.sha256(crudo.encode('utf-8')).hexdigest()[:24]}.json"


registrar_ayudante(Ayudante(
    nombre="traer_json",
    imports=[("json", None), ("os", None), ("urllib.error", None), ("urllib.request", None),
             ("pathlib", None)],
    fuente='''
def traer_json(url, archivo_cache, encabezados=None, tiempo_limite=90, forzar_red=False):
    """Devuelve JSON de una API, con cache en disco. Cache primero, red despues.

    `archivo_cache` es una ruta. Si existe y no se pidio `forzar_red`, se lee de
    ahi y no se toca la red: es lo que hace que un analisis exportado reproduzca
    los mismos numeros meses despues, aunque la fuente revise la serie.

    Usa solo la biblioteca estandar a proposito: el script exportado no debe
    necesitar `requests` para volver a correr.
    """
    ruta = pathlib.Path(archivo_cache)
    if ruta.exists() and not forzar_red:
        return json.loads(ruta.read_text(encoding="utf-8"))

    peticion = urllib.request.Request(url, headers=encabezados or {})
    try:
        with urllib.request.urlopen(peticion, timeout=tiempo_limite) as respuesta:
            crudo = respuesta.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        cuerpo = ""
        try:
            cuerpo = exc.read().decode("utf-8", "replace")[:400]
        except Exception:
            pass
        if exc.code in (401, 403):
            raise ValueError(
                f"La fuente rechazo la peticion ({exc.code}). Dos causas, por orden de "
                f"frecuencia: (1) falta el token o esta mal — revisa la variable de entorno; "
                f"(2) la fuente bloquea las IPs de centros de datos, que es lo que le pasa a "
                f"Banxico y a INEGI. En el segundo caso corre `python tools/traer_datos.py` "
                f"desde una computadora con conexion domestica: llena esta misma cache y el "
                f"servidor ya no necesita red. Respuesta: {cuerpo}"
            ) from exc
        raise ValueError(f"La fuente respondio {exc.code}. {cuerpo}") from exc
    except Exception as exc:
        raise ValueError(
            f"No se pudo contactar a la fuente ({type(exc).__name__}). Si el servidor no tiene "
            f"salida a internet, llena la cache con `python tools/traer_datos.py` desde una "
            f"maquina que si la tenga y vuelve a ejecutar."
        ) from exc

    datos = json.loads(crudo)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(crudo, encoding="utf-8")
    return datos
''',
))


registrar_ayudante(Ayudante(
    nombre="_validar_claves",
    fuente='''
def _validar_claves(claves, que="serie"):
    """Las claves entran a una URL: solo letras, digitos, guiones y puntos.

    Sin esto, una clave con `../` o con `?` podria redirigir la peticion a otro
    lado. Se valida aqui, dentro del ayudante, y no solo en el compilador,
    porque el script exportado corre sin el compilador.
    """
    limpias = []
    for clave in claves:
        texto = str(clave).strip()
        if not texto:
            continue
        if not all(c.isalnum() or c in "-_." for c in texto):
            raise ValueError(
                f"La clave de {que} '{texto}' tiene caracteres que no se admiten. "
                f"Solo letras, digitos, '-', '_' y '.'."
            )
        limpias.append(texto)
    if not limpias:
        raise ValueError(f"No se indico ninguna clave de {que}.")
    return limpias
''',
))
