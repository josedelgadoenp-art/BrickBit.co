# Abak — Arquitectura

**Abak** es un sistema de análisis estadístico y econométrico sin código. El usuario
conecta bloques en un lienzo; el sistema compila ese lienzo a un programa de Python
legible y lo ejecuta. El programa generado no es una bitácora de lo que pasó: **es**
lo que pasó.

Este documento describe el sistema completo, con énfasis en el compilador de nodos,
que es la pieza de la que cuelga todo lo demás.

Idioma del producto: español (MX). Idioma del código: inglés para identificadores
de infraestructura, español para el dominio (`nodos`, `pesos`, `formula`), porque el
código generado lo va a leer un economista, no un ingeniero.

---

## 1. La tesis

Los cuatro sistemas que Abak toma como referencia resolvieron cosas distintas:

| Sistema | Lo que hace bien | Lo que cuesta |
|---|---|---|
| **R** | Flexibilidad total, gramática de gráficos, 20k paquetes | Hay que programar; la calidad del paquete varía |
| **Stata** | Reproducibilidad por `.do`, econometría de panel y series impecable | Comando por comando, memoria de sintaxis |
| **EViews** | Series de tiempo y VAR con muy poca fricción | Cerrado, débil fuera de macro, difícil de auditar |
| **SPSS** | Menús: se usa sin saber programar | La reproducibilidad se pierde en los clics; el rigor se diluye |

El eje del que nadie escapa es **usabilidad contra reproducibilidad**. SPSS ganó
usabilidad y perdió el rastro de lo que hizo. R y Stata ganaron el rastro y pusieron
la barrera de la sintaxis.

La tesis de Abak es que ese eje es falso, y que el punto donde se rompe es este:

> **El grafo visual es la interfaz. El programa de Python es el artefacto.
> No son dos representaciones de lo mismo: el grafo se compila al programa,
> y el programa es lo único que se ejecuta.**

Quien no quiere programar, nunca ve el código. Quien tiene que defender un resultado
ante un comité, un árbitro o un regulador, exporta un `.py` de 200 líneas comentadas
que corre en cualquier máquina con pandas y statsmodels, sin Abak de por medio.

---

## 2. La decisión central: el *shadow code* es la ejecución

Casi todos los sistemas visuales que generan código tienen dos caminos: uno que
ejecuta el análisis y otro que escribe el código "equivalente" para enseñárselo al
usuario. Los dos caminos **divergen**. Alguien arregla un borde en el ejecutor, no lo
refleja en el generador, y a partir de ahí el código exportado miente. Y el error es
silencioso: se descubre meses después, cuando alguien corre el script y le da otro
número.

Abak no tiene dos caminos:

```
                         ┌──────────────────────────────┐
   Grafo  ──compila──▶   │   Programa de Python (AST)   │
                         └──────────────┬───────────────┘
                                        │
                        ┌───────────────┴───────────────┐
                        ▼                               ▼
              ejecutar el programa              exportar el programa
              (exec por bloques)                  (ast.unparse → .py)
```

Cada nodo implementa **una sola** función: `emit()`, que devuelve sentencias de
Python. No existe un `run()` paralelo. Lo que la interfaz llama "ejecutar" es
`exec()` sobre exactamente los mismos objetos AST que produce el botón "exportar".
La divergencia no está mitigada: es **imposible de representar**.

### 2.1 Cómo salen los resultados si el código es puro

Si el código emitido es analítico y limpio (`modelo_1 = sm.OLS(y, X).fit()`), sin
instrumentación, ¿cómo obtiene la interfaz la tabla de coeficientes?

Por **cosecha de nombres**, no por instrumentación. El compilador sabe que el puerto
de salida `modelo` del nodo `n7` quedó ligado a la variable `modelo_1`. Después del
`exec`, el runtime lee `espacio_nombres["modelo_1"]`. El código no sabe que lo están
observando.

