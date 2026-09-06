"""Banxico — Sistema de Informacion Economica (SIE)."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...graph.spec import Columna, Esquema
from ...registry.base import Ayuda, Ayudante, EspecNodo, Puerto, registrar, registrar_ayudante
from .http import clave_cache, dir_fuentes

CLAVE = re.compile(r"^[A-Za-z0-9._-]+$")

# Series que la gente pide todo el tiempo. Se ofrecen como atajo, PERO el nodo
# siempre reporta el titulo oficial que devuelve Banxico: si una clave cambio o
# esta mal, se ve en pantalla en vez de pasar inadvertida.
SUGERIDAS: dict[str, str] = {
    "SF43718": "Tipo de cambio FIX (pesos por dolar)",
    "SF43783": "TIIE a 28 dias",
    "SF61745": "Tasa objetivo de Banxico",
    "SP1": "INPC general (base 2018)",
    "SP74665": "Inflacion anual del INPC",
    "SR16734": "IGAE (indicador global de la actividad economica)",
}

registrar_ayudante(Ayudante(
    nombre="traer_banxico",
    imports=[("os", None), ("pandas", "pd")],
    depende_de=["traer_json", "_validar_claves", "_nombre_cache"],
    fuente='''
def traer_banxico(series, dir_cache, inicio=None, fin=None, forzar_red=False, token=None):
    """Series del SIE de Banxico -> DataFrame con la fecha en el indice.

    El token se lee de la variable de entorno BANXICO_TOKEN y NUNCA se guarda
    en el analisis ni en este script: es una credencial personal.
    Se consigue gratis en https://www.banxico.org.mx/SieAPIRest/service/v1/token

    El titulo que devuelve Banxico para cada serie se guarda en
    `df.attrs["titulos"]`, para poder mostrarlo: si una clave esta mal, se nota.
    """
    import pathlib

    claves = _validar_claves(series, que="serie de Banxico")
    token = token or os.environ.get("BANXICO_TOKEN", "")

    rango = f"/{inicio}/{fin}" if (inicio and fin) else ""
    url = (f"https://www.banxico.org.mx/SieAPIRest/service/v1/series/"
           f"{','.join(claves)}/datos{rango}")

    archivo = pathlib.Path(dir_cache) / _nombre_cache("banxico", ",".join(claves), inicio, fin)
    if not archivo.exists() and not token:
        raise ValueError(
            "Falta el token de Banxico y no hay datos en cache. Consigue uno gratis en "
            "banxico.org.mx (SieAPIRest) y ponlo en la variable de entorno BANXICO_TOKEN, "
            "o llena la cache con `python tools/traer_datos.py`."
        )

    crudo = traer_json(url, archivo, encabezados={"Bmx-Token": token, "Accept": "application/json"},
                       forzar_red=forzar_red)

    series_json = (crudo.get("bmx") or {}).get("series") or []
    if not series_json:
        raise ValueError(f"Banxico no devolvio ninguna serie para {claves}. Revisa las claves.")

    columnas, titulos = {}, {}
    for serie in series_json:
        clave = serie.get("idSerie", "?")
        titulos[clave] = serie.get("titulo", "")
        observaciones = serie.get("datos") or []
        if not observaciones:
            continue
        fechas = pd.to_datetime([o["fecha"] for o in observaciones], format="%d/%m/%Y",
                                errors="coerce")
        # Banxico manda "N/E" cuando no hay dato, y separadores de miles.
        valores = pd.to_numeric(
            pd.Series([str(o.get("dato", "")).replace(",", "") for o in observaciones])
            .replace({"N/E": None, "": None}),
            errors="coerce")
        columnas[clave] = pd.Series(valores.to_numpy(), index=fechas)

    if not columnas:
        raise ValueError("Banxico devolvio las series sin observaciones para ese rango de fechas.")

    marco = pd.DataFrame(columnas).sort_index()
    marco.index.name = "fecha"
    marco.attrs["titulos"] = titulos
    marco.attrs["fuente"] = "Banxico — Sistema de Informacion Economica (SIE)"
    return marco
''',
))

registrar_ayudante(Ayudante(
    nombre="_nombre_cache",
    imports=[("hashlib", None)],
    fuente='''
def _nombre_cache(fuente, *partes):
    """Nombre de archivo estable para una peticion. No incluye el token."""
    crudo = "|".join(str(p) for p in partes)
    return f"{fuente}_{hashlib.sha256(crudo.encode('utf-8')).hexdigest()[:24]}.json"
''',
))


@registrar
class Banxico(EspecNodo):
    op = "fuentes.banxico"
    familia = "fuentes"
    titulo = "Banxico (SIE)"
    prefijo_var = "banxico"
    necesita_datos = True
    ayuda = Ayuda(
        que_hace="Descarga series del Sistema de Informacion Economica de Banxico: tipo de cambio, "
                 "TIIE, tasa objetivo, INPC, IGAE y cualquier otra por su clave.",
        cuando_usarlo="Cuando el analisis necesita datos macro reales y actuales, en vez de un ejemplo.",
        interpretacion="El resultado es una tabla con la fecha en el indice y una columna por serie. "
                       "Abajo se muestra el TITULO OFICIAL que devolvio Banxico para cada clave: "
                       "si no es el que esperabas, la clave esta mal.",
        supuestos=["Hace falta un token gratuito del SIE en la variable de entorno BANXICO_TOKEN. "
                   "El token no se guarda en el analisis ni viaja en el codigo exportado."],
        advertencias=["Banxico rechaza peticiones desde IPs de centros de datos. Si el servidor no "
                      "tiene salida, corre `python tools/traer_datos.py` desde una computadora con "
                      "conexion domestica: llena la cache y el servidor deja de necesitar red.",
                      "La primera descarga se guarda en cache y el analisis vuelve a usar ESE archivo. "
                      "Es a proposito: un resultado no debe cambiar solo porque la fuente revisó la "
                      "serie. Para traer datos nuevos, marca «volver a descargar».",
                      "Las claves sugeridas son un atajo, no un catalogo verificado: confirma siempre "
                      "el titulo que aparece en el resultado."],
        referencia="https://www.banxico.org.mx/SieAPIRest/service/v1/doc/catalogoSeries",
        equivalente={"stata": "import delimited (descarga manual)", "r": "siebanxicor::getSeriesData()"},
    )
    salidas = [Puerto(nombre="datos", tipo="serie", titulo="Series de Banxico")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        series: list[str] = Field(
            default=["SF43718"],
            json_schema_extra={"abak": {"control": "claves", "sugerencias": SUGERIDAS}},
        )
        inicio: str | None = Field(default=None, description="AAAA-MM-DD. Vacio = toda la historia.")
        fin: str | None = Field(default=None, description="AAAA-MM-DD")
        volver_a_descargar: bool = Field(
            default=False,
            description="Ignora la cache y vuelve a pedir a Banxico. Cambia los resultados.",
        )

        @field_validator("series")
        @classmethod
        def _claves_limpias(cls, v: list[str]) -> list[str]:
            for clave in v:
                if not CLAVE.match(clave.strip()):
                    raise ValueError(
                        f"La clave «{clave}» tiene caracteres que no se admiten. "
                        "Las claves del SIE son del estilo SF43718.")
            return [c.strip() for c in v if c.strip()]

        @field_validator("inicio", "fin")
        @classmethod
        def _fecha_iso(cls, v: str | None) -> str | None:
            if v and not re.match(r"^\d{4}-\d{2}-\d{2}$", v.strip()):
                raise ValueError("La fecha va en formato AAAA-MM-DD.")
            return v.strip() if v else None

    def _archivo(self, params: BaseModel) -> str:
        return clave_cache("banxico", ",".join(params.series),  # type: ignore[attr-defined]
                           params.inicio, params.fin)           # type: ignore[attr-defined]

    def archivos(self, params: BaseModel) -> dict[str, str]:
        nombre = self._archivo(params)
        return {f"datos/fuentes/{nombre}": str(dir_fuentes() / nombre)}

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        # Las columnas se conocen sin descargar nada: son las claves pedidas.
        # Por eso los desplegables de los nodos de aguas abajo ya funcionan.
        return {"datos": Esquema(
            indice_temporal="fecha",
            columnas=[Columna(nombre=c, tipo="numerica",
                              fuente="Banxico (SIE)", nota=SUGERIDAS.get(c))
                      for c in params.series],  # type: ignore[attr-defined]
        )}

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("traer_banxico")
        series = ctx.p("series")
        ctx.nota("Banxico (SIE): " + ", ".join(
            f"{c} — {SUGERIDAS.get(c, 'serie ' + c)}" for c in series) + ".")
        ctx.nota("El token se lee de la variable de entorno BANXICO_TOKEN; no viaja en este archivo.")
        if ctx.p("volver_a_descargar"):
            ctx.nota("ATENCION: se ignora la cache y se vuelve a pedir. Los numeros pueden cambiar "
                     "respecto a la corrida anterior si Banxico revisó la serie.")
        else:
            ctx.nota("Si el archivo ya esta en datos/fuentes/, se usa ese y no se toca la red: "
                     "es lo que hace que este analisis se pueda repetir.")
        ctx.emitir(
            "SAL = traer_banxico(SERIES, RUTA_DATOS / 'fuentes', inicio=INI, fin=FIN, forzar_red=RED)",
            SAL=ctx.salida("datos"), SERIES=ctx.plit("series"),
            INI=ctx.plit("inicio"), FIN=ctx.plit("fin"), RED=ctx.plit("volver_a_descargar"))
        return ctx.fin()

    def resumir(self, salidas: dict[str, Any], params: BaseModel) -> dict[str, Any]:
        from ...runtime.artefactos import tabla_a_json

        df = salidas.get("datos")
        if df is None:
            return {}
        titulos = df.attrs.get("titulos", {})
        return {
            "datos": tabla_a_json(df, titulo="Series de Banxico"),
            "fuente": {"tipo": "detalle", "titulo": "Lo que devolvio Banxico",
                       "datos": {**titulos,
                                 "fuente": df.attrs.get("fuente", ""),
                                 "periodos": len(df),
                                 "desde": str(df.index.min())[:10] if len(df) else "—",
                                 "hasta": str(df.index.max())[:10] if len(df) else "—"}},
        }
