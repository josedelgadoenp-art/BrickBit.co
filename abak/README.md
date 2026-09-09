# Abak

**Inteligencia económica.** Describes el análisis en español y la IA lo arma con
econometría de verdad; o lo armas tú conectando bloques. Las dos maneras llegan
al mismo sitio.

Lo que separa esto de pedirle un análisis a un chatbot: la IA **no escribe
código**, arma un grafo de herramientas del catálogo, y ese grafo pasa por el
mismo validador y el mismo compilador que uno hecho a mano. Después Abak lo
compila a un programa de Python legible y lo ejecuta. El programa generado no es
una bitácora de lo que pasó: **es** lo que pasó, y lo puedes exportar y correr en
cualquier máquina sin Abak.

Nada queda en una caja negra: el análisis vive en el lienzo, cada herramienta
explica qué hace, cada cifra explica cómo se lee, y lo estimado va en ámbar.

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

### Windows: un clic

En Windows no hay `make`, y arrancar a mano son dos comandos en dos terminales.
Para uso diario eso se paga todos los días, así que hay atajos:

```
Instalar Abak.bat          doble clic, una sola vez (tarda unos minutos)
crear-acceso-directo.ps1   deja «Abak» en el Escritorio
```

A partir de ahí, **doble clic en el icono del Escritorio**: levanta el API y la
interfaz en ventanas minimizadas, espera a que compile y abre el navegador
solo. Para cerrarlo todo, `detener.ps1` o cierra las dos ventanas.

`iniciar.ps1` usa `npm run dev` a propósito y no `npm run start`: `start` sirve
una compilación ya hecha, y después de un `git pull` estaría enseñando la
versión vieja sin avisar.

### Desde el celular, en tu propia red

`Iniciar Abak en red.bat` (o `.\iniciar.ps1 -Red`) deja la interfaz escuchando
en toda la red local y te dice la dirección — algo como `http://192.168.1.42:3000`.
La primera vez hay que correr `Permitir Abak en la red.bat`, que abre el puerto
en el Firewall **sólo para redes privadas** y pide permisos de administrador.

Se expone **un solo puerto, el 3000**. El API se queda escuchando nada más en
`127.0.0.1`: la interfaz le habla desde la misma máquina, así que el celular
nunca necesita alcanzarlo. Verificado: por la IP de red, el 3000 responde 200 y
el 8000 rechaza la conexión.

Aun así, esto **no es una puerta con llave**: quien esté en tu red y llegue al
puerto 3000 puede ejecutar código en tu computadora, porque eso es exactamente
lo que hace Abak. En tu casa es tu gente; en el wifi de un café es cualquiera.
Por eso el modo red es opcional y no el predeterminado, y por eso el lanzador
se detiene a preguntar cuando Windows tiene la red marcada como pública.

### Windows a mano

Si prefieres los comandos sueltos, desde PowerShell en la carpeta `abak`:

```powershell
python -m venv .venv
.venv\Scripts\pip install -e "packages/core[todo,dev]"
.venv\Scripts\pip install -e services/worker -e services/api
cd apps\web ; npm install ; cd ..\..
```

Y luego, en dos terminales:

```powershell
.venv\Scripts\python -m uvicorn abak_api.main:app --port 8000 --reload   # terminal 1
cd apps\web ; npm run dev                                                 # terminal 2
```

`--reload` importa: sin él, un `git pull` no surte efecto hasta reiniciar el
servidor a mano, y el síntoma engaña — la pantalla sigue mostrando mensajes de
error viejos, o una función recién agregada responde «Not Found», y parece que
la actualización no sirvió.

Lo que `--reload` **no** arregla: si cambias la **llave** (o cualquier variable
de entorno), hay que cerrar la ventana y abrir una nueva. El entorno se hereda
al arrancar el proceso; recargar el código no lo vuelve a leer.

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

**67 herramientas** en 14 familias:

- **Datos** — archivos, ejemplos, filtros, uniones, agrupar, remodelar, declarar serie / panel / ubicación
- **Fuentes oficiales** — Banxico (SIE), INEGI (BIE/BISE), DENUE, con caché en disco
- **Transformar** — logaritmos, rezagos, crecimiento, deflactar, estandarizar, dummies, winsorizar
- **Explorar** — descriptivos, correlaciones, comparación de grupos
- **Econometría** — MCO con errores robustos (HC1/HC3/HAC/cluster), variables instrumentales, logit/probit con efectos marginales, cuantiles, panel (efectos fijos y aleatorios + Hausman), diagnósticos, VIF
- **Series de tiempo** — ADF y KPSS, ARIMA/SARIMAX con banda de pronóstico, VAR con impulso-respuesta y Granger, Johansen y VECM, filtros de ciclo (HP y Hamilton)
- **Econometría espacial** — matrices de vecindad (KNN, distancia, kernel), I de Moran, LISA, SAR, SEM, pruebas LM para elegir entre los dos
- **Macro e insumo-producto** — Leontief, multiplicadores de producción, empleo e ingreso, encadenamientos de Rasmussen, impacto de un choque de demanda, multiplicador keynesiano
- **Machine learning** — partición honesta, XGBoost, validación de origen móvil, importancias
- **Gráficos** — gramática por capas (lienzo + puntos, línea, barras, área, banda, tendencia, facetas, escalas, tema) renderizada con Plotly
- **Inferencia causal** — dibujas qué causa qué y el criterio de puerta trasera decide los controles
- **Escenarios y proyecciones** — «¿qué pasa si?»: recorre una variable, deja las demás en su mediana y proyecta el resultado con su banda, para moverlo con un control deslizante
- **Inmobiliario** — índice de precios de calidad constante (hedónico encadenado)
- **Entregables** — tabla de publicación estilo `esttab`, exportar a CSV o Excel

### Las gráficas salen solas

No hay que armarlas. Cada herramienta que estima dibuja la lectura visual que le
corresponde en cuanto ejecutas: el bosque de coeficientes con su intervalo, el
ajuste contra lo observado y los residuos, el abanico del pronóstico, la rejilla
de impulso-respuesta de un VAR, el ranking de importancias, el mapa de
correlaciones, las cajas de los descriptivos. Y aparecen **junto a su tabla**,
no en otra pestaña: la gráfica de coeficientes explica la tabla que tiene encima.

Antes había que apilarlas capa por capa con el bloque «Lienzo», y en la
verificación completa de los seis ejemplos se dibujaba **una** gráfica en total.
No es que nadie las quisiera: el camino para tenerlas era más largo que el camino
para no tenerlas. La gramática por capas sigue ahí para lo que quieras armar a
mano; lo que cambió es el punto de partida.

Dos cosas que estas gráficas **no** hacen, porque serían mentiras cómodas:

- **No comparten eje entre magnitudes distintas.** Las cajas de los descriptivos
  van en paneles con su propia escala: un precio por m² de 8,300 a 40,500 y una
  escolaridad de 6.8 a 13.6 en el mismo eje dejan a la segunda aplastada contra
  el suelo, y el gráfico dice «la escolaridad no varía», que es falso.
- **No comparan coeficientes crudos.** Un ingreso en pesos da 0.48 y una
  escolaridad en años da 1,105: en un eje compartido el primero se ve pegado al
  cero aunque mueva más el resultado. El bosque escala cada coeficiente por la
  desviación estándar de su variable —el efecto de moverla una desviación— y lo
  dice en el eje. Los coeficientes en sus unidades siguen enteros en la tabla.

### Proyecciones que se mueven

El bloque **«¿Qué pasa si?»** contesta lo que un coeficiente no contesta: no
«cuánto vale el parámetro» sino «a dónde llega el precio por m² si el ingreso
sube». Recorre una variable de punta a punta, deja las demás en su mediana
—no en cero, que produce perfiles imposibles— y proyecta con banda. Si eliges
una segunda variable, calcula una curva por cada valor de ésa y las entrega
todas: en pantalla sale un control deslizante que las recorre.