Después, y **fuera** del programa generado, un `resumir()` por tipo de nodo convierte
ese objeto en un artefacto JSON para la interfaz (tabla de coeficientes, diagnósticos,
figura). Esa función es presentación pura: no puede alterar el análisis, y por lo
tanto no puede causar divergencia. Es la única asimetría entre ejecutar y exportar, y
está del lado inocuo.

| | Ejecutar | Exportar |
|---|---|---|
| Preludio (imports, semillas, ayudantes) | idéntico | idéntico |
| Cuerpo analítico | idéntico | idéntico |
| Cómo se ven los resultados | `exec` + cosecha de nombres | `print()` / `fig.show()` al final |

### 2.2 El script exportado es autónomo

Un nodo complejo (construir una matriz de pesos espaciales, un pronóstico recursivo)
no cabe razonablemente como AST en línea. La salida tentadora es que el script importe
`abak_runtime` — y entonces deja de ser portable, porque exige instalar Abak.

En vez de eso, el registro declara **ayudantes** (`Helper`): funciones de Python
independientes con su propio código fuente y sus propias dependencias. El compilador
emite en el preludio **sólo los ayudantes que el grafo realmente usa**, en orden
topológico de dependencia entre ellos. El resultado es un `.py` que sólo necesita
`pandas`, `statsmodels` y las bibliotecas del análisis en cuestión. Abak no aparece
en el archivo.

---

## 3. Vista de sistemas

```
┌────────────────────────────────────────────────────────────────────┐
│  apps/web — Next.js (App Router)                                   │
│  React Flow (lienzo) · Zustand (estado) · TailwindCSS              │
│  Pestañas: Lienzo · Datos · Resultados · Gráficos · Código · Bitácora│
│  La paleta de nodos NO está escrita en el frontend: se descarga    │
│  de GET /api/v1/registro                                           │
└───────────────┬────────────────────────────────────────────────────┘
                │  HTTP/JSON  (contratos Pydantic → JSON Schema → TS)
┌───────────────▼────────────────────────────────────────────────────┐
│  services/api — FastAPI                                            │
│  /registro  /grafos  /ejecuciones  /datos  /artefactos  /codigo    │
│  Valida el grafo y COMPILA de forma síncrona (es milisegundos).    │
│  Encola la EJECUCIÓN (que sí puede tardar minutos).                │
└───────────────┬────────────────────────────────────────────────────┘
                │  Celery (broker Redis, backend Redis)
┌───────────────▼────────────────────────────────────────────────────┐
│  services/worker — Celery                                          │
│  Ejecuta el programa bloque por bloque, publica progreso por nodo, │
│  guarda artefactos y valores intermedios.                          │
└───────────────┬────────────────────────────────────────────────────┘
                │
┌───────────────▼────────────────────────────────────────────────────┐
│  packages/core — abak_core   (Python puro, sin dependencias web)  │
│  graph · registry · nodes · codegen · runtime · viz                │
│  Se puede usar como biblioteca, sin API ni frontend.               │
└────────────────────────────────────────────────────────────────────┘
```

`abak_core` no importa FastAPI ni Celery. Esa regla se prueba (`test_core_puro`):
el núcleo tiene que poder compilarse y correrse desde un cuaderno o un `python -m`,
porque de otro modo no hay forma honesta de probar el compilador.

---

## 4. El compilador de nodos

Siete etapas. Las cuatro primeras son de milisegundos y corren en la API en cada
cambio del lienzo (es lo que alimenta la pestaña **Código** en vivo, y los subrayados
rojos sobre los nodos mal configurados). Las tres últimas corren en el worker.

```
  ①            ②           ③          ④           ⑤          ⑥         ⑦
Parsear → Resolver → Verificar → Planear → Bajar a IR → Emitir → Ejecutar
 JSON     registro     tipos       DAG                   AST     por bloques
```

### ① Parsear — JSON de React Flow → `GrafoSpec`

El frontend manda su propio JSON (React Flow trae `position`, `selected`, `dragging`,
estilos...). El parser conserva **sólo lo semántico** y descarta lo visual, salvo
`position`, que se guarda aparte para volver a dibujar el lienzo.

