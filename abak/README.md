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

## Volúmenes grandes: lo que está medido

Los números de abajo se midieron en este repositorio, con un CSV de **2 millones
de filas × 40 columnas (553 MB)**, en un contenedor de 2 vCPU. No son
estimaciones.

| Paso | Tiempo | Pico de RAM |
|---|---:|---:|
| Subir y convertir a columnar (por trozos) | 49 s | 385 MB |
| Análisis completo: leer → log → MCO robusto | 4.1 s | 770 MB |
| Informe en PDF de ese análisis | 1 s | — |

553 MB de CSV quedan en 318 MB de Parquet. Los coeficientes salieron idénticos
a calcularlos a mano con pandas y statsmodels, hasta el último dígito que
guarda el artefacto.

Tres cosas hacen que eso funcione:

**Se lee sólo lo que el análisis usa.** El compilador ya sabe qué columnas
nombra cada bloque, así que el nodo de carga emite `columns=[...]` con esa
lista. En ese archivo de 40 columnas, el análisis usaba 3: leer las otras 37
sólo habría gastado memoria. Sale gratis, porque la información ya estaba en el
grafo.

La poda se apaga sola en cuanto **un** bloque puede tocar columnas que no
nombró —«Descriptivos» sin lista resume todas las numéricas, «Exportar tabla»
escribe la tabla completa—. Se prefiere gastar memoria a cambiar un resultado
en silencio. Hay una prueba que corre el mismo análisis con y sin poda y exige
que los coeficientes sean idénticos.

**Los tipos se fijan antes de leer, no trozo por trozo.** Es un asunto de
corrección, no de memoria: si `pandas` infiere por trozo, una columna que en
las primeras 500 mil filas sólo trae enteros se lee `int64`, y cuando en la
fila 800 mil aparece un decimal, ese trozo se lee `float64`. Queda una columna
de tipo mixto que falla raro y sin avisar. Abak hace una pasada de muestreo,
fija el tipo de cada columna y lee todo con ese tipo.

**Los enteros se reducen; los flotantes no.** Un año o una edad caben en 16
bits. Los `float64` **se quedan en 64 bits**: `float32` tiene ~7 dígitos
significativos y una suma de un millón de valores acumula error visible. En un
sistema que va a hacer econometría, cambiar precisión por memoria es un mal
canje.

### Dónde están los límites hoy

- **La subida pasa por la API.** Un archivo de 2 GB tarda y ocupa el proceso
  mientras llega. Para archivos así, lo correcto es subir directo al almacén de
  objetos con una URL firmada y avisar a la API cuando terminó. Está anotado,
  no construido.
- **Excel se lee completo en memoria.** Es una limitación del formato, no del
  código. El nodo lo dice al subir el archivo.
- **Todo cabe en una máquina.** No hay ejecución distribuida. Para decenas de
  millones de filas con modelos pesados, el siguiente paso es un motor
  fuera-de-memoria (DuckDB o Polars con streaming) detrás de los mismos nodos;
  el compilador no cambiaría.

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
make pruebas          # 297 pruebas
```

Cubren: pureza del núcleo, invariantes del registro (incluida la ayuda de cada
herramienta), tipos de puerto, ciclos, poda de ramas muertas, propagación de
esquema, nombres de variable, huellas de caché, inyección de código, ejecución
real de las ocho familias de flujos, aislamiento de fallos y reproducibilidad
del script exportado.

Y, específicamente para lo que este sistema tiene que sostener:

- **Precisión** (`test_numerico.py`): MCO contra la solución analítica y contra
  (X'X)⁻¹X'y calculada aparte; la inversa de Leontief contra una matriz de 2×2
  resuelta con lápiz; la identidad x = (I−A)⁻¹f; el multiplicador keynesiano
  contra su fórmula; Moran contra patrones construidos con la respuesta puesta;
  y que dos corridas con la misma semilla den lo mismo hasta el último dígito.
- **Volumen** (`test_grandes.py`): que los tipos no se mezclen entre trozos, que
  la conversión a columnar no mueva ni un valor, que la poda de columnas **no
  cambie el resultado**, y que se apague sola cuando no es segura.
- **Fuentes** (`test_fuentes.py`): el parseo de cada API con sus rarezas reales,
  que el token no llegue nunca al código exportado, y que una clave hostil no
  entre a una URL.
- **Informe** (`test_informe.py`): que el PDF se genere igual cuando falta
  Chrome, porque una dependencia opcional no puede tumbar el entregable.

---

## Lo que falta

- Persistencia en Postgres, cuentas y colaboración
- Conectores en vivo: INEGI, Banxico (SIE), SHF
- Sandbox por ejecución (gVisor/Firecracker) para multi-tenant
- Nodo de expresión restringida (una expresión de pandas sobre columnas
  conocidas) en lugar del bloque de código libre, que no existe a propósito