Lo que hace honesto al deslizador: **la rejilla completa se calcula en el motor
y viaja entera al navegador**. El control no modela nada; escoge cuál de las
curvas ya calculadas se resalta, y las demás quedan tenues detrás para que se
vea el abanico entero. Cada punto dibujado está en la tabla de al lado, en el
script exportado y en el PDF. Si el deslizador estimara del lado del cliente
sería un modelo en la sombra: nadie podría auditarlo ni citarlo, y el número de
la pantalla no coincidiría con el del informe. Una prueba lo verifica punto por
punto.

El recorrido va del percentil 5 al 95 y no del mínimo al máximo, para no
extrapolar sobre un solo caso extremo: fuera del rango observado un modelo
lineal dice cualquier cosa con toda seguridad.

Cada resultado se baja en PDF: un bloque suelto, o el informe completo del
análisis con su metodología. En papel no hay deslizador, así que la proyección
se imprime con todas sus curvas a la vez: se pierde el gesto, no la información.
Convertir una gráfica a imagen necesita Chrome en el servidor; si no lo
encuentra, el informe sale con sus tablas y dice en el hueco por qué falta la
figura (`BROWSER_PATH` apunta a un Chromium existente). Y cada indicador que aparece en pantalla —el
coeficiente, el p, el R², el AIC, la I de Moran, los multiplicadores— trae un
botón que explica qué es, cómo se lee y con qué hay que tener cuidado. Son 205
fichas; si un indicador no tiene ficha el botón no aparece, y una prueba
comprueba que nada de lo que Abak nombra se quede sin la suya.

**Cada herramienta se verifica contra un cálculo hecho por fuera.** No basta con
que corra: el número que reporta se compara con la fórmula, o con la biblioteca
llamada por su API canónica. Así no se prueba que statsmodels sepa estimar —eso
ya lo sabe—, se prueba el cableado, que es lo nuestro: reportar el error clásico
diciendo que es robusto, el coeficiente de un logit como si fuera un efecto
marginal, o el multiplicador de la fila en vez del de la columna son errores que
devuelven números perfectamente plausibles y no dan ninguna señal.

El detalle está en [docs/nodos.md](docs/nodos.md), que se genera del registro.

---

## Pídelo en español

Al abrir Abak no hay lienzo, ni paleta, ni ocho pestañas: hay una pregunta.
Escribes lo que quieres —«explica el precio por m² con el ingreso y la
escolaridad, en logaritmos, y grafica el ajuste»— y **Abak lo arma, lo revisa,
lo ejecuta y te deja en el resultado**. Tres pasos, y sólo el primero es tuyo:

    1. Pregunta  ›  2. Análisis  ›  3. Resultado

Antes se detenía en el segundo. Armaba el grafo y dejaba a la persona mirando
doce cajas conectadas y un botón «Ejecutar» que había que descubrir: había
hecho una pregunta y recibía un diagrama. Ahora el diagrama sigue ahí —a una
pestaña de distancia, entero y corregible— pero lo primero que se ve es la
respuesta, con la frase que se escribió y lo que se hizo con ella encima de las
tablas.

En el resultado, los pasos que sólo prepararon los datos van plegados al final.
No se ocultan —un clic los abre, y el orden real sigue intacto en el lienzo, en
el código y en la nota metodológica—: es que la tabla de 32 renglones que sirvió
para llegar al modelo no es la respuesta, y estaba cuatro pantallas por encima
de ella.

Las pestañas también bajaron de ocho a cinco. Cuatro contestan «¿qué salió?» y
«¿con qué?» (Resultado, Gráficos, Análisis, Datos); las cuatro de auditoría
—Metodología, Código, Especificaciones, Bitácora— viven dentro de **«Cómo se
hizo»**, que es la pregunta que contestan. Y la paleta y el inspector aparecen
sólo en el lienzo, que es donde sirven: leer una tabla de regresión por una
rendija de 600 px menos no ayudaba a nadie.

Lo que hace que esto sea seguro y no una caja negra: **el modelo no escribe
código, escribe un GRAFO**. Su única salida posible es una lista de bloques del
catálogo con sus parámetros, y ese grafo pasa por la misma validación de tipos
y el mismo compilador que uno armado a mano. Un `op` inventado se rechaza por
nombre; un parámetro con el tipo equivocado lo caza Pydantic; una **columna
inventada** —la alucinación más probable— la caza el esquema propagado, que
sabe qué columnas existen de verdad en ese punto del grafo.