```python
class NodoSpec(BaseModel):
    id: str
    op: str                      # "econometria.mco"
    etiqueta: str | None         # nombre que le puso el usuario
    params: dict[str, Any]       # sin validar todavía
    posicion: Posicion

class AristaSpec(BaseModel):
    origen: str; puerto_origen: str
    destino: str; puerto_destino: str

class GrafoSpec(BaseModel):
    version_esquema: Literal["1"]
    nodos: list[NodoSpec]
    aristas: list[AristaSpec]
```

Que el contrato sea `GrafoSpec` y no "lo que mande React Flow" es lo que permite
cambiar de biblioteca de lienzo sin tocar el backend.

### ② Resolver — buscar cada `op` en el registro

Cada `op` se busca en el registro de nodos. Se obtiene su `EspecNodo`: puertos de
entrada y salida con sus tipos, esquema de parámetros, ayudantes que necesita,
imports, versión y **ayuda en español**.

Aquí los parámetros dejan de ser `dict[str, Any]`: se validan contra el modelo
Pydantic del nodo y se les aplican los valores por omisión. Un parámetro que no
valida es un error localizado (`nodo n7, parámetro "rezagos": debe ser ≥ 1`), no una
excepción a 40 marcos de profundidad.

### ③ Verificar tipos — la red que atrapa el 80% de los errores

Los puertos tienen tipo. Los tipos forman una jerarquía pequeña:

```
        cualquiera
             │
    ┌────────┼─────────┬────────┬───────┬────────┬───────┐
  tabla   modelo     pesos     mio    capa   figura  escalar
    │
 ┌──┴───┬──────────┐
serie  panel   geotabla
```

`serie`, `panel` y `geotabla` **son** tablas (en pandas todas son `DataFrame`), así
que un puerto que pide `tabla` acepta las tres. Al revés no: el nodo VAR pide `serie`
y una tabla cruda no le sirve — hay que pasar antes por *Definir serie temporal*.
Eso no es burocracia: es la diferencia entre un VAR con índice temporal y un VAR sobre
filas en desorden, que es un error que en EViews se comete callado.

Se verifica además:
- que no queden puertos **obligatorios** sin conectar,
- que no haya dos aristas al mismo puerto de entrada (salvo puertos `multiple=True`,
  que es como se apilan las capas de un gráfico),
- que los nombres de columna en los parámetros **existan en el esquema de la tabla
  que llega por el puerto**. Esto exige propagar el esquema por el grafo (§4.1).

### ③.1 Propagación de esquema

Antes de ejecutar nada, el compilador propaga por el DAG el **esquema** de cada
tabla: nombres de columna, tipo (numérico / categórico / fecha), y marcas
(`es_indice_temporal`, `es_id_entidad`, `es_estimado`). Cada nodo declara
`esquema_salida(esquema_entrada, params)`.

Esto vale mucho más de lo que cuesta:

- El desplegable de "variable dependiente" muestra **las columnas que de verdad hay
  en ese punto del grafo**, no las del archivo original. Es la razón por la que este
  sistema se puede usar sin manual.
- Cambiar un nodo aguas arriba invalida los nombres de columna aguas abajo **en el
  acto**, con el nodo marcado en rojo, antes de esperar tres minutos a que truene.
- La marca `es_estimado` viaja por el grafo. Una columna que salió de un pronóstico
  contamina a todo lo que toca, y la interfaz la pinta en ámbar `#F5C277`
  automáticamente, hasta en la tabla final. Un dato estimado nunca se presenta como
  hecho, y no depende de que alguien se acuerde de marcarlo.

### ④ Planear — análisis del DAG

- **Ciclos**: detección por DFS con pila de color. El error nombra el ciclo completo
  (`n3 → n7 → n11 → n3`), no dice "hay un ciclo".
