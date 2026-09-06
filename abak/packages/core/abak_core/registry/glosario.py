"""Glosario de indicadores: qué es cada número que Abak pone en pantalla.

El problema que resuelve es el que hunde a SPSS y a EViews: alguien encuentra
el procedimiento, lo corre, y se queda mirando una tabla con «R²», «Prob(F)» y
«Durbin-Watson» sin saber cuál importa ni qué valor es bueno.

Cada estadístico que sale de una herramienta tiene aquí su ficha, y la interfaz
la enseña al lado del número. La misma ficha viaja al informe en PDF.

Tres campos, siempre:

  que_es        qué mide, en una frase, sin fórmula
  como_se_lee   qué hacer con el número que tienes enfrente
  ojo_con       el error que la gente comete con ESE indicador

Se busca por el nombre de la columna o la etiqueta del diagnóstico, normalizado
(sin acentos, sin mayúsculas). Un indicador sin ficha simplemente no muestra
nada: no se inventa una explicación.
"""

from __future__ import annotations

import unicodedata

from pydantic import BaseModel


class Indicador(BaseModel):
    titulo: str
    que_es: str
    como_se_lee: str
    ojo_con: str | None = None
    #: Referencias que la interfaz muestra como «para leer más».
    referencia: str | None = None


def normalizar(clave: str) -> str:
    """«R² ajustada» y «r2_ajustada» tienen que encontrar la misma ficha."""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", str(clave)) if not unicodedata.combining(c))
    limpio = "".join(c if c.isalnum() else "_" for c in sin_acentos.lower())
    limpio = limpio.replace("²", "2")
    while "__" in limpio:
        limpio = limpio.replace("__", "_")
    return limpio.strip("_")


_CRUDO: dict[str, Indicador] = {}


def _f(claves: str, **kw: str) -> None:
    """Registra una ficha bajo varios nombres: los mismos números aparecen con
    etiquetas distintas según la herramienta que los produjo."""
    ficha = Indicador(**kw)  # type: ignore[arg-type]
    for clave in claves.split("|"):
        _CRUDO[normalizar(clave)] = ficha


# --- lo que trae cualquier regresión ----------------------------------------

_f("coeficiente|coef|betas",
   titulo="Coeficiente",
   que_es="Cuánto cambia la variable que quieres explicar cuando esa variable sube una "
          "unidad y todas las demás se quedan igual.",
   como_se_lee="Mira primero el SIGNO (¿va en la dirección que esperabas?) y después el "
               "TAMAÑO en las unidades del problema. Si el modelo está en logaritmos de los "
               "dos lados, el coeficiente es una elasticidad: un cambio de 1% en la "
               "explicativa mueve ese porcentaje a la dependiente.",
   ojo_con="Un coeficiente mide asociación condicional, no efecto causal. Para hablar de "
           "causa hace falta un argumento de identificación, no un p-valor chico.")

_f("error_estandar|error_est|std_err|bse|desviacion_estandar",
   titulo="Error estándar",
   que_es="Qué tan preciso es el coeficiente. Es la incertidumbre que queda por trabajar "
          "con una muestra y no con toda la población.",
   como_se_lee="Mientras más chico, más preciso. Compáralo contra el coeficiente: si el "
               "error estándar es del mismo tamaño que el coeficiente, no puedes distinguir "
               "el efecto de cero.",
   ojo_con="Con datos económicos, los errores clásicos casi siempre salen demasiado chicos. "
           "Por eso Abak usa errores robustos (HC1) por omisión.")

_f("estadistico|estadistico_z|estadistico_t|t|z|tvalues|z_stat",
   titulo="Estadístico t (o z)",
   que_es="El coeficiente dividido entre su error estándar: cuántos errores estándar "
          "separan al coeficiente del cero.",
   como_se_lee="Como regla gruesa, por encima de 2 en valor absoluto el coeficiente se "
               "distingue de cero al 5%. El p-valor de al lado ya hace esa cuenta bien.",
   ojo_con="Con muestras grandes casi todo pasa de 2. Que se distinga de cero no lo vuelve "
           "importante.")

