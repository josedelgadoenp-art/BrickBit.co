# Herramientas de Abak

**Este archivo se genera solo.** Sale del registro (`abak_core/nodes/`), así que
no puede quedar desactualizado. Para regenerarlo: `python tools/generar_docs.py`.

66 herramientas en 13 familias.

| Familia | Herramientas | Para qué |
|---|---:|---|
| [Datos](#datos) | 13 | Traer datos al analisis y prepararlos: archivos, ejemplos, uniones, filtros. |
| [Fuentes oficiales](#fuentes) | 3 | Series en vivo de INEGI y Banxico. Se guardan en cache: el analisis reproduce los mismos numeros aunque la fuente revise la serie. |
| [Transformar](#transformar) | 7 | Crear variables nuevas: logaritmos, tasas de crecimiento, rezagos, deflactar, estandarizar. |
| [Explorar](#explorar) | 3 | Mirar los datos antes de modelarlos: descriptivos, correlaciones, tablas cruzadas, pruebas. |
| [Econometria](#econometria) | 7 | Regresiones y modelos de siempre: MCO, variables instrumentales, panel, eleccion discreta. |
| [Inferencia causal](#causal) | 1 | Dibuja que causa que y deja que el criterio de puerta trasera decida los controles. |
| [Series de tiempo](#series) | 5 | Todo lo que tiene fecha: raiz unitaria, ARIMA, VAR, impulso-respuesta, cointegracion, ciclos. |
| [Econometria espacial](#espacial) | 6 | Cuando la ubicacion importa: matrices de vecindad, Moran, LISA, SAR y SEM. |
| [Macro e insumo-producto](#macro) | 4 | Estructura productiva: Leontief, multiplicadores, encadenamientos, impacto sectorial, keynesiano. |
| [Inmobiliario](#inmobiliario) | 1 | Indices de precios de calidad constante y herramientas de mercado inmobiliario. |
| [Machine learning](#ml) | 3 | Prediccion con XGBoost y validacion honesta para series y panel. |
| [Graficos](#graficos) | 11 | Gramatica por capas: un lienzo y encima puntos, lineas, bandas, tendencias y facetas. |
| [Entregables](#salida) | 2 | Lo que te llevas: tablas de publicacion, exportar a Excel o CSV, informe en PDF. |

<a id="datos"></a>

## Datos

Traer datos al analisis y prepararlos: archivos, ejemplos, uniones, filtros.

### Agrupar y resumir

`datos.agrupar` · v1.0.0

**Qué hace.** Junta las filas por una o varias columnas y calcula un resumen por grupo.

**Cuándo usarlo.** Para pasar de microdatos a agregados: de hogares a entidades, de dias a meses.

**Cómo se lee el resultado.** Cada fila del resultado es un grupo. Ojo con el numero de observaciones por grupo: un promedio de tres casos no es un promedio.

**Ten cuidado con:**

- Agregar destruye la variabilidad dentro del grupo. Si tu pregunta es sobre individuos, no la respondas con datos agregados (falacia ecologica).

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | datos | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `por` | `—` |
| `columnas` | `—` |
| `funcion` | `mean` |

Si vienes de otro sistema — **Stata**: `collapse` · **R**: `dplyr::group_by() %>% summarise()`

### Cambiar de ancho a largo (o al reves)

`datos.remodelar` · v1.0.0

**Qué hace.** Reacomoda la tabla: de una columna por anio a una fila por anio, o al contrario.

**Cuándo usarlo.** Casi todas las herramientas estadisticas piden formato largo (una fila por observacion). Las hojas de calculo casi siempre vienen en ancho.

**Cómo se lee el resultado.** El numero total de datos no cambia; cambia como estan acomodados.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | datos | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `direccion` | `a_largo` |
| `identificadores` | `—` |
| `columnas` | `—` |
| `nombre_variable` | `variable` |
| `nombre_valor` | `valor` |

Si vienes de otro sistema — **Stata**: `reshape long` · **R**: `tidyr::pivot_longer()`

### Cargar archivo (CSV o Excel)

`datos.csv` · v1.0.0

**Qué hace.** Lee un archivo que subiste y lo convierte en una tabla. Al subirlo se guarda en formato columnar, que es lo que permite trabajar con archivos de millones de filas.

**Cuándo usarlo.** Es casi siempre el primer paso de un analisis propio.

**Cómo se lee el resultado.** Revisa en la pestana Datos que las columnas se hayan leido con el tipo correcto y cuantos faltantes trae cada una. Una columna numerica leida como texto es la causa mas comun de errores mas adelante.

**Supuestos que impone:**

- Los tipos se deducen de una muestra grande del archivo y luego se aplican a todo. Es a proposito: dejar que se deduzcan trozo por trozo produce columnas de tipo mixto que fallan raro y sin avisar.

**Ten cuidado con:**

- Si los numeros traen coma decimal, indicalo al subir el archivo o se leeran como texto.
- Abak lee del archivo SOLO las columnas que tu analisis usa. Si agregas un bloque que necesita otra columna, se lee tambien: no hay que volver a subir nada.

| | Puerto | Tipo |
|---|---|---|
| sale | Tabla | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `archivo_id` | `—` |
| `nombre` | `datos.csv` |
| `columnas` | `—` |
| `n_filas` | `0` |
| `tope_filas` | `None` |

Si vienes de otro sistema — **Stata**: `import delimited` · **R**: `arrow::read_parquet()` · **SPSS**: `Abrir datos`

### Datos de ejemplo

`datos.ejemplo` · v1.0.0

**Qué hace.** Carga uno de los conjuntos que trae Abak para aprender y probar.

**Cuándo usarlo.** Cuando quieras entender como funciona una herramienta antes de usarla con tus propios datos.

**Cómo se lee el resultado.** El resultado es una tabla lista para conectar a cualquier otra herramienta.

**Ten cuidado con:**

- Estos datos son para practicar. Las columnas marcadas en ambar son estimaciones o simulaciones: no sirven para sustentar una decision ni para citarse.

| | Puerto | Tipo |
|---|---|---|
| sale | Tabla | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `conjunto` | `mexico_estados` |

Si vienes de otro sistema — **Stata**: `sysuse auto` · **R**: `data(mtcars)`

### Definir panel

`datos.panel` · v1.0.0

**Qué hace.** Declara cual columna identifica a la entidad (estado, empresa, hogar) y cual al periodo.

**Cuándo usarlo.** Antes de estimar efectos fijos o aleatorios.

**Cómo se lee el resultado.** El resultado tiene un indice de dos niveles: entidad y tiempo. Es lo que permite que un modelo distinga la variacion entre entidades de la variacion dentro de cada una.

**Supuestos que impone:**

- La pareja (entidad, periodo) debe ser unica: no puede haber dos filas del mismo estado en el mismo anio.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | Panel | Una tabla de panel: varias entidades observadas en varios periodos |

| Parámetro | Por omisión |
|---|---|
| `entidad` | `—` |
| `periodo` | `—` |

Si vienes de otro sistema — **Stata**: `xtset entidad anio` · **R**: `plm::pdata.frame()`

### Definir serie temporal

`datos.serie_temporal` · v1.0.0

**Qué hace.** Le dice a Abak cual columna es la fecha y cada cuanto estan medidos los datos.

**Cuándo usarlo.** Antes de cualquier herramienta de series de tiempo: ADF, ARIMA, VAR, filtros de ciclo.

**Cómo se lee el resultado.** Despues de este paso la tabla queda ordenada por fecha y con la frecuencia declarada. Si aparecen filas nuevas con huecos, es que tu serie tenia periodos faltantes: es mejor enterarse aqui que dentro de un modelo.

**Supuestos que impone:**

- Los periodos deben estar espaciados de forma regular; si no, los rezagos no significan lo mismo en cada punto.

**Ten cuidado con:**

- Sin frecuencia declarada, statsmodels adivina, y cuando adivina mal el pronostico sale con fechas equivocadas.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | Serie | Una tabla con fecha: cada fila es un periodo en orden |

| Parámetro | Por omisión |
|---|---|
| `columna_fecha` | `—` |
| `frecuencia` | `QS` |
| `rellenar_huecos` | `True` |

Si vienes de otro sistema — **Stata**: `tsset fecha, quarterly` · **R**: `ts()` · **EViews**: `Structure/Resize`

### Definir ubicacion

`datos.ubicacion` · v1.0.0

**Qué hace.** Declara que columnas traen la latitud y la longitud de cada fila.

**Cuándo usarlo.** Antes de construir una matriz de pesos espaciales o de dibujar un mapa.

**Cómo se lee el resultado.** No cambia los datos: marca la tabla como geografica para que las herramientas espaciales la acepten.

**Ten cuidado con:**

- En Mexico la longitud es NEGATIVA (alrededor de -99). Si te salen puntos en China, estan invertidas la latitud y la longitud.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | Tabla con ubicacion | Una tabla con ubicación: cada fila tiene coordenadas o geometría |

| Parámetro | Por omisión |
|---|---|
| `latitud` | `lat` |
| `longitud` | `lng` |
| `etiqueta` | `None` |

Si vienes de otro sistema — **Stata**: `spset` · **R**: `sf::st_as_sf()`

### Elegir columnas

`datos.seleccionar` · v1.0.0

**Qué hace.** Se queda solo con las columnas que elijas, o quita las que no quieras.

**Cuándo usarlo.** Para aligerar la tabla y para que los desplegables de los siguientes pasos no sean un mar.

**Cómo se lee el resultado.** No cambia ninguna cifra: solo reduce el ancho de la tabla.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | datos | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `columnas` | `—` |
| `modo` | `conservar` |

Si vienes de otro sistema — **Stata**: `keep varlist` · **R**: `dplyr::select()`

### Filtrar filas

`datos.filtrar` · v1.0.0

**Qué hace.** Se queda solo con las filas que cumplen las condiciones que pongas.

**Cuándo usarlo.** Para analizar un subconjunto: un periodo, una region, un rango de precios.

**Cómo se lee el resultado.** Revisa cuantas filas quedaron. Si quedaron muy pocas, cualquier modelo que estimes despues va a tener errores estandar enormes.

**Ten cuidado con:**

- Filtrar por una variable relacionada con lo que quieres explicar introduce sesgo de seleccion: los resultados dejan de aplicar a la poblacion completa.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | datos | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `condiciones` | `—` |
| `unir_con` | `y` |

Si vienes de otro sistema — **Stata**: `keep if` · **R**: `dplyr::filter()` · **SPSS**: `Seleccionar casos`

### Ordenar filas

`datos.ordenar` · v1.0.0

**Qué hace.** Acomoda las filas por el valor de una o varias columnas.

**Cuándo usarlo.** Para ver los extremos, o antes de calcular rezagos y diferencias en datos con fecha.

**Cómo se lee el resultado.** No cambia ninguna cifra: cambia el orden en que las ves.

**Ten cuidado con:**

- En series de tiempo y panel el orden SI importa: un rezago sobre filas desordenadas produce numeros sin sentido y sin ningun aviso.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | datos | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `por` | `—` |
| `descendente` | `False` |

Si vienes de otro sistema — **Stata**: `sort` · **R**: `dplyr::arrange()`

### Trabajar sobre una muestra

`datos.muestra` · v1.0.0

**Qué hace.** Toma una muestra al azar para que el analisis corra en segundos, y te dice cuanta precision estas entregando a cambio, columna por columna.

**Cuándo usarlo.** Mientras exploras un archivo de millones de filas. Cuando ya sepas que analisis quieres, prende «usar todo» y el mismo lienzo corre sobre la poblacion completa.

**Cómo se lee el resultado.** `margen_95_pct` dice cuanto se puede mover la media de esa columna por el puro hecho de haber muestreado, en porcentaje de la media. Si es 0.4%, la muestra no te esta costando nada; si es 12%, cualquier conclusion fina sobre esa columna es de la muestra, no del mercado.

**Supuestos que impone:**

- La muestra es aleatoria: si tus filas vienen ordenadas por algo que importa, usa el estrato para no perder grupos chicos

**Ten cuidado con:**

- El error de muestreo es ADICIONAL al error estadistico normal. No lo sustituye ni se anula con el.
- Un resultado sacado de una muestra se reporta diciendo que es de una muestra, y con que tamaño. Esta tabla es para copiarla al reporte.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | La muestra | Una tabla de datos (filas y columnas) |
| sale | Que precision entregas | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `n` | `50000` |
| `metodo` | `aleatorio` |
| `estrato` | `None` |
| `usar_todo` | `False` |

Si vienes de otro sistema — **Stata**: `sample 5` · **R**: `dplyr::slice_sample(n = 50000)` · **Python**: `df.sample(50_000)`

Para leer más: Cochran, «Sampling Techniques» (1977), caps. 2 y 5

### Tratar datos faltantes

`datos.faltantes` · v1.0.0

**Qué hace.** Decide que hacer con los huecos: quitarlos o rellenarlos.

**Cuándo usarlo.** Cuando un modelo se queja de valores faltantes, o antes de estimar cualquier cosa.

**Cómo se lee el resultado.** Fijate en cuantas filas perdiste. Si perdiste muchas, el problema no es tecnico: puede que el modelo este descansando en una submuestra que no representa al total.

**Supuestos que impone:**

- Quitar filas solo es inofensivo si los datos faltan al azar (MCAR).

**Ten cuidado con:**

- Rellenar con la media reduce la varianza artificialmente y aprieta los errores estandar. Es comodo, no es inocuo.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | datos | Una tabla de datos (filas y columnas) |
| sale | Que se perdio | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `metodo` | `quitar_filas` |
| `columnas` | `—` |

Si vienes de otro sistema — **Stata**: `drop if missing()` · **R**: `na.omit()`

### Unir dos tablas

`datos.unir` · v1.0.0

**Qué hace.** Pega dos tablas usando una o varias columnas en comun (una llave).

**Cuándo usarlo.** Cuando tus datos vienen en pedazos: precios en una tabla, poblacion en otra.

**Cómo se lee el resultado.** Fijate en cuantas filas quedaron. Si crecieron mucho, la llave no es unica en alguna de las dos tablas y estas multiplicando filas sin querer.

**Ten cuidado con:**

- Con «solo las que coinciden» pierdes en silencio las filas que no encuentran pareja. Usa «todas las de la izquierda» si quieres ver cuales se quedaron sin match.

| | Puerto | Tipo |
|---|---|---|
| entra | izquierda | Una tabla de datos (filas y columnas) |
| entra | derecha | Una tabla de datos (filas y columnas) |
| sale | datos | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `llave_izquierda` | `—` |
| `llave_derecha` | `—` |
| `tipo` | `izquierda` |

Si vienes de otro sistema — **Stata**: `merge` · **R**: `dplyr::left_join()`

<a id="fuentes"></a>

## Fuentes oficiales

Series en vivo de INEGI y Banxico. Se guardan en cache: el analisis reproduce los mismos numeros aunque la fuente revise la serie.

### Banxico (SIE)

`fuentes.banxico` · v1.0.0

**Qué hace.** Descarga series del Sistema de Informacion Economica de Banxico: tipo de cambio, TIIE, tasa objetivo, INPC, IGAE y cualquier otra por su clave.

**Cuándo usarlo.** Cuando el analisis necesita datos macro reales y actuales, en vez de un ejemplo.

**Cómo se lee el resultado.** El resultado es una tabla con la fecha en el indice y una columna por serie. Abajo se muestra el TITULO OFICIAL que devolvio Banxico para cada clave: si no es el que esperabas, la clave esta mal.

**Supuestos que impone:**

- Hace falta un token gratuito del SIE en la variable de entorno BANXICO_TOKEN. El token no se guarda en el analisis ni viaja en el codigo exportado.

**Ten cuidado con:**

- Banxico rechaza peticiones desde IPs de centros de datos. Si el servidor no tiene salida, corre `python tools/traer_datos.py` desde una computadora con conexion domestica: llena la cache y el servidor deja de necesitar red.
- La primera descarga se guarda en cache y el analisis vuelve a usar ESE archivo. Es a proposito: un resultado no debe cambiar solo porque la fuente revisó la serie. Para traer datos nuevos, marca «volver a descargar».
- Las claves sugeridas son un atajo, no un catalogo verificado: confirma siempre el titulo que aparece en el resultado.

| | Puerto | Tipo |
|---|---|---|
| sale | Series de Banxico | Una tabla con fecha: cada fila es un periodo en orden |

| Parámetro | Por omisión |
|---|---|
| `series` | `['SF43718']` |
| `inicio` | `None` |
| `fin` | `None` |
| `volver_a_descargar` | `False` |

Si vienes de otro sistema — **Stata**: `import delimited (descarga manual)` · **R**: `siebanxicor::getSeriesData()`

Para leer más: https://www.banxico.org.mx/SieAPIRest/service/v1/doc/catalogoSeries

### DENUE (establecimientos)

`fuentes.denue` · v1.0.0

**Qué hace.** Trae los establecimientos economicos que el INEGI tiene registrados alrededor de un punto: nombre, actividad, tamano y ubicacion.

**Cuándo usarlo.** Para medir la economia de una zona: cuantos negocios hay, de que tipo y de que tamano. Es el insumo natural de un analisis de ubicacion.

**Cómo se lee el resultado.** Cada fila es un establecimiento. El «estrato» es un rango de personal ocupado, no un numero exacto: el DENUE no publica el empleo puntual de cada negocio.

**Supuestos que impone:**

- El radio maximo que admite la API es de 5,000 metros.

**Ten cuidado con:**

- Esta es LA fuente que bloquea IPs de centros de datos: al proyecto ya le pasó con la funcion `denue.js`, que quedó inservible por eso. Cuenta con llenar la cache desde una computadora con conexion domestica.
- El DENUE se actualiza por oleadas: un establecimiento cerrado puede seguir apareciendo, y uno nuevo puede faltar.

| | Puerto | Tipo |
|---|---|---|
| sale | Establecimientos | Una tabla con ubicación: cada fila tiene coordenadas o geometría |

| Parámetro | Por omisión |
|---|---|
| `condicion` | `todos` |
| `latitud` | `19.4326` |
| `longitud` | `-99.1332` |
| `metros` | `1000` |
| `volver_a_descargar` | `False` |

Para leer más: https://www.inegi.org.mx/servicios/api_denue.html

### INEGI (BIE / BISE)

`fuentes.inegi` · v1.0.0

**Qué hace.** Descarga indicadores del Banco de Informacion Economica (BIE) o del BISE de INEGI: PIB, IGAE, ocupacion, INPC, produccion industrial y cualquier otro por su clave.

**Cuándo usarlo.** Cuando necesitas la serie oficial mexicana en vez de una aproximacion.

**Cómo se lee el resultado.** Cada columna es un indicador, con el periodo en el indice. Revisa la frecuencia que reporta INEGI: mezclar una serie mensual con una trimestral sin homologarlas produce huecos que despues se ven como datos faltantes.

**Supuestos que impone:**

- Hace falta un token gratuito de INEGI en la variable de entorno INEGI_TOKEN. No se guarda en el analisis ni viaja en el codigo exportado.
- El area geografica va por clave del catalogo de INEGI: 0700 es nacional.

**Ten cuidado con:**

- INEGI rechaza peticiones desde IPs de centros de datos. Es el mismo problema que ya tenia el resto del proyecto. Si el servidor no tiene salida, llena la cache con `python tools/traer_datos.py` desde una computadora con conexion domestica.
- Una serie descargada queda en cache y el analisis vuelve a usar ESE archivo, para que el resultado no cambie solo porque INEGI revisó la serie.

| | Puerto | Tipo |
|---|---|---|
| sale | Indicadores de INEGI | Una tabla con fecha: cada fila es un periodo en orden |

| Parámetro | Por omisión |
|---|---|
| `indicadores` | `—` |
| `area` | `0700` |
| `banco` | `BIE` |
| `volver_a_descargar` | `False` |

Si vienes de otro sistema — **R**: `inegiR::inegi_series()` · **Stata**: `descarga manual`

Para leer más: https://www.inegi.org.mx/servicios/api_indicadores.html

<a id="transformar"></a>

## Transformar

Crear variables nuevas: logaritmos, tasas de crecimiento, rezagos, deflactar, estandarizar.

### Calcular variable

`transformar.calcular` · v1.0.0

**Qué hace.** Crea una columna nueva aplicando una operacion a una o dos columnas existentes.

**Cuándo usarlo.** El logaritmo es el caso mas comun en economia: convierte un efecto multiplicativo en uno aditivo y hace que los coeficientes se lean como elasticidades.

**Cómo se lee el resultado.** En un modelo log-log, el coeficiente es la elasticidad: si sube 1% la explicativa, la dependiente cambia ese porcentaje.

**Ten cuidado con:**

- El logaritmo de cero o de un numero negativo no existe: esas filas quedan como huecos.
- Dividir entre una columna que tiene ceros produce infinitos.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | datos | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `operacion` | `log` |
| `columna_a` | `—` |
| `columna_b` | `None` |
| `nombre_nuevo` | `` |

Si vienes de otro sistema — **Stata**: `gen lny = log(y)` · **R**: `mutate(lny = log(y))`

### Crear indicadoras (dummies)

`transformar.dummies` · v1.0.0

**Qué hace.** Convierte una columna de categorias en varias columnas de ceros y unos.

**Cuándo usarlo.** Cuando quieres meter una variable cualitativa (region, sector, tipo) en una regresion.

**Cómo se lee el resultado.** Cada coeficiente compara esa categoria contra la que se dejo fuera (la base). No hay una categoria «neutral»: siempre se lee contra la base.

**Supuestos que impone:**

- Hay que quitar una categoria, o el modelo cae en la trampa de las dummies (colinealidad perfecta con la constante).

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | datos | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `columnas` | `—` |
| `quitar_primera` | `True` |

Si vienes de otro sistema — **Stata**: `i.region` · **R**: `factor()` · **SPSS**: `Recodificar en distintas variables`

### Deflactar (pasar a precios constantes)

`transformar.deflactar` · v1.0.0

**Qué hace.** Divide una variable nominal entre un indice de precios para dejarla en valores reales.

**Cuándo usarlo.** Siempre que compares cantidades de dinero de anios distintos. Comparar pesos corrientes de 2010 con los de 2025 no dice nada.

**Cómo se lee el resultado.** El resultado esta en pesos del periodo base que elijas. Si el valor real baja mientras el nominal sube, el poder de compra cayo.

**Supuestos que impone:**

- El indice de precios debe corresponder a la misma cobertura geografica y de canasta que la variable.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | datos | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `columnas` | `—` |
| `indice_precios` | `—` |
| `base` | `100.0` |

Si vienes de otro sistema — **Stata**: `gen real = nominal / inpc * 100`

### Estandarizar variables

`transformar.estandarizar` · v1.0.0

**Qué hace.** Pone las variables en una escala comun: z (media 0, desviacion 1) o de 0 a 1.

**Cuándo usarlo.** Para comparar coeficientes de variables medidas en unidades distintas, y porque muchos metodos de machine learning lo necesitan.

**Cómo se lee el resultado.** Con z, un coeficiente dice cuanto cambia la dependiente si la explicativa sube una desviacion estandar. Es la forma honesta de decir «cual pesa mas».

**Ten cuidado con:**

- Si vas a partir en entrenamiento y prueba, estandariza DESPUES de partir, o el conjunto de prueba se filtra en el de entrenamiento.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | datos | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `columnas` | `—` |
| `metodo` | `z` |
| `reemplazar` | `False` |

Si vienes de otro sistema — **Stata**: `egen z = std(x)` · **R**: `scale()`

### Recortar valores extremos

`transformar.winsorizar` · v1.0.0

**Qué hace.** Aplasta los valores mas altos y mas bajos hasta un percentil que tu elijas.

**Cuándo usarlo.** Cuando unos pocos valores extremos dominan la estimacion, sobre todo en datos de ingreso, riqueza o precios.

**Cómo se lee el resultado.** Compara el modelo con y sin recorte. Si los resultados cambian mucho, tu conclusion descansaba en un punado de observaciones.

**Ten cuidado con:**

- Recortar cambia los datos. Se reporta SIEMPRE en la nota metodologica, con el percentil usado.
- Un valor extremo puede ser un error de captura o el dato mas informativo de la muestra. Vale la pena mirarlo antes de aplastarlo.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | datos | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `columnas` | `—` |
| `percentil` | `1.0` |

Si vienes de otro sistema — **Stata**: `winsor2` · **R**: `DescTools::Winsorize()`

### Rezago o adelanto

`transformar.rezago` · v1.0.0

**Qué hace.** Crea una columna con el valor de periodos anteriores (rezago) o posteriores (adelanto).

**Cuándo usarlo.** Cuando el efecto tarda en aparecer: la tasa de hoy afecta la inversion del trimestre que entra, no la de hoy.

**Cómo se lee el resultado.** Un coeficiente sobre el rezago 1 dice cuanto responde la variable a lo que paso un periodo antes.

**Supuestos que impone:**

- Los datos deben estar ordenados por fecha. Si es panel, el rezago se calcula dentro de cada entidad.

**Ten cuidado con:**

- Cada rezago te cuesta observaciones al principio de la serie.
- Meter un adelanto como explicativa suele ser un error: estarias explicando el pasado con el futuro.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | datos | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `columnas` | `—` |
| `periodos` | `1` |
| `por_entidad` | `None` |

Si vienes de otro sistema — **Stata**: `L.y / F.y` · **R**: `dplyr::lag()` · **EViews**: `y(-1)`

### Tasa de crecimiento o diferencia

`transformar.crecimiento` · v1.0.0

**Qué hace.** Calcula el cambio de una variable entre periodos: en diferencia, en porcentaje o en log-diferencia.

**Cuándo usarlo.** Casi todas las series economicas en niveles tienen raiz unitaria. Diferenciarlas es el paso que las vuelve estacionarias y evita una regresion espuria.

**Cómo se lee el resultado.** La log-diferencia multiplicada por 100 es, para cambios chicos, casi igual al crecimiento porcentual, y tiene la ventaja de ser simetrica: subir 10% y bajar 10% se cancelan.

**Supuestos que impone:**

- Los periodos deben estar ordenados y completos.

**Ten cuidado con:**

- Diferenciar de mas convierte una serie estacionaria en ruido con autocorrelacion negativa.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | datos | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `columnas` | `—` |
| `tipo` | `porcentaje` |
| `periodos` | `1` |
| `por_entidad` | `None` |

Si vienes de otro sistema — **Stata**: `D.y` · **R**: `diff()` · **EViews**: `d(y) / dlog(y)`

<a id="explorar"></a>

## Explorar

Mirar los datos antes de modelarlos: descriptivos, correlaciones, tablas cruzadas, pruebas.

### Comparar grupos (t / ANOVA)

`explorar.comparar_grupos` · v1.0.0

**Qué hace.** Compara el promedio de una variable entre dos o mas grupos y dice si la diferencia se distingue del azar.

**Cuándo usarlo.** «¿Gana mas quien tiene credito?» «¿El precio por m² difiere entre regiones?»

**Cómo se lee el resultado.** El p-valor dice si la diferencia es distinguible del azar, NO si es importante. Con muestras grandes, diferencias irrelevantes salen significativas. Mira siempre el tamano de la diferencia en las unidades del problema.

**Supuestos que impone:**

- La prueba t supone varianzas parecidas; se usa la version de Welch, que no lo exige.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | Resultado | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `variable` | `—` |
| `grupo` | `—` |

Si vienes de otro sistema — **Stata**: `ttest y, by(g) / oneway` · **R**: `t.test()` · **SPSS**: `Comparar medias`

### Correlaciones

`explorar.correlacion` · v1.0.0

**Qué hace.** Mide que tan juntas se mueven cada par de variables, y si esa relacion se distingue del azar.

**Cuándo usarlo.** Antes de una regresion, para ver que variables se pisan entre si.

**Cómo se lee el resultado.** La correlacion va de -1 a 1. Cerca de cero no significa «sin relacion»: significa sin relacion LINEAL. Una U invertida perfecta da correlacion cero.

**Ten cuidado con:**

- Correlacion no es causalidad, y con muchas variables aparecen correlaciones altas por puro azar. Con 20 variables hay 190 pares: unos 10 saldran «significativos» al 5% sin que exista nada.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | Correlaciones | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `columnas` | `—` |
| `metodo` | `pearson` |

Si vienes de otro sistema — **Stata**: `pwcorr, sig` · **R**: `cor()` · **SPSS**: `Correlaciones bivariadas`

### Estadisticos descriptivos

`explorar.descriptivos` · v1.0.0

**Qué hace.** Resume cada variable: cuantos datos hay, promedio, dispersion, minimo, maximo y cuantos faltan.

**Cuándo usarlo.** Siempre, antes de modelar. La mitad de los problemas de un analisis se ven aqui.

**Cómo se lee el resultado.** Mira tres cosas: los faltantes (¿cuantas filas vas a perder?), el coeficiente de variacion (si pasa de 1, la variable es muy dispersa) y la asimetria (si pasa de 2, considera trabajar en logaritmos).

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | Descriptivos | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `columnas` | `—` |
| `por` | `None` |

Si vienes de otro sistema — **Stata**: `summarize, detail` · **R**: `summary()` · **SPSS**: `Descriptivos`

<a id="econometria"></a>

## Econometria

Regresiones y modelos de siempre: MCO, variables instrumentales, panel, eleccion discreta.

### Colinealidad (VIF)

`econometria.colinealidad` · v1.0.0

**Qué hace.** Mide cuanto se pisan entre si tus variables explicativas.

**Cuándo usarlo.** Cuando un coeficiente sale con el signo contrario al esperado, o cuando el modelo completo es significativo pero ninguna variable lo es por separado. Ese par de sintomas juntos es colinealidad casi siempre.

**Cómo se lee el resultado.** VIF por arriba de 10 es problema serio; entre 5 y 10 conviene mirarlo. La colinealidad no sesga los coeficientes: los vuelve imprecisos.

**Ten cuidado con:**

- Quitar variables por VIF alto puede introducir sesgo por variable omitida, que es peor. A veces la respuesta correcta es aceptar la imprecision y decirlo.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | Factor de inflacion de varianza | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `columnas` | `—` |

Si vienes de otro sistema — **Stata**: `estat vif` · **R**: `car::vif()`

### Diagnosticos del modelo

`econometria.diagnosticos` · v1.0.0

**Qué hace.** Corre las pruebas de siempre sobre los residuos: heterocedasticidad, autocorrelacion, normalidad y forma funcional.

**Cuándo usarlo.** Despues de estimar cualquier regresion. Es el paso que casi nadie hace y el que separa un resultado defendible de uno que se cae en la primera pregunta.

**Cómo se lee el resultado.** Cada fila trae su lectura en espanol. Un p-valor por debajo de 0.05 significa que se rechaza el supuesto de esa prueba.

**Ten cuidado con:**

- Estas pruebas dicen que supuesto falla, no que el modelo este mal. Con muestras grandes casi todo se rechaza; mira tambien el tamano del problema, no solo el p-valor.

| | Puerto | Tipo |
|---|---|---|
| entra | modelo | Un modelo ya estimado, con sus coeficientes y diagnósticos |
| sale | Pruebas de supuestos | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `rezagos_autocorrelacion` | `4` |

Si vienes de otro sistema — **Stata**: `estat hettest / estat vif` · **R**: `lmtest::bptest()`

Para leer más: Wooldridge, caps. 8 y 12

### Logit / Probit

`econometria.eleccion_discreta` · v1.0.0

**Qué hace.** Modela una variable que solo toma dos valores (si/no, 1/0): probabilidad de que ocurra.

**Cuándo usarlo.** ¿Que determina que un hogar tenga credito? ¿Que una empresa exporte? ¿Que alguien compre en vez de rentar?

**Cómo se lee el resultado.** Los coeficientes crudos NO son el efecto sobre la probabilidad; solo su signo y su significancia se leen directo. Para el tamano del efecto usa los efectos marginales promedio, que este nodo calcula aparte: ahi si, «una unidad mas de X sube la probabilidad en tantos puntos porcentuales».

**Supuestos que impone:**

- La variable dependiente debe ser 0/1
- Logit y probit dan casi siempre las mismas conclusiones; difieren en la cola

**Ten cuidado con:**

- Si una explicativa predice perfectamente el resultado, el modelo no converge. Eso es informacion, no una falla del software.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | modelo | Un modelo ya estimado, con sus coeficientes y diagnósticos |
| sale | Efectos marginales | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `y` | `—` |
| `x` | `—` |
| `familia` | `logit` |
| `constante` | `True` |
| `errores` | `HC1` |
| `cluster_por` | `None` |
| `rezagos_hac` | `4` |

Si vienes de otro sistema — **Stata**: `logit y x1 x2 / margins, dydx(*)` · **R**: `glm(family=binomial)`

Para leer más: Wooldridge, cap. 17

### Minimos cuadrados (MCO)

`econometria.mco` · v1.0.0

**Qué hace.** Ajusta una recta que minimiza la suma de los errores al cuadrado. Es el punto de partida de casi todo el analisis economico.

**Cuándo usarlo.** Cuando quieres explicar una variable numerica continua con otras variables.

**Cómo se lee el resultado.** Cada coeficiente dice cuanto cambia la variable dependiente si esa explicativa sube una unidad y las demas se quedan igual. Las estrellas marcan significancia: *** al 1%, ** al 5%, * al 10%. Que un coeficiente sea significativo no lo vuelve grande ni importante: mira tambien su tamano en las unidades del problema.

**Supuestos que impone:**

- El efecto es lineal en los parametros
- Las explicativas no estan correlacionadas con el error (si lo estan, MCO esta sesgado y necesitas variables instrumentales)
- Errores sin autocorrelacion (si no, usa errores HAC)
- Varianza constante (si no, usa errores robustos HC1 o HC3)

**Ten cuidado con:**

- Correlacion no es causalidad. MCO mide asociacion condicional; para hablar de efecto causal hace falta un argumento de identificacion, no un R² alto.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | modelo | Un modelo ya estimado, con sus coeficientes y diagnósticos |
| sale | Ajuste y residuos | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `y` | `—` |
| `x` | `—` |
| `constante` | `True` |
| `errores` | `HC1` |
| `cluster_por` | `None` |
| `rezagos_hac` | `4` |

Si vienes de otro sistema — **Stata**: `regress y x1 x2, robust` · **R**: `lm(y ~ x1 + x2)` · **EViews**: `Quick > Estimate Equation` · **SPSS**: `Analizar > Regresion > Lineales`

Para leer más: Wooldridge, «Introductory Econometrics», caps. 3-8

### Panel: efectos fijos o aleatorios

`econometria.panel` · v1.0.0

**Qué hace.** Estima con datos que siguen a las mismas entidades a lo largo del tiempo, controlando por lo que no cambia dentro de cada entidad.

**Cuándo usarlo.** Cuando tienes varias entidades observadas en varios periodos y te preocupa que algo que no mediste (cultura local, calidad institucional, geografia) este contaminando el resultado.

**Cómo se lee el resultado.** Con efectos fijos, el coeficiente se estima SOLO con la variacion dentro de cada entidad a lo largo del tiempo. Una variable que no cambia en el tiempo (la costa, el area) no se puede estimar con efectos fijos: desaparece en la transformacion. Eso no es un error, es la definicion del metodo.

**Supuestos que impone:**

- Efectos fijos: los efectos individuales pueden estar correlacionados con las explicativas
- Efectos aleatorios: se supone que NO lo estan. Es un supuesto fuerte, y la prueba de Hausman es la que lo pone a prueba.

**Ten cuidado con:**

- Agrupa los errores por entidad. Sin eso, los errores estandar salen demasiado chicos y todo parece significativo (Bertrand, Duflo y Mullainathan, 2004).

| | Puerto | Tipo |
|---|---|---|
| entra | Panel | Una tabla de panel: varias entidades observadas en varios periodos |
| sale | modelo | Un modelo ya estimado, con sus coeficientes y diagnósticos |
| sale | Prueba de Hausman | Un número o un texto suelto |

| Parámetro | Por omisión |
|---|---|
| `y` | `—` |
| `x` | `—` |
| `efectos` | `fijos` |
| `efectos_tiempo` | `False` |
| `errores` | `agrupados_por_entidad` |
| `prueba_hausman` | `True` |

Si vienes de otro sistema — **Stata**: `xtreg y x, fe cluster(id)` · **R**: `plm(model='within')`

Para leer más: Wooldridge, «Econometric Analysis of Cross Section and Panel Data», cap. 10

### Regresion por cuantiles

`econometria.cuantilica` · v1.0.0

**Qué hace.** Estima el efecto de las explicativas sobre un cuantil de la dependiente, no sobre su promedio.

**Cuándo usarlo.** Cuando sospechas que el efecto es distinto arriba y abajo de la distribucion: la escolaridad puede pesar mucho mas en los ingresos altos que en los bajos.

**Cómo se lee el resultado.** El coeficiente en el cuantil 0.9 dice como se mueve el percentil 90 de la dependiente. Compara varios cuantiles: si los coeficientes cambian mucho, el promedio estaba escondiendo la historia.

**Supuestos que impone:**

- No supone varianza constante ni normalidad: es mas robusto que MCO ante valores extremos.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | modelo | Un modelo ya estimado, con sus coeficientes y diagnósticos |
| sale | Ajuste y residuos | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `y` | `—` |
| `x` | `—` |
| `cuantil` | `0.5` |
| `constante` | `True` |

Si vienes de otro sistema — **Stata**: `qreg y x, quantile(.9)` · **R**: `quantreg::rq()`

Para leer más: Koenker y Bassett (1978)

### Variables instrumentales (MC2E)

`econometria.iv` · v1.0.0

**Qué hace.** Estima por minimos cuadrados en dos etapas cuando una explicativa esta correlacionada con el error (endogeneidad).

**Cuándo usarlo.** Cuando la causalidad va en las dos direcciones, hay una variable omitida importante, o la explicativa se mide con error. El caso clasico: precio y cantidad se determinan juntos.

**Cómo se lee el resultado.** El coeficiente de la variable instrumentada es el efecto causal, SI los instrumentos son validos. Revisa el estadistico F de la primera etapa: por debajo de 10, los instrumentos son debiles y el remedio es peor que la enfermedad.

**Supuestos que impone:**

- Relevancia: los instrumentos explican a la variable endogena (F de primera etapa > 10)
- Exclusion: los instrumentos afectan a la dependiente SOLO a traves de la endogena. Esto no se puede probar con datos: se defiende con un argumento.

**Ten cuidado con:**

- Instrumentos debiles sesgan MC2E hacia MCO y ademas rompen la inferencia.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | modelo | Un modelo ya estimado, con sus coeficientes y diagnósticos |
| sale | Ajuste y residuos | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `y` | `—` |
| `endogenas` | `—` |
| `instrumentos` | `—` |
| `exogenas` | `—` |
| `constante` | `True` |

Si vienes de otro sistema — **Stata**: `ivregress 2sls y x (endog = instr)` · **R**: `AER::ivreg()`

Para leer más: Angrist y Pischke, «Mostly Harmless Econometrics», cap. 4

<a id="causal"></a>

## Inferencia causal

Dibuja que causa que y deja que el criterio de puerta trasera decida los controles.

### Efecto causal (puerta trasera)

`causal.efecto` · v1.0.0

**Qué hace.** Dibujas que causa que, y Abak decide que variables hay que controlar para medir el efecto de una sobre otra. Despues estima la regresion con exactamente esos controles, ni uno mas ni uno menos.

**Cuándo usarlo.** Cuando la pregunta es CAUSAL y no descriptiva: «¿el metro subio los precios?», «¿la remodelacion aumento la renta?». Si solo quieres describir o predecir, usa MCO o XGBoost.

**Cómo se lee el resultado.** El coeficiente del tratamiento es el efecto causal SI el grafo que dibujaste es correcto. La tabla de controles dice que entro, que se quedo fuera y por que; leerla es la mitad del valor de esta herramienta.

**Supuestos que impone:**

- El grafo lo pones tu y no se puede verificar con los datos: es un argumento, no un resultado
- No hay confusion por variables que no dibujaste u observaste
- El efecto es lineal en los parametros (lo estima MCO)

**Ten cuidado con:**

- Meter todas las variables «por si acaso» es un error, no una precaucion: un mediador borra el efecto y un colisionador lo inventa. Esta herramienta existe justo para no hacer eso.
- Si dice que el efecto NO se puede identificar, ninguna regresion lo arregla. Hace falta otro dato o otro diseno.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | Efecto estimado | Un modelo ya estimado, con sus coeficientes y diagnósticos |
| sale | Que se controlo y por que | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `arcos` | `—` |
| `tratamiento` | `—` |
| `resultado` | `—` |
| `errores` | `HC1` |

Si vienes de otro sistema — **R**: `dagitty::adjustmentSets() + lm()` · **Stata**: `dagitty (fuera de Stata)` · **EViews**: `—` · **SPSS**: `—`

Para leer más: Pearl, «Causality» (2009), cap. 3. Version corta: Cunningham, «The Mixtape», cap. 3

<a id="series"></a>

## Series de tiempo

Todo lo que tiene fecha: raiz unitaria, ARIMA, VAR, impulso-respuesta, cointegracion, ciclos.

### ARIMA / SARIMAX

`series.arima` · v1.0.0

**Qué hace.** Modela una serie con su propio pasado (AR), con los errores pasados (MA) y con diferencias (I), y produce un pronostico con su intervalo.

**Cuándo usarlo.** Cuando quieres pronosticar una serie y no tienes (o no quieres usar) otras variables.

**Cómo se lee el resultado.** El pronostico viene con banda de confianza. Esa banda es lo importante: un pronostico puntual sin banda es una opinion disfrazada de numero. Todo lo pronosticado sale marcado en ambar, porque es estimacion y no dato.

**Supuestos que impone:**

- La serie debe ser estacionaria despues de aplicar d diferencias
- Los residuos deben quedar sin autocorrelacion: revisalos

**Ten cuidado con:**

- Un AIC mas bajo no garantiza mejor pronostico fuera de muestra. La unica prueba honesta es guardar los ultimos periodos y ver que tan lejos cae.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla con fecha: cada fila es un periodo en orden |
| sale | modelo | Un modelo ya estimado, con sus coeficientes y diagnósticos |
| sale | Pronostico | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `variable` | `—` |
| `p` | `1` |
| `d` | `1` |
| `q` | `1` |
| `estacional` | `False` |
| `P` | `0` |
| `D` | `0` |
| `Q` | `0` |
| `periodo_estacional` | `4` |
| `horizonte` | `8` |

Si vienes de otro sistema — **Stata**: `arima y, arima(1,1,1)` · **R**: `forecast::Arima()` · **EViews**: `ARMA`

Para leer más: Box y Jenkins; Hyndman y Athanasopoulos, «Forecasting: Principles and Practice»

### Cointegracion (Johansen)

`series.cointegracion` · v1.0.0

**Qué hace.** Busca si varias series que individualmente tienen raiz unitaria se mueven juntas en el largo plazo.

**Cuándo usarlo.** Cuando teoricamente esperas una relacion de equilibrio: consumo e ingreso, precios y salarios, tipo de cambio y diferencial de precios.

**Cómo se lee el resultado.** La tabla recorre r = 0, 1, 2... El primer renglon que NO se rechaza dice cuantas relaciones de largo plazo hay. Si hay cointegracion, la regresion en niveles NO es espuria, y el modelo correcto es un VECM, no un VAR en diferencias.

**Supuestos que impone:**

- Todas las series deben ser integradas del mismo orden, normalmente I(1). Compruebalo antes con la prueba de raiz unitaria.

**Ten cuidado con:**

- La prueba es sensible al numero de rezagos y al termino deterministico. Reporta que elegiste, o el resultado no es reproducible.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla con fecha: cada fila es un periodo en orden |
| sale | Prueba de la traza | Una tabla de datos (filas y columnas) |
| sale | VECM | Un modelo ya estimado, con sus coeficientes y diagnósticos |

| Parámetro | Por omisión |
|---|---|
| `variables` | `—` |
| `rezagos` | `1` |
| `termino_deterministico` | `constante` |
| `estimar_vecm` | `True` |
| `relaciones` | `1` |

Si vienes de otro sistema — **Stata**: `vecrank` · **R**: `urca::ca.jo()` · **EViews**: `Johansen Cointegration Test`

Para leer más: Johansen (1991); Enders, cap. 6

### Prueba de raiz unitaria (ADF y KPSS)

`series.estacionariedad` · v1.0.0

**Qué hace.** Revisa si una serie es estacionaria, es decir, si su media y su varianza se quedan quietas a lo largo del tiempo.

**Cuándo usarlo.** ANTES de cualquier modelo de series de tiempo. Es el primer paso, siempre.

**Cómo se lee el resultado.** ADF: p < 0.05 significa estacionaria. KPSS: p > 0.05 significa estacionaria. Ojo, las hipotesis nulas estan al reves entre las dos pruebas, y por eso se corren juntas. La columna «conclusion» ya resuelve la combinacion.

**Supuestos que impone:**

- Las dos pruebas tienen poca potencia con series cortas: por debajo de 50 observaciones, tomalas como indicio, no como veredicto.

**Ten cuidado con:**

- Regresionar dos series con raiz unitaria produce una regresion espuria: R² altisimo, t enormes y ninguna relacion real. Es el error mas caro de la econometria aplicada.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | Resultado de las pruebas | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `columnas` | `—` |
| `regresion` | `c` |

Si vienes de otro sistema — **Stata**: `dfuller y / kpss y` · **R**: `tseries::adf.test()` · **EViews**: `Unit Root Test`

Para leer más: Granger y Newbold (1974); Enders, «Applied Econometric Time Series», cap. 4

### Separar tendencia y ciclo

`series.ciclo` · v1.0.0

**Qué hace.** Parte una serie en su tendencia de largo plazo y su ciclo alrededor de ella.

**Cuándo usarlo.** Para medir la brecha del producto, el componente ciclico del empleo o del credito.

**Cómo se lee el resultado.** El ciclo es la desviacion respecto a la tendencia. Positivo significa por encima de su nivel de largo plazo. Es una construccion, no un dato observado, y por eso sale marcado en ambar.

**Supuestos que impone:**

- Lambda del filtro HP por convencion: 1600 trimestral, 129600 mensual, 6.25 anual.

**Ten cuidado con:**

- Hamilton (2018) mostro que el filtro HP inventa dinamicas que no estan en los datos, sobre todo al final de la muestra, que es justo donde se toman las decisiones. Por eso este nodo ofrece tambien su alternativa, y por eso conviene comparar las dos.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla con fecha: cada fila es un periodo en orden |
| sale | Tendencia y ciclo | Una tabla con fecha: cada fila es un periodo en orden |

| Parámetro | Por omisión |
|---|---|
| `variable` | `—` |
| `metodo` | `hp` |
| `lamb` | `1600.0` |
| `periodo_estacional` | `4` |

Si vienes de otro sistema — **Stata**: `tsfilter hp` · **R**: `mFilter::hpfilter()` · **EViews**: `Hodrick-Prescott Filter`

Para leer más: Hodrick y Prescott (1997); Hamilton, «Why You Should Never Use the HP Filter» (2018)

### VAR: vectores autorregresivos

`series.var` · v1.0.0

**Qué hace.** Modela varias series a la vez, donde cada una se explica con el pasado de todas, y calcula como responde el sistema a un choque en cualquiera de ellas.

**Cuándo usarlo.** Cuando las variables se determinan entre si y no quieres imponer quien causa a quien: tasa, inflacion y tipo de cambio, por ejemplo.

**Cómo se lee el resultado.** Lo que se lee no son los coeficientes (son demasiados y no significan nada por separado), sino las funciones de impulso-respuesta: «si la tasa sube un punto, ¿que le pasa a la inflacion en los siguientes 12 trimestres?». Si la banda cruza el cero, el efecto no es distinguible de cero.

**Supuestos que impone:**

- Todas las series deben ser estacionarias. Si no lo son y estan cointegradas, el modelo correcto es un VECM, no un VAR en diferencias.
- La descomposicion ortogonal (Cholesky) impone un orden causal contemporaneo: la primera variable afecta a todas en el mismo periodo y no recibe nada. El orden importa y hay que justificarlo.

**Ten cuidado con:**

- Cada rezago cuesta k² parametros. Con 4 variables y 8 rezagos son 128 coeficientes: no hay serie trimestral en Mexico que aguante eso.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla con fecha: cada fila es un periodo en orden |
| sale | modelo | Un modelo ya estimado, con sus coeficientes y diagnósticos |
| sale | Impulso-respuesta | Una tabla de datos (filas y columnas) |
| sale | Causalidad de Granger | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `variables` | `—` |
| `rezagos` | `2` |
| `elegir_rezagos` | `True` |
| `periodos_irf` | `12` |
| `ortogonal` | `True` |

Si vienes de otro sistema — **Stata**: `var y1 y2, lags(1/4) / irf create` · **R**: `vars::VAR()` · **EViews**: `VAR`

Para leer más: Sims (1980); Enders, cap. 5

<a id="espacial"></a>

## Econometria espacial

Cuando la ubicacion importa: matrices de vecindad, Moran, LISA, SAR y SEM.

### Autocorrelacion espacial (I de Moran)

`espacial.moran` · v1.0.0

**Qué hace.** Mide si los valores parecidos tienden a estar cerca unos de otros.

**Cuándo usarlo.** Es la primera pregunta del analisis espacial: ¿la ubicacion importa, si o no? Tambien sobre los residuos de un MCO, para ver si te quedo estructura espacial sin modelar.

**Cómo se lee el resultado.** I cerca de +1: los valores altos se agrupan con altos y los bajos con bajos. Cerca de 0: distribucion sin patron. Negativo: tablero de ajedrez, cada valor rodeado de sus opuestos. El p-valor por permutacion dice si el patron se distingue del azar.

**Supuestos que impone:**

- Depende por completo de la matriz W que elegiste.

**Ten cuidado con:**

- Moran significativo en los residuos de un MCO significa que el modelo esta mal especificado: los errores estandar estan mal y hay que pasar a un modelo espacial.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| entra | pesos | Una matriz de pesos espaciales (quién es vecino de quién) |
| sale | I de Moran | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `columnas` | `—` |
| `permutaciones` | `999` |

Si vienes de otro sistema — **Stata**: `moran` · **R**: `spdep::moran.test()`

Para leer más: Moran (1950); Anselin (1995)

### Conglomerados locales (LISA)

`espacial.lisa` · v1.0.0

**Qué hace.** Dice, punto por punto, si forma parte de un conglomerado de valores altos, de uno de valores bajos, o si es una anomalia rodeada de lo contrario.

**Cuándo usarlo.** Cuando Moran global dice que hay patron y ahora quieres saber DONDE esta.

**Cómo se lee el resultado.** Alto-Alto = nucleo caliente. Bajo-Bajo = nucleo frio. Alto-Bajo y Bajo-Alto son atipicos: una zona cara rodeada de baratas, o al reves. En mercados inmobiliarios los Bajo-Alto suelen ser justo las oportunidades.

**Ten cuidado con:**

- Los p-valores no estan corregidos por comparaciones multiples: con 2,400 puntos, unos 120 saldran «significativos» por azar al 5%. Para decisiones serias, baja alpha.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| entra | pesos | Una matriz de pesos espaciales (quién es vecino de quién) |
| sale | Tabla con la clasificacion | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `columna` | `—` |
| `permutaciones` | `999` |
| `alpha` | `0.05` |

Si vienes de otro sistema — **R**: `spdep::localmoran()` · **Stata**: `lisa`

Para leer más: Anselin, «Local Indicators of Spatial Association» (1995)

### Matriz de vecindad (W)

`espacial.pesos` · v1.0.0

**Qué hace.** Define quien es vecino de quien y con cuanto peso. Es el punto de partida de todo el analisis espacial.

**Cuándo usarlo.** Antes de Moran, LISA o cualquier modelo SAR/SEM.

**Cómo se lee el resultado.** Con pesos estandarizados por fila, el «rezago espacial» de una variable es el promedio de esa variable entre los vecinos de cada punto. Ese promedio es la variable que entra en los modelos espaciales.

**Supuestos que impone:**

- Vecinos mas cercanos (KNN) nunca deja puntos aislados, que es lo que suele romper una estimacion espacial.
- Por distancia es mas facil de justificar teoricamente, pero puede dejar islas.

**Ten cuidado con:**

- W es la decision mas importante y la menos justificada del analisis espacial publicado. Los resultados dependen de ella: prueba al menos dos y reporta si la conclusion aguanta el cambio.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla con ubicación: cada fila tiene coordenadas o geometría |
| sale | Matriz W | Una matriz de pesos espaciales (quién es vecino de quién) |
| sale | Ficha de la matriz | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `latitud` | `lat` |
| `longitud` | `lng` |
| `metodo` | `knn` |
| `k` | `5` |
| `umbral_km` | `None` |
| `estandarizar_filas` | `True` |

Si vienes de otro sistema — **Stata**: `spmatrix create knn` · **R**: `spdep::knearneigh()`

Para leer más: Anselin, «Spatial Econometrics: Methods and Models» (1988), cap. 3

### Modelo de error espacial (SEM)

`espacial.sem` · v1.0.0

**Qué hace.** Estima un modelo donde lo que se contagia entre vecinos no es la variable, sino lo que el modelo no logro explicar: y = Xβ + u, con u = λWu + ε.

**Cuándo usarlo.** Cuando la dependencia espacial viene de algo que no mediste y que esta repartido en el territorio: calidad del barrio, acceso a servicios, percepcion de seguridad.

**Cómo se lee el resultado.** λ (lambda) mide cuanto se parecen los errores de puntos vecinos. A diferencia de SAR, aqui los coeficientes β SI se leen como en MCO: son el efecto directo. Lo que cambia es que los errores estandar quedan bien.

**Supuestos que impone:**

- La dependencia esta en el error, no en la variable. Cual de los dos es el caso lo decide la prueba de multiplicadores de Lagrange, no la intuicion.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| entra | pesos | Una matriz de pesos espaciales (quién es vecino de quién) |
| sale | modelo | Un modelo ya estimado, con sus coeficientes y diagnósticos |
| sale | Coeficientes | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `y` | `—` |
| `x` | `—` |

Si vienes de otro sistema — **Stata**: `spregress y x, ml errorlag(W)` · **R**: `spatialreg::errorsarlm()`

Para leer más: Anselin (1988), cap. 6

### Modelo espacial autorregresivo (SAR)

`espacial.sar` · v1.0.0

**Qué hace.** Estima un modelo donde el valor de cada punto depende del promedio de sus vecinos: y = ρWy + Xβ + ε.

**Cuándo usarlo.** Cuando hay desbordamiento real entre ubicaciones. En vivienda es el caso normal: el precio de una casa depende de lo que se pago por las de al lado, porque asi valuan los avaluos y asi negocian los compradores.

**Cómo se lee el resultado.** ρ (rho) mide la fuerza del contagio espacial. Con ρ positivo y significativo, un cambio en un punto se propaga a sus vecinos, y de ahi a los vecinos de sus vecinos. Por eso el coeficiente β NO es el efecto total: el efecto total incluye el efecto indirecto que regresa por la red.

**Supuestos que impone:**

- El resultado depende de la matriz W. Cambiar de W puede cambiar ρ de forma importante.
- ρ debe quedar entre -1 y 1 para que el sistema sea estable.

**Ten cuidado con:**

- No leas β como en MCO. Para el efecto total hacen falta los impactos directo e indirecto, que se calculan a partir de la inversa (I - ρW)⁻¹.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| entra | pesos | Una matriz de pesos espaciales (quién es vecino de quién) |
| sale | modelo | Un modelo ya estimado, con sus coeficientes y diagnósticos |
| sale | Coeficientes | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `y` | `—` |
| `x` | `—` |

Si vienes de otro sistema — **Stata**: `spregress y x, ml dvarlag(W)` · **R**: `spatialreg::lagsarlm()`

Para leer más: Anselin (1988); LeSage y Pace, «Introduction to Spatial Econometrics» (2009)

### ¿SAR o SEM? (pruebas LM)

`espacial.diagnostico` · v1.0.0

**Qué hace.** Corre un MCO con diagnostico espacial y te dice cual modelo espacial corresponde.

**Cuándo usarlo.** ANTES de elegir entre SAR y SEM. Elegir por intuicion es como se llega a un modelo que no se puede defender.

**Cómo se lee el resultado.** Receta de Anselin y Florax: si solo una de las LM simples rechaza, ese es tu modelo. Si las dos rechazan, mira las robustas y quedate con la que rechace con mas fuerza. Si ninguna rechaza, MCO alcanza y no necesitas un modelo espacial.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| entra | pesos | Una matriz de pesos espaciales (quién es vecino de quién) |
| sale | Multiplicadores de Lagrange | Una tabla de datos (filas y columnas) |
| sale | MCO de referencia | Un modelo ya estimado, con sus coeficientes y diagnósticos |

| Parámetro | Por omisión |
|---|---|
| `y` | `—` |
| `x` | `—` |

Si vienes de otro sistema — **Stata**: `estat moran` · **R**: `spdep::lm.LMtests()`

Para leer más: Anselin, Bera, Florax y Yoon (1996)

<a id="macro"></a>

## Macro e insumo-producto

Estructura productiva: Leontief, multiplicadores, encadenamientos, impacto sectorial, keynesiano.

### Encadenamientos (Rasmussen)

`macro.encadenamientos` · v1.0.0

**Qué hace.** Ordena los sectores segun cuanto jalan al resto de la economia y cuanto son jalados por ella.

**Cuándo usarlo.** Para identificar sectores clave: los que si crecen, arrastran; y que ademas son insumo de muchos otros.

**Cómo se lee el resultado.** Los indices estan normalizados al promedio de la economia: por arriba de 1 significa mas encadenado que el sector promedio. Un sector con los dos indices arriba de 1 es «clave», y es donde la politica industrial rinde mas.

**Ten cuidado con:**

- Un encadenamiento alto concentrado en un solo proveedor es mas fragil que el mismo encadenamiento repartido. Por eso se reporta tambien la dispersion.

| | Puerto | Tipo |
|---|---|---|
| entra | sistema | Un sistema insumo-producto resuelto |
| sale | encadenamientos | Una tabla de datos (filas y columnas) |

Para leer más: Rasmussen (1956); Hirschman (1958)

### Impacto de un choque de demanda

`macro.impacto` · v1.0.0

**Qué hace.** Simula que le pasa a toda la economia si sube la demanda final de uno o varios sectores.

**Cuándo usarlo.** «Si se invierten 5,000 millones en construccion, ¿cuanta produccion, empleo e ingreso se generan, y en que sectores?»

**Cómo se lee el resultado.** El efecto directo es lo que produce de mas el sector que recibe el choque. El indirecto es lo que producen de mas sus proveedores, y los proveedores de estos, hasta que la cadena se agota.

**Ten cuidado con:**

- Esto es una COTA SUPERIOR. Supone capacidad ociosa, precios fijos y que la receta productiva no cambia. En una economia cerca de su capacidad, el efecto real es menor y parte se va a precios o a importaciones.
- El resultado esta en las mismas unidades que la matriz. Si la matriz esta en miles de pesos, el choque tambien.

| | Puerto | Tipo |
|---|---|---|
| entra | sistema | Un sistema insumo-producto resuelto |
| sale | impacto | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `choques` | `—` |

Para leer más: Miller y Blair, cap. 6

### Multiplicador keynesiano del gasto

`macro.multiplicador_keynesiano` · v1.0.0

**Qué hace.** Calcula cuanto producto genera cada peso de gasto adicional, descontando lo que se filtra en ahorro, impuestos e importaciones.

**Cuándo usarlo.** Para dimensionar el efecto de un programa de gasto o de inversion publica.

**Cómo se lee el resultado.** Un multiplicador de 1.6 significa que 100 pesos de gasto generan 160 de producto. Cuanto mas abierta la economia y mas alta la carga fiscal, mas chico el multiplicador.

**Supuestos que impone:**

- Economia con capacidad ociosa: si esta en pleno empleo, el efecto se va a precios.
- Sin respuesta de la politica monetaria: si el banco central sube la tasa para compensar, el multiplicador real es menor.
- Propensiones constantes en el rango del choque.

**Ten cuidado con:**

- La evidencia empirica pone el multiplicador del gasto entre 0.5 y 2.5 segun el pais y el momento del ciclo. Este calculo es el de libro de texto: sirve para ordenar magnitudes, no para prometer resultados.
- En recesion los multiplicadores son mas altos que en expansion (Auerbach y Gorodnichenko, 2012).

| | Puerto | Tipo |
|---|---|---|
| sale | Multiplicador | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `propension_consumo` | `0.65` |
| `tasa_impuestos` | `0.16` |
| `propension_importar` | `0.3` |
| `gasto_adicional` | `0.0` |

Para leer más: Keynes (1936); Blanchard, «Macroeconomics», cap. 3

### Resolver matriz insumo-producto

`macro.insumo_producto` · v1.0.0

**Qué hace.** Calcula los coeficientes tecnicos y la inversa de Leontief, y de ahi los multiplicadores de produccion, empleo e ingreso de cada sector.

**Cuándo usarlo.** Cuando quieras saber que arrastra un sector al resto de la economia: cuanto produccion, empleo e ingreso se generan por cada peso de demanda final.

**Cómo se lee el resultado.** Un multiplicador de produccion de 1.8 significa que por cada peso de demanda final a ese sector, la economia produce 1.80 pesos en total: uno directo y 80 centavos repartidos entre sus proveedores.

**Supuestos que impone:**

- Coeficientes tecnicos fijos: la receta productiva no cambia con la escala ni con los precios.
- Sin restricciones de capacidad: se supone que la oferta responde a cualquier demanda.
- Rendimientos constantes a escala.

**Ten cuidado con:**

- Estos supuestos hacen que los multiplicadores sean una COTA SUPERIOR del efecto real. Sirven para ordenar sectores entre si, no para prometer empleos.
- Una matriz insumo-producto vieja describe una estructura productiva que ya cambio.

| | Puerto | Tipo |
|---|---|---|
| entra | Matriz de transacciones | Una tabla de datos (filas y columnas) |
| sale | Sistema resuelto | Un sistema insumo-producto resuelto |
| sale | Multiplicadores | Una tabla de datos (filas y columnas) |
| sale | Inversa de Leontief | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `columna_sectores` | `sector` |
| `columnas_matriz` | `—` |
| `produccion_total` | `produccion_total` |
| `demanda_final` | `demanda_final` |
| `empleo` | `None` |
| `remuneraciones` | `None` |

Si vienes de otro sistema — **R**: `ioanalysis` · **EViews**: `—`

Para leer más: Leontief (1936); Miller y Blair, «Input-Output Analysis», 2a ed.

<a id="inmobiliario"></a>

## Inmobiliario

Indices de precios de calidad constante y herramientas de mercado inmobiliario.

### Indice de precios de calidad constante

`inmobiliario.indice_hedonico` · v1.0.0

**Qué hace.** Construye un indice de precios que separa el movimiento del MERCADO del cambio en la mezcla de lo que se vendio. Es lo que hace el Case-Shiller y el indice de la SHF.

**Cuándo usarlo.** Cuando tienes ventas u ofertas con fecha, precio y caracteristicas, y quieres saber si los precios subieron de verdad. La mediana de lo vendido NO contesta eso.

**Cómo se lee el resultado.** El indice arranca en 100 en el primer periodo. Si llega a 118, los precios a calidad constante subieron 18% desde entonces. La columna cambio_pct es el movimiento de cada periodo, ya limpio de composicion.

**Supuestos que impone:**

- Las caracteristicas que incluyes explican buena parte del precio: lo que dejes fuera y cambie con el tiempo se cuela en el indice
- Dentro de cada par de periodos, el valor de cada caracteristica es estable
- Las observaciones de cada periodo son comparables entre si

**Ten cuidado con:**

- Con pocas ventas por periodo el indice brinca por ruido, no por mercado. La tabla marca los periodos flacos: hazles caso o agrega a trimestres.
- Si tus datos son ASKING PRICE y no precio de cierre, esto mide lo que se pide, no lo que se paga. No son lo mismo y la diferencia se abre en las bajadas.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | Indice encadenado | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `periodo` | `—` |
| `precio` | `—` |
| `caracteristicas` | `—` |
| `base` | `100.0` |
| `minimo_por_periodo` | `30` |

Si vienes de otro sistema — **R**: `hedonicIndex / IndexNumR` · **Stata**: `—` · **EViews**: `—`

Para leer más: Eurostat/OCDE, «Handbook on Residential Property Price Indices» (2013), cap. 5

<a id="ml"></a>

## Machine learning

Prediccion con XGBoost y validacion honesta para series y panel.

### Partir en entrenamiento y prueba

`ml.particion` · v1.0.0

**Qué hace.** Separa los datos en una parte para entrenar el modelo y otra, que el modelo nunca ve, para medir que tan bien predice.

**Cuándo usarlo.** Siempre, antes de entrenar cualquier modelo predictivo.

**Cómo se lee el resultado.** El error en el conjunto de prueba es el unico que se parece al error que vas a tener con datos nuevos. El error de entrenamiento siempre es optimista.

**Ten cuidado con:**

- En datos con fecha, la particion ALEATORIA miente: entrena con el futuro y evalua con el pasado. Por eso el valor por omision es cortar por tiempo.
- Estandariza o imputa DESPUES de partir, o el conjunto de prueba se filtra en el de entrenamiento.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | entrenamiento | Una tabla de datos (filas y columnas) |
| sale | prueba | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `proporcion_prueba` | `0.2` |
| `aleatoria` | `False` |
| `columna_orden` | `None` |

Si vienes de otro sistema — **R**: `rsample::initial_time_split()` · **Python**: `TimeSeriesSplit`

### Validacion de origen movil

`ml.validacion_temporal` · v1.0.0

**Qué hace.** Evalua el modelo como se usaria de verdad: entrena con el pasado, predice el futuro inmediato, avanza y repite.

**Cuándo usarlo.** Siempre que vayas a pronosticar. Es la unica validacion honesta con datos que tienen fecha.

**Cómo se lee el resultado.** Mira la fila PROMEDIO y, sobre todo, la variacion entre cortes. Un modelo que predice muy bien en tres cortes y muy mal en dos no es un buen modelo: es un modelo inestable, y el promedio lo esconde.

**Ten cuidado con:**

- La validacion cruzada aleatoria (k-fold) sobre series de tiempo da metricas optimistas que no se repiten en produccion. No la uses.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | Error por corte | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `y` | `—` |
| `x` | `—` |
| `n_cortes` | `5` |
| `horizonte` | `4` |
| `profundidad` | `4` |
| `n_arboles` | `300` |

Si vienes de otro sistema — **Python**: `sklearn.model_selection.TimeSeriesSplit`

Para leer más: Hyndman y Athanasopoulos, «Forecasting», sec. 5.10

### XGBoost (arboles con refuerzo)

`ml.xgboost` · v1.0.0

**Qué hace.** Entrena un ensamble de arboles de decision donde cada arbol corrige los errores del anterior. Suele ser lo mejor que hay para datos tabulares.

**Cuándo usarlo.** Cuando tu objetivo es predecir bien y las relaciones no son lineales ni aditivas. Para valuar inmuebles, estimar demanda o clasificar riesgo, gana casi siempre.

**Cómo se lee el resultado.** Compara el error de entrenamiento contra el de prueba. Si el de entrenamiento es mucho mejor, el modelo se memorizo los datos y no va a generalizar: baja la profundidad o sube la regularizacion.

**Supuestos que impone:**

- No supone linealidad ni normalidad, y no le molestan las escalas distintas.
- Necesita bastantes observaciones: con menos de unos cientos, MCO suele ganarle.

**Ten cuidado con:**

- XGBoost predice, no explica. Sus «importancias» dicen que variable usa el modelo, no que variable CAUSA el resultado. Para efectos causales, sigue haciendo falta econometria.
- No extrapola: fuera del rango de sus datos de entrenamiento devuelve el valor del borde. Con series con tendencia hay que modelar las diferencias, no los niveles.

| | Puerto | Tipo |
|---|---|---|
| entra | entrenamiento | Una tabla de datos (filas y columnas) |
| entra | prueba *(opcional)* | Una tabla de datos (filas y columnas) |
| sale | modelo | Un modelo ya estimado, con sus coeficientes y diagnósticos |
| sale | Que tan bien predice | Una tabla de datos (filas y columnas) |
| sale | Importancia de variables | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `y` | `—` |
| `x` | `—` |
| `objetivo` | `regresion` |
| `n_arboles` | `300` |
| `profundidad` | `4` |
| `tasa_aprendizaje` | `0.05` |
| `submuestra` | `0.8` |
| `regularizacion_l2` | `1.0` |

Si vienes de otro sistema — **R**: `xgboost::xgb.train()` · **Stata**: `—`

Para leer más: Chen y Guestrin (2016)

<a id="graficos"></a>

## Graficos

Gramatica por capas: un lienzo y encima puntos, lineas, bandas, tendencias y facetas.

### + Banda de confianza

`graficos.banda` · v1.0.0

**Qué hace.** Sombrea el area entre un limite inferior y uno superior.

**Cuándo usarlo.** Para intervalos de confianza y de pronostico. Un pronostico sin banda es una opinion disfrazada de numero.

**Cómo se lee el resultado.** Mientras mas ancha la banda, menos sabes. Si la banda de dos series se traslapa, no puedes afirmar que una sea distinta de la otra.

| | Puerto | Tipo |
|---|---|---|
| entra | Grafico | Una capa de gráfico, para apilar sobre un lienzo |
| sale | Grafico | Una capa de gráfico, para apilar sobre un lienzo |

| Parámetro | Por omisión |
|---|---|
| `limite_bajo` | `—` |
| `limite_alto` | `—` |
| `opacidad` | `0.2` |
| `etiqueta` | `Intervalo de confianza` |

Si vienes de otro sistema — **R**: `+ geom_ribbon()`

### + Barras

`graficos.barras` · v1.0.0

**Qué hace.** Dibuja una barra por categoria.

**Cuándo usarlo.** Para comparar magnitudes entre categorias: produccion por sector, precio por entidad.

**Cómo se lee el resultado.** Ordena las barras por su valor, no alfabeticamente: el orden es informacion.

**Ten cuidado con:**

- El eje de las barras SIEMPRE empieza en cero. Truncarlo exagera diferencias chicas y es la forma mas comun de mentir con una grafica.

| | Puerto | Tipo |
|---|---|---|
| entra | Grafico | Una capa de gráfico, para apilar sobre un lienzo |
| sale | Grafico | Una capa de gráfico, para apilar sobre un lienzo |

| Parámetro | Por omisión |
|---|---|
| `opacidad` | `0.9` |

Si vienes de otro sistema — **R**: `+ geom_col()`

### + Escala de un eje

`graficos.escala` · v1.0.0

**Qué hace.** Cambia como se dibuja un eje: escala logaritmica, limites, formato de los numeros.

**Cuándo usarlo.** La escala logaritmica es util cuando los valores abarcan varios ordenes de magnitud, o cuando lo que importa son los cambios porcentuales.

**Cómo se lee el resultado.** En escala logaritmica, la misma distancia vertical significa el mismo cambio porcentual, no el mismo cambio absoluto. Hay que decirlo en el pie del grafico.

**Ten cuidado con:**

- Poner limites al eje puede exagerar o esconder diferencias. Si los cambias, dilo.

| | Puerto | Tipo |
|---|---|---|
| entra | Grafico | Una capa de gráfico, para apilar sobre un lienzo |
| sale | Grafico | Una capa de gráfico, para apilar sobre un lienzo |

| Parámetro | Por omisión |
|---|---|
| `eje` | `y` |
| `tipo` | `lineal` |
| `minimo` | `None` |
| `maximo` | `None` |
| `formato` | `None` |

Si vienes de otro sistema — **R**: `+ scale_y_log10()`

### + Facetas (un panel por categoria)

`graficos.facetas` · v1.0.0

**Qué hace.** Parte el grafico en varios paneles chicos, uno por categoria.

**Cuándo usarlo.** Cuando tienes mas de cinco o seis series y el grafico se vuelve un plato de espagueti. Casi siempre es mejor que meter mas colores.

**Cómo se lee el resultado.** Con el eje vertical compartido las magnitudes se comparan entre paneles; sin compartirlo se ve mejor la forma de cada uno, pero ya no se comparan niveles.

| | Puerto | Tipo |
|---|---|---|
| entra | Grafico | Una capa de gráfico, para apilar sobre un lienzo |
| sale | Grafico | Una capa de gráfico, para apilar sobre un lienzo |

| Parámetro | Por omisión |
|---|---|
| `por` | `—` |
| `columnas` | `3` |
| `compartir_eje_y` | `True` |

Si vienes de otro sistema — **R**: `+ facet_wrap(~ grupo)`

### + Linea

`graficos.linea` · v1.0.0

**Qué hace.** Une los puntos consecutivos con una linea continua, una serie por color.

**Cuándo usarlo.** Para series de tiempo. La linea insinua continuidad entre observaciones, asi que solo tiene sentido cuando el eje horizontal es un orden real (tiempo, rangos).

**Cómo se lee el resultado.** Fijate en el nivel y en la pendiente. Un salto de nivel suele ser un cambio metodologico de la fuente, no un fenomeno economico.

**Ten cuidado con:**

- Nunca uses linea sobre categorias sin orden: sugiere una transicion que no existe.

| | Puerto | Tipo |
|---|---|---|
| entra | Grafico | Una capa de gráfico, para apilar sobre un lienzo |
| sale | Grafico | Una capa de gráfico, para apilar sobre un lienzo |

| Parámetro | Por omisión |
|---|---|
| `ancho` | `2` |
| `marcadores` | `False` |
| `es_estimado` | `False` |

Si vienes de otro sistema — **R**: `+ geom_line()`

### + Linea de referencia

`graficos.referencia` · v1.0.0

**Qué hace.** Traza una linea horizontal o vertical en un valor que tu elijas.

**Cuándo usarlo.** Para marcar el cero, una meta, el promedio nacional o la fecha de un cambio de regimen.

**Cómo se lee el resultado.** Da un punto de comparacion: sin el, el lector no sabe si un valor es alto o bajo.

| | Puerto | Tipo |
|---|---|---|
| entra | Grafico | Una capa de gráfico, para apilar sobre un lienzo |
| sale | Grafico | Una capa de gráfico, para apilar sobre un lienzo |

| Parámetro | Por omisión |
|---|---|
| `eje` | `y` |
| `valor` | `0.0` |
| `etiqueta` | `None` |

Si vienes de otro sistema — **R**: `+ geom_hline()`

### + Linea de tendencia

`graficos.tendencia` · v1.0.0

**Qué hace.** Ajusta y dibuja una recta de minimos cuadrados sobre los puntos, con su intervalo.

**Cuándo usarlo.** Para ver de un vistazo si hay relacion y de que signo.

**Cómo se lee el resultado.** Es la misma recta de un MCO simple. Si el intervalo es tan ancho que cabe una recta horizontal, no hay evidencia de relacion.

**Ten cuidado con:**

- La tendencia es una estimacion: se dibuja en ambar, no en el color de la serie.

| | Puerto | Tipo |
|---|---|---|
| entra | Grafico | Una capa de gráfico, para apilar sobre un lienzo |
| sale | Grafico | Una capa de gráfico, para apilar sobre un lienzo |

| Parámetro | Por omisión |
|---|---|
| `metodo` | `lm` |
| `intervalo` | `True` |

Si vienes de otro sistema — **R**: `+ geom_smooth(method='lm')`

### + Puntos (dispersion)

`graficos.puntos` · v1.0.0

**Qué hace.** Dibuja un punto por observacion.

**Cuándo usarlo.** Para ver la relacion entre dos variables numericas, y sobre todo para ver la dispersion: cuanto se separan los casos de la relacion promedio.

**Cómo se lee el resultado.** La nube dice mas que la recta. Si los puntos se abren en abanico, hay heterocedasticidad; si se agrupan en islas, puede haber submuestras distintas.

| | Puerto | Tipo |
|---|---|---|
| entra | Grafico | Una capa de gráfico, para apilar sobre un lienzo |
| sale | Grafico | Una capa de gráfico, para apilar sobre un lienzo |

| Parámetro | Por omisión |
|---|---|
| `opacidad` | `0.85` |
| `tamano` | `9` |

Si vienes de otro sistema — **R**: `+ geom_point()`

### + Titulos y estilo

`graficos.tema` · v1.0.0

**Qué hace.** Pone titulo, nombres de los ejes, la nota al pie y elige modo claro u oscuro.

**Cuándo usarlo.** Al final, antes de dibujar. Un grafico sin titulo ni unidades no se puede usar fuera de la pantalla donde lo hiciste.

**Cómo se lee el resultado.** La nota al pie es donde va la fuente. Si el grafico sale de casa, la fuente no es opcional.

| | Puerto | Tipo |
|---|---|---|
| entra | Grafico | Una capa de gráfico, para apilar sobre un lienzo |
| sale | Grafico | Una capa de gráfico, para apilar sobre un lienzo |

| Parámetro | Por omisión |
|---|---|
| `titulo` | `None` |
| `eje_x` | `None` |
| `eje_y` | `None` |
| `nota` | `None` |
| `modo` | `claro` |
| `leyenda` | `True` |

Si vienes de otro sistema — **R**: `+ labs() + theme()`

### Dibujar

`graficos.dibujar` · v1.0.0

**Qué hace.** Convierte la pila de capas en una grafica interactiva.

**Cuándo usarlo.** Es el ultimo nodo de todo grafico.

**Cómo se lee el resultado.** La grafica es interactiva: pasa el cursor para ver los valores, y usa la leyenda para prender y apagar series.

| | Puerto | Tipo |
|---|---|---|
| entra | grafico | Una capa de gráfico, para apilar sobre un lienzo |
| sale | figura | Una gráfica lista para verse |

Si vienes de otro sistema — **R**: `print(p)`

### Lienzo (empezar un grafico)

`graficos.lienzo` · v1.0.0

**Qué hace.** Empieza un grafico: dice que columna va en el eje horizontal, cual en el vertical y cual separa las series por color.

**Cuándo usarlo.** Siempre es el primer nodo de un grafico. Encima se apilan las capas.

**Cómo se lee el resultado.** Por si solo no dibuja nada: hace falta al menos una capa (puntos, linea, barras).

**Ten cuidado con:**

- Abak no permite dos ejes verticales, a proposito. Dos medidas de escalas distintas van en dos graficos o indexadas a una base comun: con dos ejes se puede elegir la conclusion moviendo las escalas.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | Grafico | Una capa de gráfico, para apilar sobre un lienzo |

| Parámetro | Por omisión |
|---|---|
| `x` | `—` |
| `y` | `None` |
| `color` | `None` |
| `tamano` | `None` |
| `etiqueta` | `None` |

Si vienes de otro sistema — **R**: `ggplot(datos, aes(x, y, color))` · **SPSS**: `Constructor de graficos`

<a id="salida"></a>

## Entregables

Lo que te llevas: tablas de publicacion, exportar a Excel o CSV, informe en PDF.

### Exportar tabla

`salida.exportar` · v1.0.0

**Qué hace.** Guarda la tabla en un archivo para abrirlo en Excel o compartirlo.

**Cuándo usarlo.** Al final, cuando el resultado ya se va a usar fuera de Abak.

**Cómo se lee el resultado.** El archivo queda junto a los resultados de la ejecucion, y se descarga desde la pestana Resultados.

**Ten cuidado con:**

- Si exportas una tabla con columnas estimadas, la marca de ambar se pierde en el CSV. Anota en el documento cuales son estimaciones.

| | Puerto | Tipo |
|---|---|---|
| entra | datos | Una tabla de datos (filas y columnas) |
| sale | Archivo | Un número o un texto suelto |

| Parámetro | Por omisión |
|---|---|
| `nombre_archivo` | `resultados` |
| `formato` | `csv` |

Si vienes de otro sistema — **Stata**: `export excel` · **R**: `write.csv()`

### Tabla de resultados (publicacion)

`salida.tabla_publicacion` · v1.0.0

**Qué hace.** Pone varios modelos lado a lado en el formato de un articulo: coeficientes, errores estandar entre parentesis, estrellas y el pie con observaciones y R².

**Cuándo usarlo.** Cuando ya tienes tus especificaciones y quieres compararlas, o llevartelas a un documento sin volver a teclear numeros.

**Cómo se lee el resultado.** Se lee por renglones: como se mueve un coeficiente al cambiar de especificacion. Un coeficiente que cambia de signo o de tamano al agregar controles es la senal mas util de la tabla.

**Ten cuidado con:**

- Ensenar solo la especificacion que te gusto es el problema, no la tabla. Reporta todas las que corriste.

| | Puerto | Tipo |
|---|---|---|
| entra | Modelos | Un modelo ya estimado, con sus coeficientes y diagnósticos |
| sale | Tabla | Una tabla de datos (filas y columnas) |

| Parámetro | Por omisión |
|---|---|
| `nombres` | `—` |
| `decimales` | `3` |
| `errores_debajo` | `True` |

Si vienes de otro sistema — **Stata**: `esttab m1 m2 m3, se star` · **R**: `stargazer / modelsummary`