- **Orden topológico**: Kahn, con desempate por `(profundidad, posición y, posición x)`
  para que el script generado se lea **de arriba hacia abajo igual que el lienzo**.
  Un orden topológico arbitrario también sería correcto, pero produciría un script
  que el usuario no reconoce como suyo.
- **Poda**: los nodos que no alcanzan ningún nodo terminal (una salida, un gráfico,
  un modelo) no se compilan. Los sub-grafos huérfanos de experimentos abandonados no
  cuestan tiempo de cómputo.
- **Ejecución objetivo**: si el usuario pide "ejecutar hasta aquí", se calcula el
  cono ancestral de ese nodo y se compila sólo eso.

### ⑤ Bajar a IR

El IR es una lista plana de instrucciones. Es deliberadamente aburrido: sin control
de flujo, sin anidamiento. Todo el poder expresivo vive en los nodos.

```python
@dataclass(frozen=True)
class Instruccion:
    nodo_id: str
    op: str
    version: str
    entradas: dict[str, str]    # puerto → nombre de variable de donde viene
    salidas: dict[str, str]     # puerto → nombre de variable que liga
    params: dict[str, Any]      # ya validados
    etiqueta: str               # lo que el usuario escribió, para el comentario
    huella: str                 # sha256 de contenido (§6)
```

**Los nombres de variable son parte del producto.** El script exportado lo van a leer
personas. La regla es: se usa la etiqueta del usuario, transliterada a un
identificador de Python válido (`Precios CDMX 2020` → `precios_cdmx_2020`); si no hay
etiqueta, se usa un nombre derivado del tipo de nodo (`mco_1`, `pesos_reina_1`); las
colisiones se resuelven con sufijo numérico estable. Sin `var_0`, `var_1`, `var_2`.

### ⑥ Emitir — IR → AST de Python

Cada `EspecNodo` implementa:

```python
def emit(self, ctx: ContextoEmision) -> BloqueCodigo: ...
```

`ContextoEmision` es la única forma que tiene un nodo de tocar el mundo:

| Método | Devuelve |
|---|---|
| `ctx.entrada("datos")` | `ast.Name` de la variable que llega por ese puerto |
| `ctx.salida("modelo")` | nombre de variable que debe ligar |
| `ctx.p("rezagos")` | el parámetro ya validado (valor de Python) |
| `ctx.lit(x)` | `x` → nodo AST literal (por `ast.Constant` / `List` / `Dict`) |
| `ctx.usar_ayudante("construir_w")` | registra el ayudante y devuelve su `ast.Name` |
| `ctx.importar("statsmodels.api", "sm")` | registra el import y devuelve el alias |
| `ctx.nota("...")` | comentario en español que precede al bloque |

**Nunca se construye código con `f-string`.** Se construyen nodos AST. Los parámetros
entran al árbol como `ast.Constant`, es decir como **datos**, no como texto que se
vuelve a parsear. Esto elimina por construcción la inyección de código vía parámetros:
una columna que se llame `x); import os; os.system("rm -rf /"); (` acaba siendo una
cadena literal con ese contenido exacto, y statsmodels se queja de que no existe esa
columna. Que es justo lo que debe pasar.

`BloqueCodigo` = `{ cuerpo: list[ast.stmt], imports: set[Import], ayudantes: set[str], notas: list[str] }`.

El programa final se ensambla así:

```
 1. Encabezado           → docstring con título, autor, fecha, versión de Abak,
                           y la huella del grafo del que salió
 2. Imports              → deduplicados y ordenados (stdlib, terceros, locales)
 3. Semillas             → random.seed / np.random.seed  (determinismo, §7)
 4. Ayudantes            → sólo los usados, en orden de dependencia
 5. Bloques por nodo     → en orden topológico, cada uno precedido por
                           `# ── {etiqueta} ─────` y sus notas
 6. Epílogo (sólo export)→ print() de los resúmenes, fig.show() de las figuras
```

### ⑦ Ejecutar — `exec` bloque por bloque

El worker no ejecuta el programa de un golpe: lo recorre nodo por nodo sobre **un
único espacio de nombres compartido**.

```python
espacio = {}
exec(compile(preludio, "<abak:preludio>", "exec"), espacio)