_f("p_valor|p|prob|pvalues",
   titulo="p-valor",
   que_es="La probabilidad de ver un resultado como el tuyo si en la realidad no hubiera "
          "ningún efecto.",
   como_se_lee="Por debajo de 0.05 se dice que el resultado es «significativo»: es difícil "
               "explicarlo por azar. Las estrellas son un atajo: *** al 1%, ** al 5%, * al 10%.",
   ojo_con="El p-valor NO dice qué tan grande es el efecto ni qué tan probable es tu "
           "hipótesis. Con 100 mil observaciones, una diferencia irrelevante sale "
           "significativa. Y si pruebas veinte cosas, una saldrá significativa por azar.",
   referencia="Wasserstein y Lazar (2016), declaración de la ASA sobre p-valores")

_f("ic_95|ic_bajo|ic_alto|intervalo_de_confianza|intervalo",
   titulo="Intervalo de confianza (95%)",
   que_es="El rango de valores del coeficiente compatibles con tus datos.",
   como_se_lee="Es más informativo que el p-valor: si el intervalo va de 0.01 a 0.02, el "
               "efecto es chico y preciso; si va de −5 a 8, no sabes casi nada aunque el "
               "punto central se vea grande. Si el intervalo cruza el cero, no puedes "
               "afirmar el signo.",
   ojo_con="No significa «hay 95% de probabilidad de que el verdadero valor esté aquí». "
           "Significa que un procedimiento así atrapa el valor verdadero el 95% de las veces.")

_f("r2|r_2|r_cuadrada|rsquared",
   titulo="R²",
   que_es="Qué proporción de la variación de la variable dependiente queda explicada por el "
          "modelo. Va de 0 a 1.",
   como_se_lee="Sirve para comparar modelos con la MISMA dependiente. No hay un valor "
               "«bueno» universal: en corte transversal con microdatos, un 0.2 puede ser "
               "excelente; en series de tiempo en niveles, un 0.98 puede no significar nada.",
   ojo_con="Agregar variables SIEMPRE sube el R², aunque sean ruido. Y un R² altísimo entre "
           "dos series con tendencia suele ser una regresión espuria, no un hallazgo.")

_f("r2_ajustada|r_cuadrada_ajustada|rsquared_adj",
   titulo="R² ajustada",
   que_es="El R² penalizado por el número de variables que metiste.",
   como_se_lee="Es la que sirve para comparar modelos con distinto número de explicativas. "
               "Si baja al agregar una variable, esa variable no estaba aportando.",
   ojo_con="Puede salir negativa cuando el modelo es peor que predecir con el promedio.")

_f("r2_dentro|r2_within|rsquared_within",
   titulo="R² dentro (within)",
   que_es="Cuánta de la variación DENTRO de cada entidad a lo largo del tiempo explica el modelo.",
   como_se_lee="Es la que importa en efectos fijos: ese estimador sólo usa la variación "
               "dentro de cada entidad.",
   ojo_con="Suele ser mucho más baja que un R² normal, y eso no es una falla del modelo.")

_f("r2_entre|r2_between",
   titulo="R² entre (between)",
   que_es="Cuánta de la variación ENTRE entidades explica el modelo.",
   como_se_lee="Alta con R² dentro baja significa que tu modelo explica por qué unas "
               "entidades difieren de otras, pero no por qué cambian en el tiempo.")

_f("observaciones|nobs|n",
   titulo="Observaciones",
   que_es="Cuántas filas se usaron de verdad para estimar.",
   como_se_lee="Compáralo con las filas que tenías. Si es mucho menor, perdiste datos: "
               "faltantes, rezagos o filtros.",
   ojo_con="Si dos modelos que quieres comparar usan distinto número de observaciones, "
           "no son comparables: sus AIC y R² no se pueden poner lado a lado.")