El peor caso de una alucinación es un bloque en rojo con su mensaje. Nunca
código ejecutándose. Si el modelo pudiera emitir Python, esta función sería la
vulnerabilidad más grande del producto; emitiendo grafos, es la más contenida.

Y el resultado queda **en el lienzo**: se ve, se corrige y se ejecuta como
cualquier otro análisis. La IA propone el punto de partida; el trabajo sigue
siendo tuyo y sigue siendo auditable.

Antes de ejecutar se valida, y si algo quedó a medias no se corre: se dice qué
bloque le falta y un botón lleva hasta él. Después, la caja para pedir el
siguiente paso —«ahora en logaritmos», «agrega la prueba de heterocedasticidad»—
queda fija bajo las pestañas, siempre en el mismo sitio.

Necesita una llave de Anthropic en el entorno del servidor. En **Windows**, doble
clic en `Configurar llave de IA.bat`: pide la llave, la revisa antes de guardarla
y dice qué sigue. En Linux o Mac:

```bash
export ANTHROPIC_API_KEY="$(read -rs -p 'Pega la llave: ' k; echo "$k")"
```

**Sin hueco que rellenar, a propósito.** Un instructivo con un `<pega aquí tu
llave>` es una trampa: la línea se ve completa y se copia entera, texto de
ejemplo incluido. Pasó dos veces seguidas antes de que existiera este script, y
el síntoma —un 401— se lee como «mi llave está mal» en vez de «pegué el
ejemplo». Por eso el programa además revisa el prefijo y la longitud antes de
gastar una llamada.

La llave vive sólo en el entorno del servidor: nunca viaja al navegador, nunca
se guarda en el grafo, nunca sale en el script exportado. Sin llave, la pantalla
de inicio dice qué falta **y ofrece los seis análisis de ejemplo a un clic**,
más un «prefiero armarlo a mano» que abre el taller completo. Que la puerta
principal sea una pregunta no puede dejar sin Abak a quien no tenga llave.

---

## Cargar tus propios datos

Un análisis se arma encadenando bloques. Al hacer clic en una herramienta de la
izquierda, **se conecta sola** con el bloque que tenías seleccionado si los
tipos encajan, y se coloca a su derecha. No hay que arrastrar hilos entre
puntos de seis píxeles: ese gesto era el que dejaba a la gente con «Ejecutar»
apagado, sin saber si la herramienta estaba rota o si les faltaba algo.

Y **Ejecutar nunca se queda muerto**: si falta configurar algo, el clic te
lleva al bloque que lo pide y dice qué le falta.

Una regresión sobre tu propio archivo son diez acciones, contadas en una prueba
de navegador (`recorrido3`): buscar «cargar», clic, subir el archivo, buscar
«MCO», clic, elegir la columna a explicar, marcar tres explicativas, Ejecutar.


1. **«Subir datos»**, arriba, y eliges tu archivo. El bloque queda puesto y
   configurado; no hay que buscar nada en la paleta.
2. **Ejecutar**. La pestaña **Datos** te muestra la tabla.

**El separador, el decimal y la codificación se detectan solos.** Abak mira el
principio del archivo y deduce si viene con coma o con punto y coma, si el
decimal es punto o coma, y en qué codificación está — y **te dice qué supuso**,
porque adivinar en silencio es la mitad del problema. Antes había que saberlo de
antemano: un CSV exportado por un Excel en español (punto y coma + coma decimal),
que es el formato más común en México, se leía como **una sola columna** llamada
`entidad;precio_m2;escolaridad`, con basura dentro y sin ningún error. Y un
archivo en latin-1 moría con «'utf-8' codec can't decode byte 0xe9», que no le
dice nada a nadie.

Formatos: `.csv`, `.tsv`, `.txt`, `.xlsx`, `.xls`, `.parquet` y `.zip`.

