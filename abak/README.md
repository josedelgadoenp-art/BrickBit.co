# Abak

Análisis estadístico y econométrico **sin escribir código**, enfocado en economía.

Conectas bloques en un lienzo. Abak compila ese lienzo a un programa de Python
legible y lo ejecuta. El programa generado no es una bitácora de lo que pasó:
**es** lo que pasó, y lo puedes exportar y correr en cualquier máquina sin Abak.

> Vive **al lado** de BrickBit, no dentro: es un producto con su propio ciclo de
> vida, como el Atlas (`atlas/`) y el Motor de Morfogénesis (`app.py`). No se
> publica en Netlify — `netlify.toml` cierra la ruta `/abak/*`.

---

## El problema que resuelve

| | Lo que hace bien | Lo que cuesta |
|---|---|---|
| **R** | Flexibilidad total, gramática de gráficos | Hay que programar |
| **Stata** | Reproducible por `.do`, panel y series impecables | Memoria de sintaxis |
| **EViews** | Series de tiempo con poca fricción | Cerrado, difícil de auditar |
| **SPSS** | Se usa sin saber programar | La reproducibilidad se pierde en los clics |

El eje del que nadie escapa es **usabilidad contra reproducibilidad**. La tesis
de Abak es que ese eje es falso: el grafo visual es la interfaz, el programa de
Python es el artefacto, y **el segundo se compila del primero**.

Quien no quiere programar nunca ve el código. Quien tiene que defender un
resultado exporta un `.py` comentado que corre con pandas y statsmodels.

