# BrickBit Atlas — Motor de Inteligencia Inmobiliaria de la CDMX

Motor de valuación y pronóstico para la Ciudad de México. Vive **al lado** del
Motor de Morfogénesis (`app.py`), no dentro: son dos productos con datos y
ciclos de vida distintos, y mezclarlos habría hecho a los dos más frágiles.

**Estado: Fases 0, 1 y 2 completas.** Las fases 3 a 5 están por construir.

---

## Lo primero que hay que saber

**La muestra de la CDMX es delgada: 2,144 inmuebles.**

Durante un tiempo el bloqueo fue no tener ningún listado individual —sin precio
+ m² + atributos por inmueble no hay AVM, ni SHAP, ni intervalo conforme—. Eso
ya se resolvió: el scraper autorizado de Century 21 corrió sobre el país entero
y de sus **18,380 propiedades**, 2,144 caen dentro de la CDMX y sobreviven a la
validación. La Fase 2 puede arrancar.

Pero 2,144 para 16 alcaldías **no da para intervalos estrechos**, y menos por
segmento. Conviene saberlo antes de leer el primer resultado del AVM: las bandas
van a salir anchas, y eso será una propiedad honesta del dato, no un defecto del
modelo. Dos cosas engordan la muestra, las dos documentadas más abajo: arreglar
las siete alcaldías que el scraper no supo pedir, y volver a correrlo cada mes
—cada corrida agrega inventario nuevo y, de paso, alimenta la serie temporal—.

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
en la Fase 2, sobre los 2,144 listados.

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
equivoca 20% y lo dice sirve; uno que se equivoca 12% y no lo dice, no. Sobre
los datos reales de la CDMX la conformalización subió la cobertura de **77.7% a
97.8%** contra un objetivo de 95%: no estaba afinando un intervalo casi bueno,
estaba arreglando uno que cubría tres cuartas partes de lo que prometía.

**Pero cubrir no es servir**, y el informe lo dice cuando toca. La primera
corrida real dio ±139% de ancho: garantía perfecta, utilidad nula.

Parte de eso era ineficiencia y se puede recuperar. Con un error mediano del 25%,
un intervalo del 95% *eficiente* mide **±69%**; el de CQR daba el doble. La causa
es que CQR tiene que estimar los cuantiles 2.5% y 97.5% **directamente**, y esa
cola se apoya en el 2.5% de las observaciones —unas 24 de 953—. Así que se
calibran **dos** formas, con la misma garantía y distinto ancho:

| | qué estima | con cuántas observaciones |
|---|---|---|
| CQR | los cuantiles 2.5% y 97.5% | las ~24 de cada cola |
| Normalizado | \|y − ŷ\| / σ̂(x) | las 953 |

El normalizado sigue siendo adaptativo —donde el modelo sabe menos, σ̂ es grande
y el intervalo se abre— y de regalo permite cambiar el nivel de confianza sin
reentrenar nada: es otro cuantil de los mismos scores. El informe imprime la
tabla de qué cuesta cada nivel (50 / 80 / 90 / 95%).

**El ruido en σ̂ se paga en ancho, y no compra cobertura.** Medido en simulación:
con la misma cobertura, una σ̂ ruidosa infla la corrección conforme de 1.92 a
3.44 y casi DUPLICA el ancho. Se vio en producción cuando entró OSM: el error
puntual mejoró (mediana 24.7% → 22.0%) y el intervalo se ENSANCHÓ (±107% →
±126%), porque σ̂ con 137 variables y 953 filas se volvió más ruidosa. Dos
remedios: σ̂ se ajusta con un modelo más suave que la media —es un parámetro de
estorbo, su trabajo es la FORMA del ancho, no acertar— y el score se calcula
sobre σ̂(x) + γ, la estabilización aditiva de Lei et al. (2018). γ se elige
midiendo el ancho sobre datos fuera de muestra del entrenamiento. Se puede
elegir por ancho sin miedo porque **todos los γ dan intervalos válidos**: la
garantía no depende de que σ̂ sea correcta.

Lo que NO se recupera con método es el resto: el modelo se equivoca ~25% en la
mediana, y un intervalo honesto sobre ese error tiene que ser ancho. Eso se
estrecha con más inventario y mejores atributos.

**La intercambiabilidad se rompe a propósito.** La garantía conforme exacta
supone que calibración y despliegue son intercambiables, y la partición por
bloque hace que sean barrios DISTINTOS. Por eso la cobertura medida puede caer
un par de puntos bajo el objetivo. No se corrige subiendo el nivel hasta que el
número quede bonito: es la condición real de uso —valuar donde no hubo
comparables— y con una partición al azar el número saldría clavado y no diría
nada sobre el barrio siguiente.

Lo que sí midió bien la primera corrida real:

| | |
|---|---|
| I de Moran del **precio** | **0.444** (p=0.001) con knn(5) |
| SDM · ρ | **+0.377** (p = 4.8e-21), pseudo R² 0.574 |
| Error del apilado en prueba | mediana 23.9% · dentro de ±20%: 43.7% |

El ρ de 0.38 con esa significancia es el hallazgo de fondo de la fase: el precio
de un inmueble en la CDMX depende materialmente del de sus vecinos, y un modelo
sin componente espacial estaría mal especificado. Ya no es un supuesto heredado
de la Fase 1 —que se midió sobre densidad de empleo—, es una medición sobre
precios.