_f("aic",
   titulo="AIC (criterio de Akaike)",
   que_es="Una medida de ajuste que castiga la complejidad del modelo.",
   como_se_lee="Más bajo es mejor. Sólo tiene sentido comparado con el AIC de otro modelo "
               "sobre LOS MISMOS datos.",
   ojo_con="Un AIC más bajo no garantiza mejor pronóstico fuera de muestra. La única prueba "
           "honesta es guardar los últimos periodos y ver qué tan lejos cae.")

_f("bic|schwarz",
   titulo="BIC (criterio de Schwarz)",
   que_es="Como el AIC, pero castiga más la complejidad conforme crece la muestra.",
   como_se_lee="Más bajo es mejor. Tiende a elegir modelos más chicos que el AIC.",
   ojo_con="AIC y BIC pueden elegir modelos distintos. No hay un ganador universal: el AIC "
           "busca predecir, el BIC busca el modelo verdadero.")

_f("log_verosimilitud|llf|logll",
   titulo="Log-verosimilitud",
   que_es="Qué tan probables son tus datos bajo el modelo estimado.",
   como_se_lee="Más alta es mejor, pero sólo comparada entre modelos sobre los mismos datos. "
               "Por sí sola no dice nada.")

_f("f|fvalue|prob_f|f_pvalue",
   titulo="Estadístico F",
   que_es="Prueba si TODAS las explicativas juntas aportan algo, contra un modelo con puras constantes.",
   como_se_lee="Prob(F) por debajo de 0.05 significa que el modelo en conjunto aporta.",
   ojo_con="Un F significativo con ningún coeficiente significativo por separado es la firma "
           "de la colinealidad. Revisa el VIF.")

_f("pseudo_r2|prsquared",
   titulo="Pseudo R²",
   que_es="El análogo del R² para modelos de elección discreta (logit, probit).",
   como_se_lee="No es una proporción de varianza explicada: sirve para comparar modelos "
               "entre sí, no para juzgar uno solo. Valores de 0.2 a 0.4 suelen ser buenos.",
   ojo_con="No lo reportes como si fuera un R²: no significa lo mismo.")

_f("vif",
   titulo="VIF (factor de inflación de varianza)",
   que_es="Cuánto se infla la imprecisión del coeficiente porque esa variable se explica con "
          "las otras explicativas.",
   como_se_lee="Por arriba de 10 hay colinealidad seria; entre 5 y 10 conviene mirarlo.",
   ojo_con="La colinealidad NO sesga los coeficientes: los vuelve imprecisos. Quitar una "
           "variable por VIF alto puede introducir sesgo por variable omitida, que es peor.")

# --- series de tiempo -------------------------------------------------------

_f("adf_estadistico|adf|adf_p|adf_rezagos",
   titulo="ADF (Dickey-Fuller aumentada)",
   que_es="Prueba si la serie tiene raíz unitaria, es decir, si no vuelve a un nivel de "
          "largo plazo.",
   como_se_lee="La hipótesis nula es que SÍ tiene raíz unitaria. Un p-valor por debajo de "
               "0.05 la rechaza: la serie es estacionaria.",
   ojo_con="Ojo: aquí rechazar es la buena noticia, al revés que en KPSS. Con menos de 50 "
           "observaciones la prueba tiene poca potencia.")

_f("kpss_estadistico|kpss|kpss_p",
   titulo="KPSS",
   que_es="La otra prueba de estacionariedad, con la hipótesis nula al revés que ADF.",
   como_se_lee="La nula es que la serie SÍ es estacionaria. Un p-valor por ARRIBA de 0.05 no "
               "la rechaza: la serie es estacionaria.",
   ojo_con="Se corren las dos juntas porque cada una por separado tiene poca potencia. Que "
           "las dos coincidan es lo que vuelve sólida la conclusión.")

_f("estadistico_traza|traza",
   titulo="Estadístico de la traza (Johansen)",
   que_es="Cuenta cuántas relaciones de largo plazo (cointegración) hay entre tus series.",
   como_se_lee="Se recorre r = 0, 1, 2... El primer renglón que NO se rechaza dice cuántas "
               "relaciones hay. Si hay al menos una, la regresión en niveles no es espuria y "
               "el modelo correcto es un VECM.",
   ojo_con="Es sensible al número de rezagos y al término determinístico. Reporta qué "
           "elegiste o el resultado no es reproducible.")