El diseño completo está en [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Arrancar

Sin Docker, sin Redis, sin Postgres:

```bash
cd abak
make instalar      # venv + dependencias + npm install
make api           # FastAPI en :8000   (Celery corre en proceso)
make web           # Next.js en :3000   (en otra terminal)
```

Abre <http://localhost:3000> y carga un ejemplo desde la barra superior.

Con cola de verdad:

```bash
export ABAK_REDIS=redis://localhost:6379/0
make worker        # en una tercera terminal
```

O todo junto: `docker compose -f infra/docker-compose.yml up`.

---

## Cómo está armado

```
abak/
  ARCHITECTURE.md        el diseño del compilador de nodos
  apps/web/              Next.js · React Flow · Zustand · Tailwind
  services/api/          FastAPI — compila (síncrono) y encola (asíncrono)
  services/worker/       Celery — ejecuta bloque por bloque, publica progreso
  packages/core/         abak_core — Python puro, sin dependencias web
    abak_core/
      graph/             contratos, tipos de puerto, compilador
      registry/          el registro de herramientas
      nodes/             una herramienta = un archivo
      codegen/           IR → AST → script
      runtime/           ejecutor, caché, traducción de errores, exportación
      viz/               gramática de gráficos por capas
  docs/nodos.md          generado del registro (`make docs`)
  ejemplos/              análisis de ejemplo en JSON
  infra/                 docker-compose y Dockerfiles
```

`abak_core` no importa FastAPI ni Celery. Es una regla probada
(`test_nucleo_puro`): si el compilador sólo se pudiera ejercitar levantando un
servidor, en la práctica no se probaría.

---

## Qué trae hoy

**60 herramientas** en 10 familias:

- **Datos** — archivos, ejemplos, filtros, uniones, agrupar, remodelar, declarar serie / panel / ubicación
- **Transformar** — logaritmos, rezagos, crecimiento, deflactar, estandarizar, dummies, winsorizar
- **Explorar** — descriptivos, correlaciones, comparación de grupos
- **Econometría** — MCO con errores robustos (HC1/HC3/HAC/cluster), variables instrumentales, logit/probit con efectos marginales, cuantiles, panel (efectos fijos y aleatorios + Hausman), diagnósticos, VIF
- **Series de tiempo** — ADF y KPSS, ARIMA/SARIMAX con banda de pronóstico, VAR con impulso-respuesta y Granger, Johansen y VECM, filtros de ciclo (HP y Hamilton)
- **Econometría espacial** — matrices de vecindad (KNN, distancia, kernel), I de Moran, LISA, SAR, SEM, pruebas LM para elegir entre los dos
- **Macro e insumo-producto** — Leontief, multiplicadores de producción, empleo e ingreso, encadenamientos de Rasmussen, impacto de un choque de demanda, multiplicador keynesiano
- **Machine learning** — partición honesta, XGBoost, validación de origen móvil, importancias
- **Gráficos** — gramática por capas (lienzo + puntos, línea, barras, área, banda, tendencia, facetas, escalas, tema) renderizada con Plotly
- **Resultados** — tabla de publicación estilo `esttab`, exportar a CSV o Excel

El detalle está en [docs/nodos.md](docs/nodos.md), que se genera del registro.

---

## Tres decisiones que vale la pena conocer

### El código exportado es el que se ejecutó

Cada herramienta implementa **una sola** función, `emit()`, que devuelve
sentencias de Python. No hay un `run()` paralelo. Lo que la interfaz llama
«ejecutar» es `exec()` sobre exactamente los mismos objetos AST que produce el
botón «exportar». La divergencia entre lo que corrió y lo que te enseñamos no
está mitigada: **es imposible de representar**.

Hay una prueba que lo comprueba de punta a punta: exporta el paquete, lo
descomprime en una carpeta temporal y lo corre en un proceso donde `abak_core`
no existe. Los coeficientes salen idénticos.

### Un dato estimado nunca se presenta como hecho

La marca `es_estimado` viaja por el grafo con el esquema de cada tabla. Una
columna que salió de un pronóstico contamina lo que toca, y la interfaz la pinta
en ámbar `#F5C277` hasta en la tabla final. No depende de que alguien se acuerde
de marcarla.

### Cada herramienta se explica

Toda herramienta trae qué hace, cuándo usarla, cómo se lee su resultado, qué
supuestos impone, con qué hay que tener cuidado y cómo se llama en Stata, R,
SPSS o EViews. Una prueba recorre el registro y falla si falta algo de eso. Un
sistema que quiere ser más fácil que SPSS no puede tener herramientas sin
explicar: la explicación es el producto tanto como el cálculo.

---

## Agregar una herramienta

Es escribir un archivo en `packages/core/abak_core/nodes/<familia>/`. Nada más:
no se toca el frontend, ni la API, ni el ejecutor, ni el generador de código.
De ese archivo salen la paleta, el formulario, la verificación de tipos, el
código generado, la invalidación de caché y la documentación.

```python
@registrar
class MiHerramienta(EspecNodo):
    op = "econometria.mi_herramienta"
    familia = "econometria"
    titulo = "Mi herramienta"
    ayuda = Ayuda(que_hace=..., cuando_usarlo=..., interpretacion=...)
    entradas = [Puerto(nombre="datos", tipo="tabla")]
    salidas  = [Puerto(nombre="modelo", tipo="modelo")]

    class Params(BaseModel):
        y: str = CampoColumna()
        x: list[str] = CampoColumnas()

    def emit(self, ctx):
        ctx.importar("statsmodels.api", "sm")
        ctx.emitir("SAL = sm.OLS(ENT[Y], ENT[X]).fit()",
                   SAL=ctx.salida("modelo"), ENT=ctx.entrada("datos"),
                   Y=ctx.plit("y"), X=ctx.plit("x"))
        return ctx.fin()
```

Nunca se construye código con f-strings: se arman nodos AST y los parámetros
entran como constantes. Eso elimina por construcción la inyección de código, y
hay pruebas que lo verifican comparando el árbol del programa generado con
parámetros benignos y hostiles.

---

## Pruebas

```bash
make pruebas          # 234 pruebas
```

Cubren: pureza del núcleo, invariantes del registro (incluida la ayuda de cada
herramienta), tipos de puerto, ciclos, poda, propagación de esquema, nombres de
variable, huellas de caché, inyección de código, ejecución real de las siete
familias de flujos, aislamiento de fallos y reproducibilidad del script
exportado.

---

## Lo que falta

- Persistencia en Postgres, cuentas y colaboración
- Conectores en vivo: INEGI, Banxico (SIE), SHF
- Sandbox por ejecución (gVisor/Firecracker) para multi-tenant
- Nodo de expresión restringida (una expresión de pandas sobre columnas
  conocidas) en lugar del bloque de código libre, que no existe a propósito
