"""
Cliente de HERE: buscar direcciones y poner un mapa de verdad debajo.

QUÉ RESUELVE. La app pedía escribir `19.4326` a mano, que no es algo que nadie
sepa de memoria, y dibujaba las columnas del precio flotando sobre un fondo
negro sin ciudad debajo. Lo primero se arregla geocodificando; lo segundo con
teselas. Las de CARTO —que es lo que trae pydeck por omisión— pasaron a exigir
cuenta (documentado en CLAUDE.md), así que HERE entra también por ahí.

DOS USOS DE LA LLAVE, Y NO SON IGUALES DE SEGUROS.

  · Geocodificar ocurre en el SERVIDOR. La llave no sale de ahí.
  · Las teselas las pide el NAVEGADOR, así que la llave viaja en la URL de cada
    tesela y es visible para cualquiera que abra las herramientas del
    desarrollador. Eso no es un descuido: es como funcionan todas las llaves de
    mapas, incluida la de Google Maps que este repo ya publica a propósito. La
    protección no es esconderla, es RESTRINGIRLA POR DOMINIO en el panel de
    HERE. Si la app se embebe en brickbit.co desde Streamlit Cloud, el dominio
    que HERE va a ver es el de Streamlit, no el de BrickBit: hay que permitir
    ese, y conviene una llave distinta de la del servidor.

DÓNDE VIVE LA LLAVE. En `st.secrets["HERE_API_KEY"]` cuando corre en Streamlit
Cloud, o en la variable de entorno `HERE_API_KEY` en local. **Nunca en el
repositorio** — `netlify.toml` ya cierra `/scripts/*` y `/tools/*` justamente
porque una vez se publicó de más.

SIN LLAVE LA APP NO SE CAE. Todo aquí devuelve None o una lista vacía, y quien
llama enseña el camino de siempre —elegir alcaldía, mapa sin teselas—. Un
buscador de direcciones roto que además tumba la valuación sería peor que no
tenerlo.

⚠ LOS ENDPOINTS NO ESTÁN VERIFICADOS CONTRA EL SERVICIO. El entorno donde se
escribió esto tiene bloqueado `*.hereapi.com` por política de red, así que las
rutas y los nombres de campo salen de la documentación de HERE y no de una
respuesta real. Lo que sí está probado es el comportamiento sin llave y ante
error. Si HERE cambió algo, el síntoma será que no encuentra direcciones —no
que la app reviente— y el mensaje lo dirá.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .config import Config, cargar

GEOCODE = "https://geocode.search.hereapi.com/v1/geocode"
AUTOSUGGEST = "https://autosuggest.search.hereapi.com/v1/autosuggest"
TESELAS = ("https://maps.hereapi.com/v3/base/mc/{z}/{x}/{y}/png8"
           "?apiKey={llave}&style={estilo}&size=512&ppi=400")

# `explore.night` es el estilo oscuro de HERE y es el que casa con la paleta v2
# de BrickBit. `lite.night` es más plano —menos etiquetas, menos ruido— y suele
# leerse mejor cuando encima van columnas de color, que es nuestro caso.
ESTILO = "lite.night"
TIEMPO_LIMITE = 6          # segundos: la app no se queda colgada por HERE


@dataclass(frozen=True)
class Lugar:
    titulo: str
    lat: float
    lng: float

    def __str__(self) -> str:
        return self.titulo


def llave() -> str | None:
    """
    La llave, de donde esté. Nunca del repositorio.

    `st.secrets` primero porque es lo que usa Streamlit Cloud; la variable de
    entorno después para correr en local sin tocar secretos.
    """
    try:
        import streamlit as st

        v = st.secrets.get("HERE_API_KEY")     # type: ignore[union-attr]
        if v:
            return str(v).strip()
    except Exception:                          # noqa: BLE001 — sin streamlit, o sin secrets
        pass
    v = os.environ.get("HERE_API_KEY", "").strip()
    return v or None


def disponible() -> bool:
    return llave() is not None


def url_de_teselas(estilo: str = ESTILO) -> str | None:
    """
    Plantilla XYZ para la capa de teselas, o None si no hay llave.

    Sale con la llave dentro porque la pide el navegador. Ver el encabezado:
    la defensa es la restricción por dominio, no el secreto.
    """
    k = llave()
    if not k:
        return None
    return TESELAS.format(z="{z}", x="{x}", y="{y}", llave=k, estilo=estilo)


def _pedir(url: str) -> dict | None:
    """Una petición GET que NUNCA lanza: la app no se cae por un mapa."""
    try:
        with urllib.request.urlopen(url, timeout=TIEMPO_LIMITE) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            json.JSONDecodeError, OSError, ValueError):
        return None


def _dentro(lat: float, lng: float, cfg: Config) -> bool:
    c = cfg.caja
    return (c.lat_min <= lat <= c.lat_max) and (c.lng_min <= lng <= c.lng_max)


def buscar(texto: str, cfg: Config | None = None, limite: int = 6) -> list[Lugar]:
    """
    Direcciones que coinciden con `texto`, SÓLO dentro de la CDMX.

    El filtro geográfico no es cosmético: el Atlas está entrenado con 1,772
    inmuebles de la Ciudad de México y su malla no existe fuera de ella. Dejar
    que alguien busque una dirección en Monterrey daría una valuación —la fila
    tomaría la celda H3 más cercana, que estaría a cientos de kilómetros— y esa
    cifra sería inventada con apariencia de cálculo. Más vale no encontrarla.

    Devuelve [] si no hay llave, si HERE no responde o si nada cae dentro. Quien
    llama distingue los tres casos con `disponible()` y con la lista vacía.
    """
    cfg = cfg or cargar()
    k = llave()
    t = (texto or "").strip()
    if not k or len(t) < 3:
        return []

    c = cfg.caja
    q = urllib.parse.urlencode({
        "q": t,
        "apiKey": k,
        "in": f"bbox:{c.lng_min},{c.lat_min},{c.lng_max},{c.lat_max}",
        "lang": "es-MX",
        "limit": str(int(limite)),
    })
    datos = _pedir(f"{GEOCODE}?{q}")
    if not datos:
        return []

    salida: list[Lugar] = []
    for it in datos.get("items", []) or []:
        pos = it.get("position") or {}
        try:
            lat, lng = float(pos["lat"]), float(pos["lng"])
        except (KeyError, TypeError, ValueError):
            continue
        # El `in=bbox` de HERE sesga pero no garantiza; se vuelve a filtrar
        # aquí porque de esto depende que no se valúe fuera de la ciudad.
        if not _dentro(lat, lng, cfg):
            continue
        salida.append(Lugar(str(it.get("title") or t), lat, lng))
    return salida


def sugerir(texto: str, cfg: Config | None = None, limite: int = 6) -> list[Lugar]:
    """
    Autosuggest: lo mismo, pensado para teclear.

    OJO CON LA CUOTA. Autosuggest está hecho para dispararse en cada tecla, y
    ahí es donde se va el presupuesto de un plan gratuito: una dirección de
    treinta caracteres son treinta peticiones. La app lo llama al ENVIAR, no al
    teclear, y por eso esto se parece tanto a `buscar`. Si algún día se quiere
    el desplegable en vivo, hay que meter un retardo y memoria antes, no
    después.
    """
    cfg = cfg or cargar()
    k = llave()
    t = (texto or "").strip()
    if not k or len(t) < 3:
        return []

    c = cfg.caja
    centro_lat = (c.lat_min + c.lat_max) / 2
    centro_lng = (c.lng_min + c.lng_max) / 2
    q = urllib.parse.urlencode({
        "q": t,
        "apiKey": k,
        "at": f"{centro_lat},{centro_lng}",
        "in": f"bbox:{c.lng_min},{c.lat_min},{c.lng_max},{c.lat_max}",
        "lang": "es-MX",
        "limit": str(int(limite)),
    })
    datos = _pedir(f"{AUTOSUGGEST}?{q}")
    if not datos:
        return []
    salida: list[Lugar] = []
    for it in datos.get("items", []) or []:
        pos = it.get("position") or it.get("access", [{}])[0] or {}
        try:
            lat, lng = float(pos["lat"]), float(pos["lng"])
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        if not _dentro(lat, lng, cfg):
            continue
        salida.append(Lugar(str(it.get("title") or t), lat, lng))
    return salida