_f("valor_critico_5pct|valor_critico",
   titulo="Valor crítico al 5%",
   que_es="El umbral contra el que se compara el estadístico de la prueba.",
   como_se_lee="Si el estadístico lo supera, se rechaza la hipótesis nula al 5%.")

_f("pronostico|forecast|mean",
   titulo="Pronóstico",
   que_es="El valor que el modelo espera para ese periodo futuro.",
   como_se_lee="Nunca lo leas solo: la banda de al lado es la que dice cuánto sabes. Un "
               "pronóstico puntual sin banda es una opinión disfrazada de número.",
   ojo_con="Es una ESTIMACIÓN, no un dato. En Abak sale en ámbar por eso.")

_f("banda_baja|banda_alta|mean_ci_lower|mean_ci_upper",
   titulo="Banda del pronóstico (95%)",
   que_es="El rango dentro del cual el modelo espera que caiga el valor real.",
   como_se_lee="Mientras más se abre hacia el futuro, menos sabes de los periodos lejanos. "
               "Si la banda es más ancha que la decisión que quieres tomar, el pronóstico no "
               "alcanza para tomarla.",
   ojo_con="La banda supone que el modelo es correcto. No incluye el riesgo de haberse "
           "equivocado de modelo, que suele ser el riesgo grande.")

_f("efecto",
   titulo="Respuesta al impulso",
   que_es="Cómo responde una variable, periodo a periodo, a un choque de una desviación "
          "estándar en otra.",
   como_se_lee="Sigue la trayectoria: cuándo llega el efecto máximo y cuándo se agota. Si la "
               "banda cruza el cero, el efecto no se distingue de cero en ese periodo.",
   ojo_con="La identificación de Cholesky impone un orden causal contemporáneo. Cambiar el "
           "orden de las variables cambia las respuestas, y ese orden hay que justificarlo.")

_f("tendencia",
   titulo="Tendencia",
   que_es="El componente de largo plazo que el filtro separó de la serie.",
   como_se_lee="Es una construcción del filtro, no un dato observado.",
   ojo_con="El filtro HP inventa dinámicas al final de la muestra, que es justo donde se "
           "toman las decisiones. Compara con el filtro de Hamilton.")

_f("ciclo|brecha",
   titulo="Ciclo (brecha)",
   que_es="La desviación de la serie respecto a su tendencia de largo plazo.",
   como_se_lee="Positivo significa por encima de su nivel de largo plazo.",
   ojo_con="La brecha del producto es de las cifras menos confiables de la macro: se revisa "
           "mucho conforme llegan datos nuevos.")

# --- espacial ---------------------------------------------------------------

_f("i|moran_i|i_de_moran",
   titulo="I de Moran",
   que_es="Mide si los valores parecidos tienden a estar cerca unos de otros.",
   como_se_lee="Cerca de +1: los altos se agrupan con altos y los bajos con bajos. Cerca de "
               "0: sin patrón. Negativo: tablero de ajedrez, cada valor rodeado de sus "
               "opuestos. El p-valor dice si el patrón se distingue del azar.",
   ojo_con="Depende por completo de la matriz de vecindad que elegiste. Prueba al menos dos "
           "y reporta si la conclusión aguanta el cambio.",
   referencia="Moran (1950); Anselin (1995)")

_f("esperado_bajo_azar|ei",
   titulo="Valor esperado bajo azar",
   que_es="El I de Moran que saldría si los valores estuvieran repartidos al azar.",
   como_se_lee="Es −1/(n−1), un número pequeño y negativo. Compara tu I contra éste, no "
               "contra cero.")

_f("w_dependiente_rho|rho",
   titulo="ρ (rho) — contagio espacial",
   que_es="Qué tan fuerte es el efecto de los vecinos en un modelo SAR.",
   como_se_lee="Positivo y significativo significa que un cambio en un punto se propaga a sus "
               "vecinos, y de ahí a los vecinos de sus vecinos.",
   ojo_con="Con ρ distinto de cero, los coeficientes β NO son el efecto total. El efecto "
           "total incluye lo que regresa por la red.")

