# BrickBit Atlas — Motor de Inteligencia Inmobiliaria de la CDMX

Motor de valuación y pronóstico para la Ciudad de México. Vive **al lado** del
Motor de Morfogénesis (`app.py`), no dentro: son dos productos con datos y
ciclos de vida distintos, y mezclarlos habría hecho a los dos más frágiles.

**Estado: Fases 0 a 3 completas.** Las fases 4 y 5 están por construir.

---

## Lo primero que hay que saber

**La muestra de la CDMX es delgada: 2,313 inmuebles.**

Durante un tiempo el bloqueo fue no tener ningún listado individual —sin precio
+ m² + atributos por inmueble no hay AVM, ni SHAP, ni intervalo conforme—. Eso
ya se resolvió: el scraper autorizado de Century 21 corrió sobre el país entero
y de sus **18,560 propiedades**, 2,313 caen dentro de la CDMX y sobreviven a la
validación.

Pero 2,313 para 16 alcaldías **no da para intervalos estrechos**, y menos por
segmento. Conviene saberlo antes de leer el primer resultado del AVM: las bandas
van a salir anchas, y eso será una propiedad honesta del dato, no un defecto del
modelo. Lo que engorda la muestra es volver a correr el scraper cada mes —cada
corrida agrega inventario nuevo y, de paso, alimenta la serie temporal de la
Fase 3—.

```bash
node tools/c21-scraper.mjs todo      # deja c21_out/listados.json
python -m pipelines.fase0            # lo ingiere al lago
```

---

## Correr la Fase 0

```bash
pip install -r atlas/requirements.txt
cd atlas
python -m pipelines.fase0            # sin red: sólo lo que ya está en el repo
python -m pipelines.fase0 --osm      # además baja OSM (ver abajo)
python -m pipelines.fase0 --informe  # sólo el estado del lago
python -m pytest tests/ -q
```

### Correr la Fase 1

```bash
python -m pipelines.fase1              # ~1 min sobre 12,259 celdas
python -m pipelines.fase1 --informe
```

Construye la malla H3 de la CDMX, le cuelga las variables de amenidad y
accesibilidad, elige la matriz **W** con criterio explícito y corre el
diagnóstico espacial que el documento exige *antes* de modelar.

| Salida | |
|---|---|
| `features_malla` | 12,259 celdas × 134 columnas |
| W elegido | `banda(500 m)`, **I de Moran = 0.960** (p = 0.001) |
| Clústeres LISA | 1,459 alto-alto · 5,714 bajo-bajo |

El criterio de selección de W es **máxima I de Moran**: el W que más
estructura espacial captura es el que menos señal espacial deja en el
residual. No es AICc —eso exige un modelo por cada W, y en la Fase 1 todavía
no hay modelo— y se declara como lo que es.

El diagnóstico se corre sobre **densidad de empleo DENUE**, no sobre precios.
Mide que la estructura espacial de la actividad económica es real, que es el
supuesto del que cuelga todo el aparato espacial. El Moran del precio se mide
en la Fase 2, sobre los listados.

### Correr la Fase 2

```bash
python -m pipelines.fase2                  # AVM + intervalo, sobre venta
python -m pipelines.fase2 --operacion renta
python -m pipelines.fase2 --alpha 0.10     # intervalos al 90%
python -m pipelines.fase2 --informe        # relee la última evaluación
```

Junta los listados con la malla, parte **por bloque espacial**, ajusta hedónico
+ Durbin + boosting, los combina por apilado y convierte la predicción en un
intervalo con cobertura garantizada.

**Lo que hay que mirar primero es la cobertura, no el error.** Un AVM que se
equivoca 27% y lo dice sirve; uno que se equivoca 12% y no lo dice, no.

Sobre los datos reales de la CDMX, con 1,773 inmuebles de venta repartidos en 38
bloques espaciales (1,063 / 355 / 355):

| | |
|---|---|
| I de Moran del **precio** | **0.447** (p = 0.001) con knn(5) |
| SDM · ρ | **+0.302** (p = 3.2e-13), pseudo R² 0.580 |
| Error del apilado en prueba | mediana **26.9%** · R²(log) 0.525 |
| **Cobertura del intervalo 95%** | **94.9%** — calibrado |

El ρ positivo y muy significativo es el hallazgo de fondo: el precio de un
inmueble en la CDMX depende materialmente del de sus vecinos, y un modelo sin
componente espacial estaría mal especificado. Ya no es un supuesto heredado de
la Fase 1 —medida sobre densidad de empleo—, es una medición sobre precios.

### Qué cuesta cada nivel de confianza