Decisiones que conviene conocer, todas encontradas midiendo:

- **El segmento de Mondrian sale de la PREDICCIÓN, no del precio real.** Al
  valuar un inmueble su precio es justamente lo que no se sabe; un grupo que
  dependiera de él daría una cobertura preciosa en la evaluación y sería
  inaplicable en producción. Es fuga en la variable objetivo, la hermana de la
  fuga espacial que evita la partición por bloques.
- **La segmentación se adapta al tamaño de la calibración.** Con 290 inmuebles,
  `tipo × tercil` daba nueve grupos y ocho quedaban bajo el mínimo: Mondrian no
  hacía nada mientras el informe *parecía* segmentado. Ahora baja a una
  segmentación que la muestra sí sostiene, y dice cuál eligió.
- **El W del SDM es KNN, no banda de distancia.** Una banda deja islas —puntos
  sin ningún vecino dentro del umbral— y sobre ellas la verosimilitud del modelo
  de rezago no converge: medido, daba ρ = −0.93 con pseudo R² de 0.002, que no
  es un hallazgo económico sino un síntoma numérico. Con KNN: ρ = +0.21
  (p = 0.007), pseudo R² = 0.36.
- **El diseño se pasa por QR pivotante y después por VIF.** El QR sólo ve
  dependencias EXACTAS; la colinealidad real es casi-exacta y pasaba entera. En
  los datos de la CDMX salieron `dist_servicios_m` en −0.91 y `dist_abasto_m` en
  +0.78 —dos variables que miden casi lo mismo, con signos opuestos— y el
  hedónico se derrumbó de R²=0.456 dentro de muestra a **R²=0.002 fuera**. No es
  sobreajuste: unos coeficientes que se cancelan entre sí no transfieren a otro
  barrio.
- **Interpretar y predecir son dos trabajos, y se hacen con dos herramientas.**
  Para LEER el modelo, OLS sobre variables podadas por VIF, con errores robustos.
  Para PREDECIR, cresta con el α elegido por validación cruzada espacial: la
  penalización reparte el peso entre variables colineales en vez de dárselo todo
  a una con signo arbitrario.
- **Los grupos chicos de Mondrian se juntan y se calibran juntos**, en vez de
  caer a la corrección global. La global la dominan los segmentos numerosos:
  medido, `depto·barato` —12 inmuebles en calibración— cubrió **69.6%** cuando
  prometía 95%. Un intervalo del 95% que cubre 70% no es un intervalo del 95%.
- **La categoría de referencia no es "otro".** La fila sin ninguna indicadora
  encendida es la categoría que se dejó fuera del diseño. En los datos reales
  resultó ser `casa`, y las 144 casas de la calibración salían en el informe
  como "otro" mientras el segmento `casa` no existía. Se detectó porque la
  salida traía depto, otro y terreno y ninguna casa, que en un inventario
  inmobiliario es imposible.

### Cobertura de la CDMX: siete alcaldías con ruta rota

En la corrida del scraper de 2026-09 el barrido profundo devolvió **HTTP 404 en
la página 1** para Benito Juárez, Cuauhtémoc, Coyoacán, Álvaro Obregón, Gustavo
A. Madero, Venustiano Carranza y La Magdalena Contreras. Un 404 no es "no hay
inventario": es una ruta que no existe. Son casi la mitad de la ciudad y las de
mayor valor por m², así que el AVM las tendría prácticamente ciegas.

`tools/c21-scraper.mjs` ahora resuelve el filtro **por municipio** en vez de
aplicarle a todos el segmento que funcionó con el primero, y prueba variantes
del slug (sin artículo, sin inicial, con acentos, con el estado para desambiguar
homónimos). Y trae un modo que sólo mide:

```bash
node tools/c21-scraper.mjs sondeo --estado ciudad-de-mexico
```

Imprime, para cada alcaldía, qué contestó cada ruta candidata. Se corre en local
porque el portal rechaza las IP de nube, igual que INEGI y Overpass.

### Qué ingiere hoy, sin red

| Capa | Filas | Fuente |
|---|---:|---|
| `denue` | 351,631 | INEGI DENUE, 9 de 16 alcaldías |
| `cp` | 1,182 | Polígonos de código postal de la CDMX |
| `calles` | 9,090 | Ejes viales por alcaldía |
| `properties` | 2,144 | Century 21 — de 18,380 nacionales, los de la CDMX |

### Lo que se corre en tu máquina

Overpass (OSM), el portal de datos de la CDMX e INEGI **rechazan las IP de
nube**. Comprobado desde este contenedor: reset de conexión. Es el mismo patrón
que ya seguían `tools/riesgos_local.py` y `tools/macro_local.py`.

```bash
python -m pipelines.fase0 --osm      # parques, plazas, Metro, Metrobús, Cablebús…
python scripts/ingerir_denue.py      # las 7 alcaldías que faltan
```

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
├─ pipelines/
│  ├─ fase0.py            ingesta + informe
│  ├─ fase1.py            variables geoespaciales + diagnóstico
│  └─ fase2.py            AVM + incertidumbre calibrada
├─ tests/                 63 pruebas
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
3. **Temporal + campo de crecimiento** — índice SHF/ventas repetidas, VECM,
   superficies por kriging/GP, gradiente ∇g, pesos `(I−ρW)⁻¹`.
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