_f("error_espacial_lambda|lambda",
   titulo="λ (lambda) — error espacial",
   que_es="Qué tanto se parecen los errores de puntos vecinos en un modelo SEM.",
   como_se_lee="A diferencia de ρ, aquí los coeficientes de X sí se leen como en MCO. Lo que "
               "se corrige es la inferencia.")

_f("lisa_i|lisa_tipo|lisa_p",
   titulo="LISA (Moran local)",
   que_es="Clasifica cada punto según su valor y el de sus vecinos.",
   como_se_lee="Alto-Alto es un núcleo caliente; Bajo-Bajo, uno frío. Alto-Bajo y Bajo-Alto "
               "son atípicos: una zona cara rodeada de baratas, o al revés. En mercados "
               "inmobiliarios, los Bajo-Alto suelen ser las oportunidades.",
   ojo_con="Los p-valores no están corregidos por comparaciones múltiples: con 2,400 puntos, "
           "unos 120 saldrán «significativos» por azar al 5%.")

_f("rezago_espacial",
   titulo="Rezago espacial",
   que_es="El promedio de la variable entre los vecinos de cada punto.",
   como_se_lee="Es la variable que entra en los modelos espaciales. Sólo se lee como "
               "«promedio de los vecinos» si la matriz está estandarizada por filas.")

# --- insumo-producto --------------------------------------------------------

_f("multiplicador_produccion|multiplicador",
   titulo="Multiplicador de producción",
   que_es="Cuánta producción total genera cada peso de demanda final de ese sector, contando "
          "todas las vueltas de la cadena de proveedores.",
   como_se_lee="Un 1.8 significa que por cada peso de demanda, la economía produce 1.80: uno "
               "directo y 80 centavos repartidos entre los proveedores.",
   ojo_con="Es una COTA SUPERIOR. Supone capacidad ociosa, precios fijos y receta productiva "
           "constante. Sirve para ordenar sectores entre sí, no para prometer resultados.",
   referencia="Miller y Blair, «Input-Output Analysis», cap. 6")

_f("multiplicador_empleo|coeficiente_empleo",
   titulo="Multiplicador de empleo",
   que_es="Cuánto empleo total se genera por unidad de demanda final de ese sector.",
   como_se_lee="Compáralo entre sectores para saber cuál genera más empleo por peso invertido.",
   ojo_con="Supone que la relación empleo-producción de hoy se mantiene. No captura "
           "automatización ni cambios de productividad.")

_f("encadenamiento_atras",
   titulo="Encadenamiento hacia atrás",
   que_es="Cuánto jala ese sector al resto de la economía cuando produce.",
   como_se_lee="Está normalizado al promedio: por arriba de 1 significa que jala más que el "
               "sector promedio.",
   referencia="Rasmussen (1956); Hirschman (1958)")

_f("encadenamiento_adelante",
   titulo="Encadenamiento hacia adelante",
   que_es="Cuánto lo jala el resto de la economía a él, por ser insumo de muchos otros.",
   como_se_lee="Un sector con los dos encadenamientos por encima de 1 es «clave»: es donde "
               "la política industrial suele rendir más.")

_f("dispersion_atras",
   titulo="Dispersión del encadenamiento",
   que_es="Si el sector jala a muchos proveedores o a unos pocos.",
   como_se_lee="Alta significa que el encadenamiento depende de pocos proveedores, y eso es "
               "más frágil que el mismo encadenamiento repartido.")

_f("efecto_directo|efecto_indirecto|produccion_adicional",
   titulo="Efecto directo e indirecto",
   que_es="El directo es lo que produce de más el sector que recibe el choque; el indirecto, "
          "lo que producen de más sus proveedores, y los proveedores de éstos.",
   como_se_lee="La suma es el efecto total. Un indirecto grande indica un sector muy "
               "encadenado.")