for ins in programa.instrucciones:
    if cache.tiene(ins.huella):
        espacio.update(cache.leer(ins.huella))   # revive las variables y sigue
        emitir_progreso(ins.nodo_id, "cacheado"); continue

    exec(compile(bloque_de(ins), f"<abak:{ins.nodo_id}>", "exec"), espacio)

    salidas = {v: espacio[v] for v in ins.salidas.values()}   # cosecha de nombres
    cache.escribir(ins.huella, salidas)
    artefactos.guardar(ins.nodo_id, resumir(ins.op, salidas))  # fuera del programa
    emitir_progreso(ins.nodo_id, "listo")
```

Por bloques y no de golpe, por cuatro razones concretas:

1. **Progreso real por nodo** en el lienzo, no una barra que finge.
2. **Caché**: se salta el bloque, pero se reponen sus variables en el espacio de
   nombres, así que el resto del programa no nota la diferencia.
3. **Errores localizados**: el `try` envuelve un bloque, y el bloque es un nodo. El
   traceback se traduce a "el nodo *Regresión de precios* falló porque la columna
   `ingreso` tiene 340 valores faltantes" y se pinta sobre ese nodo.
4. **Cancelar** entre bloques, sin matar el proceso.

El `compile()` se hace sobre los mismos objetos AST que `ast.unparse()` convierte en
el archivo exportado. No hay una segunda ruta.

---

## 5. El registro de nodos: una sola fuente de verdad

Agregar un nodo nuevo a Abak es **escribir un archivo de Python**. Nada más. No se
toca el frontend, ni la API, ni el ejecutor, ni el generador de código.

```python
@registrar
class MCO(EspecNodo):
    op = "econometria.mco"
    version = "1.2.0"
    familia = "econometria"
    titulo = "Mínimos cuadrados (MCO)"

    ayuda = Ayuda(
        que_hace="Ajusta una recta que minimiza la suma de los errores al "
                 "cuadrado. Es el punto de partida de casi todo.",
        cuando_usarlo="Cuando quieres explicar una variable numérica continua "
                      "con otras variables.",
        interpretacion="Cada coeficiente dice cuánto cambia la variable "
                       "dependiente si esa variable sube una unidad y las demás "
                       "se quedan igual.",
        supuestos=["Relación lineal en los parámetros",
                   "Errores sin autocorrelación (si no, usa errores HAC)",
                   "Varianza constante (si no, usa errores robustos HC1/HC3)"],
        referencia="Wooldridge (2019), cap. 3-4",
    )

    entradas = [Puerto("datos", "tabla", requerido=True)]
    salidas  = [Puerto("modelo", "modelo"), Puerto("residuos", "tabla")]

    class Params(BaseModel):
        y: Columna
        x: list[Columna]
        constante: bool = True
        errores: Literal["clasicos","HC1","HC3","HAC","cluster"] = "HC1"
        cluster_por: Columna | None = None

    def emit(self, ctx): ...
    def esquema_salida(self, entradas, params): ...
    def resumir(self, salidas): ...