El `.zip` está porque las fuentes oficiales mexicanas publican así —el DENUE,
las series de la SHF, casi todo el INEGI— y descomprimir a mano antes de subir
es un paso de más en lo que más se repite. Se saca el archivo tabular de
adentro; si el zip trae varios **no se adivina cuál**: se listan y se pide
elegir, porque analizar el archivo equivocado en silencio es peor que fallar.

Al subir, el archivo se convierte a **Parquet** (columnar). Eso es lo que
permite trabajar con millones de filas: se lee sólo las columnas que el
análisis usa. El original se borra después de convertirlo.

Tope por archivo: 2 GB (`ABAK_TOPE_SUBIDA_MB` lo cambia).

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

## Para mercado inmobiliario

### Un índice de precios, no la mediana de lo vendido

**El precio mediano de las casas vendidas no es un índice de precios.** Si un
trimestre se vendieron más departamentos chicos, la mediana baja aunque ningún
precio haya bajado: cambió la mezcla, no el mercado.

**Índice de precios de calidad constante** separa las dos cosas por el método
de la ficticia de periodos adyacentes: para cada par de periodos estima
`log(precio) = a + B'X + δ·D` y encadena `exp(δ) − 1`. Es la metodología del
Case-Shiller y del índice de la SHF.

La prueba mide las dos cosas a la vez sobre un mercado simulado: que el índice
recupere la subida real (dentro del 2%) y que la mediana de lo vendido **caiga
más de 20%** por composición. Si sólo comprobara lo primero, no estaría midiendo
por qué existe la herramienta.

### Iterar sobre millones de filas sin mentir sobre la precisión

Con millones de filas, esperar cuatro segundos por iteración mata la
exploración: se prueban tres ideas en vez de treinta, y las buenas son de las
que no se probaron.

**Trabajar sobre una muestra** toma la muestra y calcula, columna por columna,
cuánta precisión estás entregando a cambio. `margen_95_pct` dice cuánto se puede
mover la media por el puro hecho de haber muestreado: 0.4% significa que no te
está costando nada; 12% significa que cualquier conclusión fina sobre esa
columna es de la muestra, no del mercado. Y trae un interruptor —`usar todo`—
para que el resultado final corra sobre la población completa sin tocar nada más
del análisis.

El error de muestreo es **adicional** al error estadístico de siempre: se suma,
no lo sustituye. Por eso se reporta aparte en vez de esconderse dentro de un
intervalo de confianza. La prueba repite el muestreo 200 veces y comprueba que
el intervalo del 95% cubra la media real cerca del 95% de las veces: si el
margen prometido no se cumpliera, la herramienta sería peor que no tenerla.

---

## Dos cosas que no hace ningún otro programa

### Decide qué controlar, en vez de obedecer

«¿Qué variables meto de control?» es la pregunta que todo economista aplicado
contesta a diario y que ningún programa estadístico responde: R, Stata, EViews
y SPSS meten lo que les pidas. Y meter de más es tan grave como meter de menos.
Un **mediador** —algo por lo que pasa el efecto— borra justo lo que querías
medir. Un **colisionador** inventa una correlación que no existe. Ninguno de
los dos errores mueve el R², el p-valor ni ningún diagnóstico: el modelo se ve
perfecto y la respuesta es falsa.

Como el lienzo ya es un grafo dirigido, dibujar quién causa a quién es el gesto
natural. Con eso, **Efecto causal (puerta trasera)** decide el conjunto de
controles y entrega, al lado del coeficiente, una tabla que dice de cada
variable qué es, si entró y por qué. Cuando el efecto **no** se puede
identificar con las columnas que hay, lo dice y no estima: ninguna regresión
arregla un confusor que no observaste, y saberlo antes de publicar el número es
justo el valor.

El grafo lo pones tú y no se puede verificar con los datos: es un argumento, no
un resultado. Abak no descubre estructura causal a partir de los datos, porque
no se puede sin supuestos fuertes y fingir que sí sería la clase de
deshonestidad que este producto existe para evitar.

### Cuenta las especificaciones que probaste