_f("filtracion_por_peso",
   titulo="Filtración por peso",
   que_es="Cuánto de cada peso de ingreso se sale del circuito por ahorro, impuestos e "
          "importaciones.",
   como_se_lee="Mientras más se filtra, más chico el multiplicador. El multiplicador es "
               "exactamente 1 dividido entre esta cifra.")

# --- machine learning -------------------------------------------------------

_f("rmse",
   titulo="RMSE (raíz del error cuadrático medio)",
   que_es="El error típico del modelo, en las mismas unidades que la variable que predices.",
   como_se_lee="Más bajo es mejor. Compáralo contra la desviación estándar de la variable: "
               "si el RMSE es parecido, el modelo no aporta sobre predecir el promedio.",
   ojo_con="Castiga mucho los errores grandes. Si te importa más el error típico que los "
           "casos extremos, mira el MAE.")

_f("mae",
   titulo="MAE (error absoluto medio)",
   que_es="Qué tanto se equivoca el modelo en promedio, sin castigar de más los errores grandes.",
   como_se_lee="Más bajo es mejor, en las unidades de la variable. Es más fácil de explicar "
               "que el RMSE: «en promedio le erramos por tanto».")

_f("mape_pct|mape",
   titulo="MAPE (error porcentual absoluto medio)",
   que_es="El error promedio expresado en porcentaje del valor real.",
   como_se_lee="Permite comparar modelos sobre variables de escalas distintas.",
   ojo_con="No está definido si hay ceros, y castiga más los errores por arriba que por "
           "abajo. Con valores cercanos a cero se dispara.")

_f("importancia|feature_importance",
   titulo="Importancia de la variable",
   que_es="Cuánto usa el modelo esa variable para predecir.",
   como_se_lee="Ordena las variables por cuánto aportan al poder predictivo.",
   ojo_con="NO es un efecto causal ni un coeficiente. Dos variables muy correlacionadas se "
           "reparten la importancia de forma arbitraria.")

# --- descriptivos y pruebas -------------------------------------------------

_f("media|promedio|mean",
   titulo="Media",
   que_es="El promedio aritmético.",
   como_se_lee="Compárala con la mediana: si son muy distintas, la distribución es asimétrica "
               "y la media está siendo jalada por los extremos.")

_f("mediana|p50",
   titulo="Mediana",
   que_es="El valor que parte los datos a la mitad.",
   como_se_lee="Es más representativa que la media cuando hay valores extremos, que es el "
               "caso normal en ingreso, riqueza y precios.")

_f("minimo|min",
   titulo="Mínimo",
   que_es="El valor más chico de la columna.",
   como_se_lee="Es la primera revisión de calidad: un mínimo negativo en un precio, una edad "
               "o una superficie significa que hay basura en los datos, no un hallazgo.",
   ojo_con="Un mínimo de 0 muchas veces es un dato faltante que alguien capturó como cero. "
           "Vale la pena contar cuántos ceros hay antes de modelar.")

_f("maximo|max",
   titulo="Máximo",
   que_es="El valor más grande de la columna.",
   como_se_lee="Compáralo con p75: si el máximo es varias veces el percentil 75, hay una cola "
               "larga y unos pocos casos van a dominar cualquier promedio.",
   ojo_con="En datos administrativos el máximo suele ser un tope de captura (un ingreso "
           "«topado»), no el valor real. Eso sesga hacia abajo cualquier estimación.")

_f("p25|cuartil_1|q1|percentil_25",
   titulo="Percentil 25",
   que_es="El valor por debajo del cual queda una cuarta parte de los casos.",
   como_se_lee="Junto con p75 delimita a la mitad central de los datos, la parte que no "
               "depende de los extremos.")

_f("p75|cuartil_3|q3|percentil_75",
   titulo="Percentil 75",
   que_es="El valor por debajo del cual quedan tres cuartas partes de los casos.",
   como_se_lee="La distancia entre p25 y p75 es el rango intercuartílico: la medida de "
               "dispersión que no se mueve cuando hay valores extremos.")

_f("desv_est|desviacion_estandar_muestral|std",
   titulo="Desviación estándar",
   que_es="Qué tan dispersos están los datos alrededor de su media.",
   como_se_lee="En una distribución más o menos normal, dos tercios de los casos caen a una "
               "desviación de la media.")