La conformalización lleva la cobertura de 73.2% a 94.9% contra un objetivo de
95%. Pero **cubrir no es servir**, y el informe lo dice cuando toca: a 95% el
ancho es de ±101%, que es un intervalo con la garantía perfecta y sin utilidad
para decidir.

Contra la frontera de eficiencia —lo que ese error justifica si los errores
fueran log-normales—:

| nivel | cobertura | ancho ideal | ancho real | sobrecosto |
|---|---|---|---|---|
| 50% | 47.6% | ±24% | ±26% | 1.08× |
| **80%** | **79.7%** | ±47% | **±58%** | 1.24× |
| 90% | 88.7% | ±61% | ±76% | 1.24× |
| 95% | 94.9% | ±75% | ±101% | 1.35× |

**La banda del 80% es la que sirve como número de producto.** El 95% se guarda
para riesgo y cumplimiento, donde la cola importa y el ancho se tolera. El
sobrecosto que queda en los niveles altos es mitad colas pesadas reales —hay
anuncios mal capturados y hay que cubrirlos— y mitad ruido de estimar un
percentil extremo con seis bloques de calibración.

Lo que NO se recupera con método es el resto: el modelo se equivoca ~27% en la
mediana, y un intervalo honesto sobre ese error tiene que ser ancho. Eso se
estrecha con más inventario y mejores atributos.

### Cómo se llegó a un intervalo calibrado

Cuatro cosas, todas encontradas midiendo:

**Dos scores, no uno.** CQR estima los cuantiles 2.5% y 97.5% *directamente*, y
esa cola se apoya en el 2.5% de las observaciones —unas 26 de 1,063—. El
normalizado usa \|y − ŷ\| / σ̂(x), que se ajusta con todas. Los dos tienen la
misma garantía; medido sobre los datos reales, CQR da ±144% y el normalizado
±101%. Se calibran los dos y se reportan lado a lado.

**El ruido en σ̂ se paga en ancho y no compra cobertura.** En simulación, con la
misma cobertura, una σ̂ ruidosa infla la corrección de 1.92 a 3.44 y casi duplica
el ancho. Por eso σ̂ se ajusta con un modelo más suave que la media —es un
parámetro de estorbo: su trabajo es la FORMA del ancho, no acertar— y el score
usa σ̂(x) + γ, la estabilización aditiva de Lei et al. (2018). γ se elige
midiendo el ancho sobre datos que σ̂ no vio; todos los γ dan intervalos válidos,
así que elegir por ancho no compromete la cobertura.

**Los grupos chicos de Mondrian se juntan y se calibran juntos**, en vez de caer
a la corrección global —que la dominan los segmentos numerosos—. Medido:
`depto·barato`, con 12 inmuebles en calibración, cubría 69.6% cuando prometía 95%.

**La intercambiabilidad se rompe a propósito.** La garantía conforme exacta
supone que calibración y despliegue son intercambiables, y la partición por
bloque hace que sean barrios DISTINTOS. Por eso la cobertura puede caer un par
de puntos bajo el objetivo. No se corrige subiendo el nivel hasta que el número
quede bonito: es la condición real de uso —valuar donde no hubo comparables— y
con una partición al azar el número saldría clavado sin decir nada del barrio
siguiente.

### Correr la Fase 3

```bash
python -m pipelines.fase3                  # tiempo + campo espacial
python -m pipelines.fase3 --zona Guadalajara
python -m pipelines.fase3 --informe
```

Cuatro piezas, y conviene saber cuál se apoya en qué.

**Índice temporal (SHF, 32 zonas × 22 años).** Dato real de *transacciones* con
crédito garantizado, no de ofertas — complementario de los listados: uno tiene la
profundidad temporal que al otro le falta. La CDMX acumuló **×4.92 entre 2005 y
2026**, 7.88% anual compuesto. **Nominal**: sin la serie del INPC no se puede
decir cuánto de eso fue plusvalía y cuánto inflación, y el informe lo declara en
vez de dejar que se lea como real.

**¿El crecimiento se contagia entre zonas vecinas?** `data/forecast.json` afirma
un modelo "50% momentum + 50% contagio espacial". La Fase 3 lo pone a prueba con
validación hacia adelante —ajustar con los años anteriores, predecir el
siguiente— sobre 480 predicciones fuera de muestra. Y el resultado incomoda:

| predictor | error absoluto medio |
|---|---|
| media histórica | 2.17 pp |
| sólo momentum | **1.81 pp** |
| momentum + vecinos | 1.86 pp |