```

De ese archivo salen, sin duplicación:

| Consumidor | Qué toma |
|---|---|
| Paleta del frontend | `familia`, `titulo`, `ayuda.que_hace` |
| Panel de inspector | `ayuda` completa, con supuestos y referencia |
| Formulario de parámetros | `Params` → JSON Schema → controles generados |
| Validador de tipos | `entradas`, `salidas` |
| Compilador | `emit`, imports, ayudantes |
| Caché | `version` (subirla invalida lo cacheado) |
| Documentación | todo lo anterior, en `docs/nodos.md` autogenerado |

La ayuda **no es opcional**. Una prueba recorre el registro y falla si un nodo no
explica qué hace, cuándo usarlo y cómo se lee su resultado. Un sistema que quiere ser
más fácil que SPSS no puede tener nodos sin explicar: la explicación es el producto
tanto como el cálculo.

---

## 6. Caché por huella de contenido

```
huella(nodo) = sha256(
    op ‖ version ‖ params_canónicos ‖ [huella(padres) ordenadas] ‖ semilla
)
```

Para los nodos raíz (cargar archivo), la huella incluye el `sha256` del contenido del
archivo, no su nombre ni su fecha. Un archivo que se vuelve a subir idéntico no
re-ejecuta nada; un archivo con una celda cambiada invalida exactamente el subgrafo
que dependía de él.

Consecuencia práctica: mover un nodo en el lienzo no invalida nada (la posición no
entra en la huella), pero cambiar un parámetro invalida ese nodo y todo lo que está
aguas abajo, y **nada más**. En un flujo con un XGBoost de cuatro minutos, cambiar el
color de una gráfica al final tarda lo que tarda dibujar la gráfica.

Los valores se serializan con Parquet (tablas) y `joblib` (modelos), en un almacén
por sesión con expiración. Los objetos que no se pueden serializar (rara vez) se
marcan como no cacheables en su `EspecNodo` y siempre se recalculan.

---

## 7. Determinismo

Un resultado que no se puede repetir no sirve para publicar. El programa fija en el
preludio `random.seed`, `np.random.seed` y las semillas de scikit-learn y XGBoost, con
la semilla de la sesión —que se guarda con el grafo y se escribe en el encabezado del
script exportado—. `n_jobs` se fija a 1 en los estimadores cuya reducción en paralelo
no es asociativa, salvo que el usuario acepte explícitamente el intercambio en el nodo.

---

## 8. Seguridad

Generar código y ejecutarlo es una operación peligrosa. El diseño lo trata como tal.

1. **El código sale de un registro cerrado.** No hay ninguna ruta por la que texto del
   usuario se convierta en código. El AST lo arma el nodo; los parámetros entran como
   `ast.Constant`.
2. **No hay fórmulas de texto libre en la v1.** El estilo `y ~ x1 + log(x2)` es
   cómodo, pero patsy evalúa Python dentro de la fórmula, y eso convertiría texto
   del usuario en código. En vez de eso, las variables se eligen del esquema
   propagado (§4.1) y las transformaciones son nodos (*Calcular variable*), que es
   además lo que permite usar el sistema sin saber sintaxis. Si algún día se abre
   el atajo de la fórmula, tiene que llegar con un validador propio que tokenice y
   acepte sólo identificadores presentes en el esquema, operadores de fórmula
   (`~ + * : - | 0 1`) y una lista blanca de transformaciones — nunca pasando la
   cadena a patsy tal cual.

   Lo que sí llega al archivo generado como texto libre son los **comentarios**: la
   etiqueta que el usuario le puso a un bloque, su nota sobre un paso, el título
   del análisis. Todo eso pasa por un saneador único que colapsa los saltos de
   línea (cerrarían el comentario, y lo que siguiera sería código) y neutraliza las
   comillas triples (cerrarían el docstring del encabezado). Hay pruebas que
   comparan el árbol del programa generado con entradas benignas y hostiles: la
   estructura tiene que ser idéntica.
3. **El worker está aislado.** Contenedor sin red de salida, sistema de archivos de
   sólo lectura salvo un directorio temporal por ejecución, límites de CPU, memoria
   (`RLIMIT_AS`) y tiempo de pared. Corre como usuario sin privilegios.
4. **Los archivos que sube el usuario** se validan por contenido (no por extensión),
   con tope de tamaño y de número de columnas, y se convierten a Parquet antes de
   tocar el motor. No se abren archivos con `pickle`.
5. **La API valida el grafo antes de encolarlo.** Un grafo inválido nunca llega al
   worker.

El modelo de amenazas que **no** se cubre en la versión de un solo tenant: un usuario
autenticado que hace un análisis carísimo a propósito. Se acota con cuotas y tiempos
límite, no con aislamiento fuerte. Para multi-tenant hace falta un sandbox por
ejecución (gVisor/Firecracker); está anotado en el plan, no implementado.

---

## 9. Errores: traducir, no ocultar

Un `LinAlgError: Singular matrix` no le dice nada a un economista, y "hubo un error"
le dice menos. El runtime tiene un traductor de excepciones que mapea patrones a
diagnósticos accionables:

| Excepción | Lo que se muestra |
|---|---|
| `LinAlgError: Singular matrix` | "Dos de tus variables explicativas dicen lo mismo (colinealidad perfecta). Revisa `x2` y `x5`, o quita una." |
| `MissingDataError` | "La columna `ingreso` tiene 340 datos faltantes de 1,200. Agrega un nodo *Tratar faltantes* antes de este." |
| `ValueError: Insufficient degrees of freedom` | "Pides 14 rezagos con 22 observaciones. Baja los rezagos o consigue más historia." |

El traceback completo **siempre** queda disponible en la pestaña Bitácora. Traducir no
es esconder: el economista lee el diagnóstico, y quien tenga que depurar lee el
traceback.

---

## 10. Persistencia

| Qué | Dónde | Por qué |
|---|---|---|
| Grafos (documentos) | Postgres, JSONB versionado | Historial, "volver a la versión de ayer" |
| Datasets del usuario | Almacén de objetos, en Parquet | Columnar, tipado, comprimido |
| Valores intermedios | Caché por sesión, con expiración | Reconstruibles: no vale la pena guardarlos para siempre |
| Artefactos (tablas, figuras) | JSON en Postgres, blobs aparte | Los pide la interfaz una y otra vez |
| Estado de ejecución | Redis | Efímero por naturaleza |

En desarrollo, todo lo anterior cae a disco (`.abak/`) y Celery corre en modo
`eager`, para que `docker compose up` no sea requisito de entrada.

---

## 11. Lo que deliberadamente no hacemos

- **No hay bloque de "código libre" en la v1.** Es la puerta trasera obvia y rompe las
  tres propiedades del sistema: verificación de tipos, caché y aislamiento. Llegará
  como un nodo de *expresión* restringido (una expresión de pandas sobre columnas
  conocidas), no como un `exec` arbitrario.
- **No se reimplementan estimadores.** Abak orquesta statsmodels, spreg, scikit-learn
  y XGBoost. Reimplementar econometría es cómo se pierde la confianza que este producto
  necesita. Si un método no está en una biblioteca respetada, no está en Abak.
- **No hay ciclos en el grafo.** Un análisis es un DAG. Lo que parece iteración
  (validación cruzada, pronóstico recursivo, bootstrap) va **dentro** de un nodo, donde
  está probado, no dibujado por el usuario.
- **No se adivinan las intenciones.** Si faltan datos, el sistema dice cuántos y
  dónde; no imputa por su cuenta. Si un supuesto se viola, lo dice; no cambia de
  estimador en silencio.

---

## 12. Estado y plan

| Fase | Alcance | Estado |
|---|---|---|
| 0 | Monorepo, contratos, arquitectura | ✅ |
| 1 | Núcleo: grafo, tipos, registro, esquemas | ✅ |
| 2 | Compilador, shadow code, ejecutor, caché | ✅ |
| 3 | Nodos: datos, transformación, econometría, series, espacial, insumo-producto, ML | ✅ 60 herramientas |
| 4 | Gramática de gráficos por capas → Plotly | ✅ |
| 5 | API FastAPI + Celery | ✅ |
| 6 | Frontend: lienzo, pestañas, inspector | ✅ |
| — | Pruebas: 234, incluida la reproducibilidad del script exportado | ✅ |
| 7 | Persistencia Postgres, cuentas, colaboración | ⏳ |
| 8 | Conectores en vivo (INEGI, Banxico SIE, SHF) | ⏳ |
| 9 | Sandbox por ejecución para multi-tenant | ⏳ |

El detalle de qué nodo existe hoy está en `docs/nodos.md`, que se genera del registro
y por lo tanto no puede quedar desactualizado.
