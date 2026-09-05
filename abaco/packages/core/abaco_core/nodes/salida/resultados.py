"""Lo que te llevas: tabla de publicacion y exportacion."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...graph.spec import Esquema
from ...registry.base import (Ayuda, Ayudante, EspecNodo, Puerto, registrar,
                              registrar_ayudante)

registrar_ayudante(Ayudante(
    nombre="tabla_publicacion",
    imports=[("pandas", "pd")],
    fuente='''
def tabla_publicacion(modelos, nombres=None, decimales=3, errores_debajo=True):
    """Varios modelos lado a lado, en el formato de un articulo o una tesis.

    Cada columna es un modelo; cada renglon, una variable. Debajo del
    coeficiente va su error estandar entre parentesis, y las estrellas marcan
    significancia (*** 1%, ** 5%, * 10%).

    Es la salida que en Stata da `esttab`. Se incluye porque una tabla de
    resultados formateada a mano es donde se cuelan los errores de dedo, y
    porque copiar de la consola a Word es como se pierde media tarde.
    """
    nombres = nombres or [f"({i + 1})" for i in range(len(modelos))]
    columnas = {}
    orden_filas = []
    diagnosticos = {}

    for modelo, nombre in zip(modelos, nombres):
        celdas = {}
        params = getattr(modelo, "params", None)
        errores = getattr(modelo, "bse", None)
        pvals = getattr(modelo, "pvalues", None)
        if params is None:
            continue
        for variable in params.index:
            if variable not in orden_filas:
                orden_filas.append(variable)
            coef = float(params[variable])
            p = float(pvals[variable]) if pvals is not None else None
            estrellas = ("***" if p is not None and p < 0.01 else
                         "**" if p is not None and p < 0.05 else
                         "*" if p is not None and p < 0.10 else "")
            celdas[variable] = f"{coef:.{decimales}f}{estrellas}"
            if errores_debajo and errores is not None:
                celdas[f"  {variable} (ee)"] = f"({float(errores[variable]):.{decimales}f})"
                if f"  {variable} (ee)" not in orden_filas:
                    orden_filas.insert(orden_filas.index(variable) + 1, f"  {variable} (ee)")
        columnas[nombre] = celdas
        diagnosticos[nombre] = {
            "Observaciones": f"{int(getattr(modelo, 'nobs', 0)):,}",
            "R²": (f"{float(modelo.rsquared):.3f}" if hasattr(modelo, "rsquared") else ""),
            "R² ajustada": (f"{float(modelo.rsquared_adj):.3f}" if hasattr(modelo, "rsquared_adj") else ""),
            "Errores": str(getattr(modelo, "cov_type", "") or ""),
        }

    cuerpo = pd.DataFrame({n: pd.Series(c) for n, c in columnas.items()}).reindex(orden_filas)
    pie = pd.DataFrame(diagnosticos)
    tabla = pd.concat([cuerpo, pie]).fillna("")
    return tabla.reset_index(names="")
''',
))


@registrar
class TablaPublicacion(EspecNodo):
    op = "salida.tabla_publicacion"
    familia = "salida"
    titulo = "Tabla de resultados (publicacion)"
    prefijo_var = "tabla"
    terminal = True
    ayuda = Ayuda(
        que_hace="Pone varios modelos lado a lado en el formato de un articulo: coeficientes, errores "
                 "estandar entre parentesis, estrellas y el pie con observaciones y R².",
        cuando_usarlo="Cuando ya tienes tus especificaciones y quieres compararlas, o llevartelas a un "
                      "documento sin volver a teclear numeros.",
        interpretacion="Se lee por renglones: como se mueve un coeficiente al cambiar de especificacion. "
                       "Un coeficiente que cambia de signo o de tamano al agregar controles es la senal "
                       "mas util de la tabla.",
        advertencias=["Ensenar solo la especificacion que te gusto es el problema, no la tabla. Reporta "
                      "todas las que corriste."],
        equivalente={"stata": "esttab m1 m2 m3, se star", "r": "stargazer / modelsummary"},
    )
    entradas = [Puerto(nombre="modelos", tipo="modelo", multiple=True, titulo="Modelos",
                       descripcion="Conecta aqui uno o varios modelos")]
    salidas = [Puerto(nombre="tabla", tipo="tabla", titulo="Tabla")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        nombres: list[str] = Field(default_factory=list)
        decimales: int = Field(default=3, ge=1, le=6)
        errores_debajo: bool = True

    def emit(self, ctx: Any) -> Any:
        ctx.usar_ayudante("tabla_publicacion")
        modelos = ctx.entradas_multiples("modelos")
        ctx.nota(f"{len(modelos)} especificacion(es) lado a lado. Estrellas: *** 1%, ** 5%, * 10%.")
        lista = ctx.temporal("modelos")
        ctx.emitir("LISTA = MODELOS", LISTA=lista, MODELOS=ctx.lista(modelos))
        ctx.emitir("SAL = tabla_publicacion(LISTA, nombres=NOM, decimales=DEC, errores_debajo=EE)",
                   SAL=ctx.salida("tabla"), LISTA=lista,
                   NOM=ctx.lit(ctx.p("nombres") or None), DEC=ctx.plit("decimales"),
                   EE=ctx.plit("errores_debajo"))
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {"tabla": Esquema()}


@registrar
class Exportar(EspecNodo):
    op = "salida.exportar"
    familia = "salida"
    titulo = "Exportar tabla"
    prefijo_var = "exportado"
    terminal = True
    cacheable = False
    ayuda = Ayuda(
        que_hace="Guarda la tabla en un archivo para abrirlo en Excel o compartirlo.",
        cuando_usarlo="Al final, cuando el resultado ya se va a usar fuera de Abaco.",
        interpretacion="El archivo queda junto a los resultados de la ejecucion, y se descarga desde la "
                       "pestana Resultados.",
        advertencias=["Si exportas una tabla con columnas estimadas, la marca de ambar se pierde en el "
                      "CSV. Anota en el documento cuales son estimaciones."],
        equivalente={"stata": "export excel", "r": "write.csv()"},
    )
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas = [Puerto(nombre="ruta", tipo="escalar", titulo="Archivo")]

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        nombre_archivo: str = Field(default="resultados")
        formato: Literal["csv", "xlsx"] = "csv"

    def emit(self, ctx: Any) -> Any:
        ctx.importar("os")
        ctx.importar("Path", desde="pathlib")
        nombre = f"{ctx.p('nombre_archivo')}.{ctx.p('formato')}"
        ctx.nota(f"Se escribe «{nombre}» en la carpeta de salida (variable de entorno ABACO_SALIDA, "
                 "o la carpeta actual).")
        ruta = ctx.temporal("ruta")
        ctx.emitir("R = Path(os.environ.get('ABACO_SALIDA', '.')) / NOMBRE",
                   R=ruta, NOMBRE=ctx.lit(nombre))
        ctx.emitir("R.parent.mkdir(parents=True, exist_ok=True)", R=ruta)
        if ctx.p("formato") == "csv":
            ctx.emitir("ENT.to_csv(R, index=False, encoding='utf-8-sig')",
                       ENT=ctx.entrada("datos"), R=ruta)
        else:
            ctx.emitir("ENT.to_excel(R, index=False)", ENT=ctx.entrada("datos"), R=ruta)
        ctx.emitir("SAL = str(R)", SAL=ctx.salida("ruta"), R=ruta)
        return ctx.fin()

    def esquema_salida(self, entradas: dict[str, Esquema], params: BaseModel) -> dict[str, Esquema]:
        return {}