**El término espacial no aporta: empeora el error un 2.6%**, y su coeficiente
medio sale negativo. El I de Moran del crecimiento es apenas +0.10 y significativo
en 5 de 21 años. Agrupamiento no es contagio: dos vecinos pueden crecer igual
por un choque común —una tasa hipotecaria, un ciclo nacional— sin que uno empuje
al otro. La prueba es predecir, y no predice.

**Superficie de precio** sobre la CDMX por proceso gaussiano —kriging con otro
nombre— con kernel Matérn ν=1.5 y no RBF: los precios cambian de golpe al cruzar
una avenida, y un kernel infinitamente suave difumina justo esos bordes. Escala
característica aprendida: **6.66 km**. Pendiente mediana **7.8%/km**, p90 17.7%/km.

**Y la incertidumbre se reporta partida en dos**, porque `predict(return_std=True)`
de scikit-learn devuelve la de UN ANUNCIO, con el ruido del WhiteKernel dentro.
Confundirlas hacía parecer que no se sabe nada:

| | |
|---|---|
| incertidumbre del **nivel** de la zona | ±19% mediana |
| dispersión **entre anuncios** de una misma zona | ±30%, irreducible |

Son preguntas distintas —cuánto puede valer este anuncio, contra cuánto vale el
m² típico de la zona— y sólo la segunda sirve para un mapa. Reportar la total
daba ±53%.

**Frente de precio**: dónde un inmueble va muy por debajo de sus vecinos —el
cuadrante bajo-alto del LISA—. Se busca sobre los **listados**, no sobre la
superficie: una superficie con escala de kilómetros no puede contener un hoyo
local de 174 m, y aplicarle LISA devolvía **cero** en toda la ciudad, lo cual
parecía decir "no hay oportunidad en la CDMX" cuando era imposible por
construcción. Suavizar borra exactamente lo que esa función busca.

**Multiplicador espacial (I − ρW)⁻¹** con el ρ de la Fase 2 (0.302). Aquí hay una trampa
que costó caer: la **suma de fila** vale 1/(1−ρ) para todas las celdas —es una
identidad algebraica— así que un mapa de sumas de fila sale plano por
construcción. Lo que varía es la **columna**: cuánto mueve al sistema entero un
cambio originado ahí. Con un W de k vecinos la variación es modesta (1.1×) y eso
también se declara: un grafo KNN es casi regular por construcción, así que apenas
hay diferencia de posición que capturar.

**Lo que la Fase 3 NO puede hacer.** El documento pide un campo de *crecimiento*
por celda. Eso exige ver la misma celda en dos momentos, y hoy hay **una sola
captura** de listados; el SHF aporta el tiempo pero a resolución estatal. No se
fabrica multiplicando una cosa por la otra —daría un mapa convincente y sin
respaldo—. La condición para desbloquearlo es concreta: **correr el scraper cada
mes**. En un año hay panel para estimar crecimiento por celda y validarlo hacia
adelante, igual que aquí se valida el contagio entre zonas.

### Cobertura de la CDMX: siete alcaldías con ruta rota

En la corrida del scraper de 2026-09 el barrido profundo devolvió **HTTP 404 en
la página 1** para siete alcaldías: casi la mitad de la ciudad y las de mayor
valor por m². Un 404 no es "no hay inventario": es una ruta que no existe.

El modo `sondeo` —que no scrapea, sólo mide qué contesta cada ruta candidata—
encontró la causa. **El portal usa dos convenciones a la vez:**

```bash
node tools/c21-scraper.mjs sondeo --estado ciudad-de-mexico   # ~6 min, en local
```

| | ruta | alcaldías |
|---|---|---|
| slug pelón | `en-municipio_iztapalapa` | 9 |
| con el estado delante | `en-municipio_ciudad-de-mexico-benito-juarez` | 6 |

Las seis del segundo grupo comparten nombre con un municipio de otro estado
—Benito Juárez con Cancún, Cuauhtémoc con Chihuahua, Álvaro Obregón con
Michoacán, Venustiano Carranza con Chiapas y Puebla—: el prefijo es cómo el
portal desambigua homónimos. Es el mismo problema que ya había metido Cancún en
la capa DENUE.

Inventario recuperado: Benito Juárez 267, Álvaro Obregón 250, Cuauhtémoc 191,
Coyoacán 131, Venustiano Carranza 52, La Magdalena Contreras 44.

**Gustavo A. Madero sigue sin ruta** tras probar 30 combinaciones. La primera
versión del generador tenía un hueco —las formas con el estado se cruzaban sólo
con el slug base, nunca con las variantes reducidas, así que
`ciudad-de-mexico-gustavo-madero` no llegó a probarse—; ya se cruzan todas.