_f("coef_variacion",
   titulo="Coeficiente de variación",
   que_es="La desviación estándar dividida entre la media: dispersión relativa.",
   como_se_lee="Permite comparar la dispersión de variables con unidades distintas. Por "
               "arriba de 1, la variable es muy dispersa.")

_f("asimetria|skew",
   titulo="Asimetría",
   que_es="Si la distribución tiene una cola larga hacia un lado.",
   como_se_lee="Cerca de 0 es simétrica. Positiva significa cola larga a la derecha, que es "
               "lo típico del ingreso.",
   ojo_con="Por arriba de 2 en valor absoluto, considera trabajar en logaritmos.")

_f("faltantes|faltantes_antes|na",
   titulo="Datos faltantes",
   que_es="Cuántos valores no están.",
   como_se_lee="Si son muchos, cualquier modelo que estimes después va a descansar en una "
               "submuestra que puede no representar al total.",
   ojo_con="Que falten al azar es un supuesto, no un hecho. Si faltan más en los casos "
           "pobres, tu resultado va a estar sesgado.")

_f("correlacion|corr",
   titulo="Correlación",
   que_es="Qué tan juntas se mueven dos variables. Va de −1 a 1.",
   como_se_lee="Cerca de 0 NO significa «sin relación»: significa sin relación LINEAL. Una U "
               "invertida perfecta da correlación cero.",
   ojo_con="Con 20 variables hay 190 pares: unos 10 saldrán «significativos» al 5% sin que "
           "exista nada.")

_f("estadistico_chi2|chi2|grados_libertad",
   titulo="Prueba χ² (Hausman)",
   que_es="Compara dos estimadores para decidir cuál usar.",
   como_se_lee="En Hausman: rechazar (p < 0.05) significa que efectos aleatorios está sesgado "
               "y hay que usar efectos fijos.",
   ojo_con="No rechazar no prueba que aleatorios sea correcto: puede ser falta de potencia.")

_f("durbin_watson",
   titulo="Durbin-Watson",
   que_es="Detecta si los errores del modelo están correlacionados de un periodo al siguiente.",
   como_se_lee="Cerca de 2 está bien. Por debajo de 1.5, autocorrelación positiva: usa "
               "errores HAC. Por arriba de 2.5, negativa: revisa si sobre-diferenciaste.",
   ojo_con="No sirve si el modelo incluye rezagos de la variable dependiente. Ahí usa "
           "Breusch-Godfrey.")

_f("estrellas",
   titulo="Estrellas de significancia",
   que_es="Un atajo visual para el p-valor: *** al 1%, ** al 5%, * al 10%.",
   como_se_lee="Sirven para recorrer una tabla rápido.",
   ojo_con="Buscar estrellas es cómo se llega a resultados que no se replican. Decide qué vas "
           "a estimar ANTES de ver los resultados.")

_f("multiplicador_ingreso|coeficiente_ingreso",
   titulo="Multiplicador de ingreso",
   que_es="Cuánto ingreso de los hogares genera cada unidad de demanda final del sector.",
   como_se_lee="Compáralo entre sectores: dice cuál derrama más en salarios.")

_f("efecto_total_sobre_pib",
   titulo="Efecto total sobre el PIB",
   que_es="El gasto adicional multiplicado por el multiplicador.",
   ojo_con="La evidencia empírica pone el multiplicador del gasto entre 0.5 y 2.5 según el "
           "país y el momento del ciclo. Este número es el de libro de texto.",
   como_se_lee="Úsalo para ordenar magnitudes, no para prometer resultados.")


GLOSARIO: dict[str, Indicador] = dict(_CRUDO)


def buscar(clave: str) -> Indicador | None:
    """La ficha de un indicador, o None si no hay. No se inventa nada."""
    return GLOSARIO.get(normalizar(clave))


def como_json() -> dict[str, dict]:
    return {clave: ficha.model_dump() for clave, ficha in GLOSARIO.items()}
