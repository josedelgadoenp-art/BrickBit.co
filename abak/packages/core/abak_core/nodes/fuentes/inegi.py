"""INEGI — indicadores del BIE/BISE y directorio de establecimientos (DENUE)."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...graph.spec import Columna, Esquema
from ...registry.base import Ayuda, Ayudante, EspecNodo, Puerto, registrar, registrar_ayudante
from .http import clave_cache, dir_fuentes

CLAVE = re.compile(r"^[A-Za-z0-9._-]+$")
AREA = re.compile(r"^[0-9]{4,7}$")

registrar_ayudante(Ayudante(
    nombre="traer_inegi",
    imports=[("os", None), ("pandas", "pd")],
    depende_de=["traer_json", "_validar_claves", "_nombre_cache", "_periodo_inegi"],
    fuente='''
def traer_inegi(indicadores, dir_cache, area="0700", banco="BIE", forzar_red=False, token=None):
    """Indicadores del BIE o del BISE de INEGI -> DataFrame con periodo en el indice.

    El token se lee de INEGI_TOKEN y no se guarda en el analisis. Se pide gratis
    en https://www.inegi.org.mx/app/desarrolladores/generatoken/Usuarios/token_Verify

    `area` es la clave geografica: 0700 es el total nacional; una entidad va
    como 07000009 (CDMX) segun el catalogo del INEGI. `banco` es BIE (series
    economicas) o BISE (indicadores del resto del sistema).
    """
    import pathlib

    claves = _validar_claves(indicadores, que="indicador de INEGI")
    token = token or os.environ.get("INEGI_TOKEN", "")
    archivo = pathlib.Path(dir_cache) / _nombre_cache("inegi", ",".join(claves), area, banco)

    if not archivo.exists() and not token:
        raise ValueError(
            "Falta el token de INEGI y no hay datos en cache. Se pide gratis en "
            "inegi.org.mx (Desarrolladores > Generar token) y va en la variable de entorno "
            "INEGI_TOKEN, o llena la cache con `python tools/traer_datos.py`."
        )

    url = (f"https://www.inegi.org.mx/app/api/indicadores/desarrolladores/jsonxml/INDICATOR/"
           f"{','.join(claves)}/es/{area}/false/{banco}/2.0/{token}?type=json")
    crudo = traer_json(url, archivo, encabezados={"Accept": "application/json"},
                       forzar_red=forzar_red)

    series = crudo.get("Series") or []
    if not series:
        raise ValueError(
            f"INEGI no devolvio series para {claves} en el area {area} del banco {banco}. "
            f"Revisa que el indicador exista en ese banco y en esa cobertura geografica."
        )

    columnas, metadatos = {}, {}
    for serie in series:
        clave = str(serie.get("INDICADOR", "?"))
        observaciones = serie.get("OBSERVATIONS") or []
        metadatos[clave] = {
            "frecuencia": serie.get("FREQ", ""),
            "unidad": serie.get("UNIT", ""),
            "observaciones": len(observaciones),
        }
        if not observaciones:
            continue
        periodos = [_periodo_inegi(o.get("TIME_PERIOD", "")) for o in observaciones]
        valores = pd.to_numeric(
            pd.Series([o.get("OBS_VALUE") for o in observaciones]), errors="coerce")
        columnas[clave] = pd.Series(valores.to_numpy(), index=pd.to_datetime(periodos, errors="coerce"))

    if not columnas:
        raise ValueError("INEGI devolvio las series sin observaciones.")

    marco = pd.DataFrame(columnas).sort_index()
    marco = marco[marco.index.notna()]
    marco.index.name = "fecha"
    marco.attrs["metadatos"] = metadatos
    marco.attrs["fuente"] = f"INEGI — {banco}, area {area}"
    return marco
''',
))

registrar_ayudante(Ayudante(
    nombre="_periodo_inegi",
    fuente='''
def _periodo_inegi(texto):
    """El TIME_PERIOD de INEGI viene en varias formas; se normaliza a fecha.

    '2020' -> 2020-01-01   '2020/03' -> 2020-03-01
    '2020/Q2' -> 2020-04-01 (inicio del trimestre)
    '2020/03/15' -> esa fecha
    """
    texto = str(texto or "").strip()
    if not texto:
        return None
    partes = texto.replace("-", "/").split("/")
    anio = partes[0]
    if len(partes) == 1:
        return f"{anio}-01-01"
    resto = partes[1].upper().lstrip("QT")
    if partes[1].upper().startswith(("Q", "T")):
        try:
            mes = (int(resto) - 1) * 3 + 1
        except ValueError:
            return f"{anio}-01-01"
        return f"{anio}-{mes:02d}-01"
    try:
        mes = int(resto)
    except ValueError:
        return f"{anio}-01-01"
    dia = int(partes[2]) if len(partes) > 2 and partes[2].isdigit() else 1
    return f"{anio}-{min(max(mes, 1), 12):02d}-{min(max(dia, 1), 28):02d}"
''',
))

registrar_ayudante(Ayudante(
    nombre="traer_denue",
    imports=[("os", None), ("pandas", "pd")],
    depende_de=["traer_json", "_nombre_cache"],
    fuente='''
def traer_denue(condicion, latitud, longitud, metros, dir_cache, forzar_red=False, token=None):
    """Establecimientos del DENUE alrededor de un punto -> DataFrame.

    `condicion` es texto de busqueda ('todos', un nombre, o una clave SCIAN).
    `metros` es el radio, con tope de 5000 en la API del INEGI.
    """
    import pathlib
    import urllib.parse

    token = token or os.environ.get("INEGI_TOKEN", "")
    condicion = urllib.parse.quote(str(condicion).strip() or "todos", safe="")
    lat, lng, radio = float(latitud), float(longitud), int(metros)
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError(f"Coordenadas fuera de rango: {lat}, {lng}. En Mexico la longitud es NEGATIVA.")
    radio = max(1, min(radio, 5000))

    archivo = pathlib.Path(dir_cache) / _nombre_cache("denue", condicion, lat, lng, radio)
    if not archivo.exists() and not token:
        raise ValueError("Falta INEGI_TOKEN y no hay datos en cache para esta consulta del DENUE.")

    url = (f"https://www.inegi.org.mx/app/api/denue/v1/consulta/Buscar/"
           f"{condicion}/{lat},{lng}/{radio}/{token}")
    crudo = traer_json(url, archivo, encabezados={"Accept": "application/json"},
                       forzar_red=forzar_red)

    if isinstance(crudo, dict):
        crudo = crudo.get("data") or crudo.get("Data") or []
    if not crudo:
        return pd.DataFrame(columns=["Nombre", "Clase_actividad", "Estrato", "Latitud", "Longitud"])

    marco = pd.DataFrame(crudo)
    for columna in ("Latitud", "Longitud"):
        if columna in marco.columns:
            marco[columna] = pd.to_numeric(marco[columna], errors="coerce")
    marco.attrs["fuente"] = "INEGI — DENUE"
    return marco
''',
))


@registrar
class INEGI(EspecNodo):
    op = "fuentes.inegi"
    familia = "fuentes"
    titulo = "INEGI (BIE / BISE)"
    prefijo_var = "inegi"
    necesita_datos = True
    ayuda = Ayuda(
        que_hace="Descarga indicadores del Banco de Informacion Economica (BIE) o del BISE de INEGI: "
                 "PIB, IGAE, ocupacion, INPC, produccion industrial y cualquier otro por su clave.",
        cuando_usarlo="Cuando necesitas la serie oficial mexicana en vez de una aproximacion.",
        interpretacion="Cada columna es un indicador, con el periodo en el indice. Revisa la frecuencia "
                       "que reporta INEGI: mezclar una serie mensual con una trimestral sin homologarlas "
                       "produce huecos que despues se ven como datos faltantes.",
        supuestos=["Hace falta un token gratuito de INEGI en la variable de entorno INEGI_TOKEN. "
                   "No se guarda en el analisis ni viaja en el codigo exportado.",
                   "El area geografica va por clave del catalogo de INEGI: 0700 es nacional."],
        advertencias=["INEGI rechaza peticiones desde IPs de centros de datos. Es el mismo problema que "
                      "ya tenia el resto del proyecto. Si el servidor no tiene salida, llena la cache "
                      "con `python tools/traer_datos.py` desde una computadora con conexion domestica.",
                      "Una serie descargada queda en cache y el analisis vuelve a usar ESE archivo, para "
                      "que el resultado no cambie solo porque INEGI revisó la serie."],
        referencia="https://www.inegi.org.mx/servicios/api_indicadores.html",
        equivalente={"r": "inegiR::inegi_series()", "stata": "descarga manual"},
    )
    salidas = [Puerto(nombre="datos", tipo="serie", titulo="Indicadores de INEGI")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        indicadores: list[str] = Field(
            default_factory=list,
            json_schema_extra={"abak": {"control": "claves"}},
        )
        area: str = Field(default="0700", description="0700 = nacional. Otras claves, en el catálogo de INEGI.")
        banco: Literal["BIE", "BISE"] = "BIE"
        volver_a_descargar: bool = False

        @field_validator("indicadores")
        @classmethod
        def _claves(cls, v: list[str]) -> list[str]:
            limpias = [c.strip() for c in v if c.strip()]
            for clave in limpias:
                if not CLAVE.match(clave):
                    raise ValueError(f"La clave de indicador «{clave}» tiene caracteres que no se admiten.")
            return limpias

        @field_validator("area")
        @classmethod
        def _area(cls, v: str) -> str:
            if not AREA.match(v.strip()):
                raise ValueError("El area geográfica es una clave numérica del catálogo de INEGI (ej. 0700).")
            return v.strip()

    def _archivo(self, params: BaseModel) -> str:
        return clave_cache("inegi", ",".join(params.indicadores),  # type: ignore[attr-defined]
                           params.area, params.banco)              # type: ignore[attr-defined]

    def archivos(self, params: BaseModel) -> dict[str, str]:
        nombre = self._archivo(params)
        return {f"datos/fuentes/{nombre}": str(dir_fuentes() / nombre)}

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"datos": Esquema(
            indice_temporal="fecha",
            columnas=[Columna(nombre=c, tipo="numerica", fuente=f"INEGI {params.banco}")  # type: ignore[attr-defined]
                      for c in params.indicadores],  # type: ignore[attr-defined]
        )}

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("traer_inegi")
        ctx.nota(f"INEGI {ctx.p('banco')}, area {ctx.p('area')}: indicadores "
                 + ", ".join(ctx.p("indicadores")) + ".")
        ctx.nota("El token se lee de la variable de entorno INEGI_TOKEN; no viaja en este archivo.")
        ctx.emitir(
            "SAL = traer_inegi(IND, RUTA_DATOS / 'fuentes', area=AREA, banco=BANCO, forzar_red=RED)",
            SAL=ctx.salida("datos"), IND=ctx.plit("indicadores"), AREA=ctx.plit("area"),
            BANCO=ctx.plit("banco"), RED=ctx.plit("volver_a_descargar"))
        return ctx.fin()

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        from ...runtime.artefactos import tabla_a_json

        df = salidas.get("datos")
        if df is None:
            return {}
        meta = df.attrs.get("metadatos", {})
        return {
            "datos": tabla_a_json(df, titulo="Indicadores de INEGI"),
            "fuente": {"tipo": "detalle", "titulo": "Lo que devolvio INEGI",
                       "datos": {**{k: f"frecuencia {v['frecuencia']}, {v['observaciones']} obs."
                                    for k, v in meta.items()},
                                 "fuente": df.attrs.get("fuente", ""),
                                 "periodos": len(df)}},
        }


@registrar
class DENUE(EspecNodo):
    op = "fuentes.denue"
    familia = "fuentes"
    titulo = "DENUE (establecimientos)"
    prefijo_var = "denue"
    necesita_datos = True
    ayuda = Ayuda(
        que_hace="Trae los establecimientos economicos que el INEGI tiene registrados alrededor de un "
                 "punto: nombre, actividad, tamano y ubicacion.",
        cuando_usarlo="Para medir la economia de una zona: cuantos negocios hay, de que tipo y de que "
                      "tamano. Es el insumo natural de un analisis de ubicacion.",
        interpretacion="Cada fila es un establecimiento. El «estrato» es un rango de personal ocupado, "
                       "no un numero exacto: el DENUE no publica el empleo puntual de cada negocio.",
        supuestos=["El radio maximo que admite la API es de 5,000 metros."],
        advertencias=["Esta es LA fuente que bloquea IPs de centros de datos: al proyecto ya le pasó con "
                      "la funcion `denue.js`, que quedó inservible por eso. Cuenta con llenar la cache "
                      "desde una computadora con conexion domestica.",
                      "El DENUE se actualiza por oleadas: un establecimiento cerrado puede seguir "
                      "apareciendo, y uno nuevo puede faltar."],
        referencia="https://www.inegi.org.mx/servicios/api_denue.html",
    )
    salidas = [Puerto(nombre="datos", tipo="geotabla", titulo="Establecimientos")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        condicion: str = Field(default="todos", max_length=120,
                               description="«todos», un nombre, o una clave SCIAN")
        latitud: float = Field(default=19.4326, ge=-90, le=90)
        longitud: float = Field(default=-99.1332, ge=-180, le=180)
        metros: int = Field(default=1000, ge=1, le=5000)
        volver_a_descargar: bool = False

    def _archivo(self, params: BaseModel) -> str:
        import urllib.parse

        return clave_cache("denue",
                           urllib.parse.quote(params.condicion.strip() or "todos", safe=""),  # type: ignore[attr-defined]
                           float(params.latitud), float(params.longitud), int(params.metros))  # type: ignore[attr-defined]

    def archivos(self, params: BaseModel) -> dict[str, str]:
        nombre = self._archivo(params)
        return {f"datos/fuentes/{nombre}": str(dir_fuentes() / nombre)}

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        # El DENUE devuelve un catalogo de campos fijo; se declaran los que se usan.
        return {"datos": Esquema(columnas=[
            Columna(nombre="Nombre", tipo="texto", fuente="INEGI DENUE"),
            Columna(nombre="Razon_social", tipo="texto", fuente="INEGI DENUE"),
            Columna(nombre="Clase_actividad", tipo="categorica", fuente="INEGI DENUE"),
            Columna(nombre="Estrato", tipo="categorica", fuente="INEGI DENUE",
                    nota="Rango de personal ocupado, no un conteo exacto."),
            Columna(nombre="Latitud", tipo="numerica", fuente="INEGI DENUE"),
            Columna(nombre="Longitud", tipo="numerica", fuente="INEGI DENUE"),
        ])}

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("traer_denue")
        ctx.nota(f"DENUE: «{ctx.p('condicion')}» en {ctx.p('metros')} m alrededor de "
                 f"({ctx.p('latitud')}, {ctx.p('longitud')}).")
        ctx.emitir(
            "SAL = traer_denue(COND, LAT, LNG, METROS, RUTA_DATOS / 'fuentes', forzar_red=RED)",
            SAL=ctx.salida("datos"), COND=ctx.plit("condicion"), LAT=ctx.plit("latitud"),
            LNG=ctx.plit("longitud"), METROS=ctx.plit("metros"), RED=ctx.plit("volver_a_descargar"))
        return ctx.fin()