El fraude involuntario más extendido de la economía aplicada: alguien prueba
veinte especificaciones y publica la que «funcionó». Nadie miente; nadie
cuenta. Con veinte intentos, un p-valor bajo 0.05 es lo esperable aunque no
haya nada.

Abak puede contarlo porque cada ejecución pasa por su registro. La pestaña
**Especificaciones** dice cuántas llevas para cada variable explicada, el rango
completo de cada coeficiente entre todas, cuántas veces salió significativo, y
avisa cuando el número que estás mirando es el extremo de todo lo que probaste
o cuando el signo cambia entre especificaciones. No acusa a nadie: pone el
contexto al lado del número, que es la diferencia entre informar y seleccionar.

Es la regla de la casa un piso más arriba: si un dato estimado no se presenta
como un hecho, una especificación elegida entre catorce tampoco se presenta
como la única.

---

## Frente a R, Stata y EViews

La pregunta honesta es si esto sustituye a esos programas. La respuesta corta:
**para el análisis económico aplicado que se hace todos los días, sí, y con
bastante menos fricción. Como reemplazo general de R, todavía no.**

**Lo que Abak hace igual y más fácil.** El camino completo de un trabajo
aplicado —traer datos, limpiarlos, declarar el panel o la serie, estimar,
diagnosticar, graficar, publicar la tabla— está cubierto y no pide escribir una
línea. Un MCO con errores HC3, un panel de efectos fijos con Hausman, un
ARIMA con banda de pronóstico, un VAR con impulso-respuesta, un Johansen, un
SAR contra un SEM decidido con pruebas LM: todo eso son bloques conectados. En
EViews el VAR sale de un cuadro de diálogo con veinte casillas; en Stata hay
que acordarse de `xtset` antes de `xtreg` o el resultado es otro y nadie avisa.

**Dos cosas en las que Abak está por delante de los tres.** La primera es que
el código exportado *es* el que se ejecutó —el mismo AST se imprime y se corre,
no hay dos caminos que puedan separarse—, así que la reproducibilidad no
depende de que alguien se acuerde de guardar el log. La segunda es que cada
herramienta y cada cifra se explican en pantalla: quién debe usarla, cómo se
lee, qué la invalida. Eso no existe en ninguno de los tres, y es justo donde se
pierde la gente que no viene de econometría.

**Lo que todavía no está.** Frente a **EViews**: la familia GARCH y volatilidad,
ARDL con prueba de límites, espacio de estados y Kalman, cambio de régimen
(Markov switching), SVAR con identificación distinta de Cholesky, ajuste
estacional X-13, raíces unitarias en panel, GMM y panel dinámico
(Arellano-Bond), pruebas de quiebre estructural (Chow, Bai-Perron), tobit y
modelos de conteo, estimación en ventana móvil, resolución de modelos de
ecuaciones simultáneas. Frente a **R**: todo lo anterior, más modelos
multinivel, GAM, inferencia bayesiana, la caja de inferencia causal moderna
(diferencias en diferencias, estudios de evento, RDD, control sintético),
remuestreo y bootstrap como ciudadano de primera, componentes principales y
análisis factorial, conglomerados, supervivencia, ponderadores de encuesta e
imputación múltiple. Y R tiene 20,000 paquetes: en cobertura bruta esa
comparación no se gana, ni se pretende.

**Dónde queda el límite real.** Si el trabajo cabe en las 63 herramientas,
Abak lo hace más rápido, con menos errores silenciosos y dejando un script que
otra persona puede correr. Si hace falta algo de la lista de arriba, hoy hay
que salirse — y la salida está prevista: se exporta el `.py`, que es Python
normal, y se sigue ahí. Esa puerta abierta es deliberada; encerrar al usuario
sería el mismo error que cometen los otros.

---

## Lo que falta

- Las técnicas listadas arriba, por orden de demanda: GARCH, ARDL, panel
  dinámico y quiebre estructural son las que más se piden en economía aplicada
- Persistencia en Postgres, cuentas y colaboración
- Sandbox por ejecución (gVisor/Firecracker) para multi-tenant
- Nodo de expresión restringida (una expresión de pandas sobre columnas
  conocidas) en lugar del bloque de código libre, que no existe a propósito