El sondeo se corre en local porque el portal rechaza las IP de nube, igual que
INEGI y Overpass.

### Qué ingiere hoy, sin red

| Capa | Filas | Fuente |
|---|---:|---|
| `denue` | 351,631 | INEGI DENUE, 9 de 16 alcaldías |
| `cp` | 1,182 | Polígonos de código postal de la CDMX |
| `calles` | 9,090 | Ejes viales por alcaldía |
| `osm_poi` | 15,904 | OpenStreetMap: parques, transporte, salud, educación |
| `properties` | 2,313 | Century 21 — de 18,560 nacionales, los de la CDMX |

### Lo que se corre en tu máquina

Overpass (OSM), el portal de datos de la CDMX e INEGI **rechazan las IP de
nube**. Comprobado desde este contenedor: reset de conexión. Es el mismo patrón
que ya seguían `tools/riesgos_local.py` y `tools/macro_local.py`.

```bash
python -m pipelines.fase0 --osm      # parques, plazas, Metro, Metrobús, Cablebús…
python scripts/ingerir_denue.py      # las 7 alcaldías que faltan
node ../tools/c21-scraper.mjs sondeo --estado ciudad-de-mexico   # rutas del portal
```

OSM ya está ingerido (15,904 puntos) y se notó: al entrar, el error mediano bajó
de 24.7% a 22.0% y `W_acc_hospitales` apareció como segundo motor de precio en
SHAP, por encima de la accesibilidad a servicios. Falta el DENUE de 7 alcaldías.

El resultado queda en el lago y las fases siguientes ya no necesitan red.

---

## Decisiones que conviene conocer

**CRS.** EPSG:4326 sólo para entrada/salida y mapas. Toda distancia, área o
buffer se calcula en **EPSG:6372** (Cónica Conforme de Lambert de México). Medir
en grados mete ~6% de error en la latitud de la CDMX **sin avisar**, y hay una
prueba que lo congela: `test_metrico_mide_en_metros_y_geografico_no`.

**Homónimos.** `data/` guarda 171 municipios del país y varios se llaman igual
que una alcaldía. `establecimientos_benito_juarez.csv.gz` es Benito Juárez de
**Quintana Roo** (Cancún). Emparejar por nombre metía Cancún en el Atlas, y como
`glob` no garantiza orden el resultado además cambiaba entre corridas. La
selección es **geográfica**: se acepta un archivo sólo si sus puntos caen dentro
de la caja de la CDMX. El nombre busca candidatos; los datos deciden.

**Precio de oferta ≠ precio de cierre.** Todo lo que entra es *asking*. En
México no hay MLS abierto ni Registro Público accesible, así que el cierre no es
observable. El descuento oferta→cierre existe y es positivo, pero
`config.yaml` lo deja en `null` **a propósito**: se declara que se desconoce en
vez de inventar un porcentaje plausible. Se calibrará cuando haya transacciones.

**El vocabulario de la fuente manda.** El DENUE del repo no viene con los ~20
sectores SCIAN sino agregado a **cuatro**: Servicios, Comercio, Alimentos e
Industria. La primera versión declaraba familias de salud, educación y ocio que
esa fuente no puede producir: generaban columnas enteras de NaN y una falsa
sensación de cobertura. Salud y educación llegan de OSM, que sí las tiene una
por una.

**Rendimiento.** Las distancias, conteos y accesibilidad pasan por árboles KD
de scipy. La primera versión recorría los pares en Python: con 12 mil celdas y
351 mil establecimientos, el pipeline no terminaba. Es la misma matemática, y
hay una prueba que compara el resultado contra haversine.

**La memoria se mide, no se supone.** La accesibilidad partía los orígenes en
bloques fijos de 4,000. Medido sobre el lago real, cada celda tiene **17,123
destinos DENUE de media dentro de 5 km, y hasta 98,476** en el centro: un bloque
pedía 68 millones de pares y el pico pasaba de 4 GB. Pasaba en una máquina de 16
GB y moría con `MemoryError: std::bad_alloc` en una normal — el clásico "en mi
máquina funciona". Ahora se muestrea la densidad, se toma el percentil 95 (no la
media: los orígenes van ordenados por índice H3, que es espacialmente coherente,
así que un bloque entero puede caer en la zona más densa) y el bloque se elige
para caber en un presupuesto de pares explícito; si aun así falta memoria, se
parte a la mitad y se reintenta. Pico: **0.96 GB**, y de paso más rápido, 0.8
min. El tamaño de bloque es un parámetro de rendimiento y **no puede mover el
resultado**: hay una prueba que lo verifica con presupuestos de 5 mil a 50
millones de pares.

**Determinismo.** Semilla fija en `config.yaml`, orden estable en toda selección
de archivos, y una prueba que lo verifica.

**Procedencia.** Cada capa del lago escribe su entrada en `_manifiesto.json`:
filas, fuente, CRS y fecha. Sin eso no hay auditoría, y el documento pide que un
banco o una autoridad puedan auditar el sistema.

---

## Estructura

```
atlas/
├─ config.yaml            todo parámetro ajustable vive aquí
├─ atlas/
│  ├─ config.py           carga única + semillas
│  ├─ geo.py              CRS, distancias, accesibilidad gravitacional, H3
│  ├─ esquema.py          tabla `properties`, validación, dedup
│  ├─ lago.py             parquet + manifiesto de procedencia
│  └─ ingesta/
│     ├─ denue.py         establecimientos (verificados geográficamente)
│     ├─ base_geo.py      códigos postales y red vial
│     ├─ osm.py           Overpass — se corre en local
│     └─ listados.py      salida del scraper C21 → properties
│  └─ features/
│     ├─ malla.py         malla H3 de la CDMX (el sustrato de la tela)
│     ├─ pesos.py         W, rezagos, I de Moran, LISA
│     └─ amenidades.py    distancias, conteos, accesibilidad gravitacional
│  └─ modelos/
│     ├─ datos.py         ensamblado + partición por bloque espacial
│     ├─ hedonico.py      OLS semi-log y Durbin espacial (SDM)
│     ├─ arboles.py       boosting de media y de cuantiles
│     ├─ apilado.py       combinación con pesos fuera de muestra
│     ├─ conforme.py      CQR y normalizado + Mondrian: intervalos con garantía
│     ├─ evaluacion.py    error en pesos y cobertura por segmento
│     └─ importancia.py   SHAP, con permutación de respaldo
│  └─ temporal/
│     ├─ indice.py        panel SHF: 32 zonas × 22 años
│     └─ difusion.py      ¿se contagia el crecimiento? validación hacia adelante
│  └─ campo/
│     ├─ superficie.py    proceso gaussiano, gradiente ∇p e incertidumbre
│     └─ multiplicador.py (I − ρW)⁻¹: dónde un cambio mueve más ciudad
├─ pipelines/
│  ├─ fase0.py            ingesta + informe
│  ├─ fase1.py            variables geoespaciales + diagnóstico
│  ├─ fase2.py            AVM + incertidumbre calibrada
│  └─ fase3.py            tiempo + campo espacial
├─ tests/                 75 pruebas
└─ data/                  el lago (parquet); no se versiona
```

---

## Siguientes fases

*(Fase 1 completa: W, rezagos, Moran, LISA, accesibilidad. Falta de la Fase 1
el delta de accesibilidad por obra pública, que necesita la capa de obras.)*

2. ~~**AVM + incertidumbre**~~ **hecha**, salvo MGWR: hedónico semi-log, SDM
   (`spreg`), boosting de media y cuantiles, apilado, **CQR + Mondrian** y SHAP.
   Los coeficientes locales de MGWR quedan pendientes a propósito: con ~1,600
   inmuebles de venta y 19 bloques espaciales, estimar una superficie de
   coeficientes por variable daría mapas bonitos y sin respaldo. Entra cuando la
   muestra lo aguante.
3. ~~**Temporal + campo de crecimiento**~~ **hecha**, salvo el crecimiento por
   celda: índice SHF, prueba de difusión con validación hacia adelante,
   superficie por proceso gaussiano con gradiente e incertidumbre, y el
   multiplicador `(I−ρW)⁻¹`. El campo de crecimiento por celda queda
   explícitamente pendiente de la segunda captura de listados; las ventas
   repetidas necesitan lo mismo.
4. **App Streamlit** — mapa-tela, campo vectorial, escenarios de obra pública.
5. **Monitoreo** — drift de datos y de cobertura, reentrenamiento.

Lo que condiciona la calidad de la Fase 2 no es el código sino el tamaño de la
muestra: 2,144 inmuebles y 19 bloques espaciales. El intervalo sale honesto pero
ancho, y se estrecha con más inventario, no con más modelo.

---

## Aviso

Este sistema produce estimaciones a partir de precios de oferta. **No es un
avalúo con validez legal** salvo que lo suscriba un perito valuador, ni asesoría
financiera. Ninguna cifra se muestra sin su intervalo.
