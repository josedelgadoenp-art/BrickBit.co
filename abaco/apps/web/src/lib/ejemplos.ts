/**
 * Análisis de ejemplo, listos para abrir.
 *
 * No son una demostración de juguete: cada uno resuelve una pregunta económica
 * real de punta a punta, y sirve como plantilla para empezar.
 */

import type { Grafo } from './tipos';

interface N { id: string; op: string; etiqueta: string; params?: Record<string, unknown>; x?: number; y?: number }

function armar(titulo: string, nodos: N[], aristas: [string, string, string, string][], semilla = 42): Grafo {
  return {
    version_esquema: '1',
    titulo,
    semilla,
    nodos: nodos.map((n, i) => ({
      id: n.id, op: n.op, etiqueta: n.etiqueta, params: n.params ?? {},
      posicion: { x: n.x ?? 80 + (i % 2) * 340, y: n.y ?? 60 + i * 120 },
      notas: null,
    })),
    aristas: aristas.map(([o, po, d, pd], i) => ({
      id: `a${i}`, origen: o, puerto_origen: po, destino: d, puerto_destino: pd,
    })),
  };
}

const SECTORES = [
  'Agropecuario', 'Mineria', 'Energia', 'Manufactura alimentos', 'Manufactura metalica',
  'Manufactura otras', 'Construccion', 'Comercio', 'Transporte', 'Informacion y medios',
  'Servicios financieros', 'Servicios diversos',
];

export const EJEMPLOS: { id: string; titulo: string; descripcion: string; grafo: () => Grafo }[] = [
  {
    id: 'hedonico',
    titulo: '¿Qué explica el precio de la vivienda?',
    descripcion: 'Regresión log-log por entidad, con errores robustos, diagnósticos y gráfica.',
    grafo: () => armar('¿Qué explica el precio de la vivienda?', [
      { id: 'd1', op: 'datos.ejemplo', etiqueta: 'Entidades', params: { conjunto: 'mexico_estados' }, x: 60, y: 60 },
      { id: 't1', op: 'transformar.calcular', etiqueta: 'Log precio', params: { operacion: 'log', columna_a: 'precio_m2' }, x: 60, y: 200 },
      { id: 't2', op: 'transformar.calcular', etiqueta: 'Log ingreso', params: { operacion: 'log', columna_a: 'ingreso_hogar_mensual' }, x: 60, y: 320 },
      { id: 'x1', op: 'explorar.descriptivos', etiqueta: 'Descriptivos', params: { columnas: ['precio_m2', 'plusvalia_pct', 'escolaridad_anios'] }, x: 420, y: 60 },
      { id: 'm1', op: 'econometria.mco', etiqueta: 'Modelo hedónico', params: { y: 'log_precio_m2', x: ['log_ingreso_hogar_mensual', 'escolaridad_anios', 'empleo_formal_pct'], errores: 'HC3' }, x: 420, y: 240 },
      { id: 'g1', op: 'econometria.diagnosticos', etiqueta: 'Supuestos', params: {}, x: 780, y: 240 },
      { id: 'v1', op: 'econometria.colinealidad', etiqueta: 'Colinealidad', params: { columnas: ['log_ingreso_hogar_mensual', 'escolaridad_anios', 'empleo_formal_pct'] }, x: 780, y: 380 },
      { id: 'p1', op: 'graficos.lienzo', etiqueta: 'Lienzo', params: { x: 'escolaridad_anios', y: 'precio_m2', color: 'ciclo', etiqueta: 'entidad' }, x: 60, y: 440 },
      { id: 'p2', op: 'graficos.puntos', etiqueta: '+ Puntos', params: {}, x: 60, y: 560 },
      { id: 'p3', op: 'graficos.tendencia', etiqueta: '+ Tendencia', params: {}, x: 60, y: 660 },
      { id: 'p4', op: 'graficos.tema', etiqueta: 'Títulos', params: { titulo: 'Precio por m² y escolaridad', eje_y: 'Precio por m² (MXN)', nota: 'Fuente: ejemplo de Ábaco. El precio por m² es una estimación.', modo: 'oscuro' }, x: 60, y: 760 },
      { id: 'p5', op: 'graficos.dibujar', etiqueta: 'Dibujar', params: {}, x: 420, y: 760 },
    ], [
      ['d1', 'datos', 't1', 'datos'], ['t1', 'datos', 't2', 'datos'],
      ['t2', 'datos', 'x1', 'datos'], ['t2', 'datos', 'm1', 'datos'],
      ['m1', 'modelo', 'g1', 'modelo'], ['t2', 'datos', 'v1', 'datos'],
      ['t2', 'datos', 'p1', 'datos'], ['p1', 'grafico', 'p2', 'grafico'],
      ['p2', 'grafico', 'p3', 'grafico'], ['p3', 'grafico', 'p4', 'grafico'],
      ['p4', 'grafico', 'p5', 'grafico'],
    ]),
  },
  {
    id: 'espacial',
    titulo: '¿La ubicación importa? (econometría espacial)',
    descripcion: 'Matriz de vecindad, I de Moran, pruebas LM para decidir entre SAR y SEM, y el modelo.',
    grafo: () => armar('¿La ubicación importa?', [
      { id: 'd1', op: 'datos.ejemplo', etiqueta: 'Entidades', params: { conjunto: 'mexico_estados' }, x: 60, y: 60 },
      { id: 't1', op: 'transformar.calcular', etiqueta: 'Log precio', params: { operacion: 'log', columna_a: 'precio_m2' }, x: 60, y: 190 },
      { id: 'u1', op: 'datos.ubicacion', etiqueta: 'Con ubicación', params: { latitud: 'lat', longitud: 'lng' }, x: 60, y: 310 },
      { id: 'w1', op: 'espacial.pesos', etiqueta: 'Vecinos (4 más cercanos)', params: { metodo: 'knn', k: 4 }, x: 60, y: 430 },
      { id: 'mo', op: 'espacial.moran', etiqueta: 'I de Moran', params: { columnas: ['log_precio_m2', 'plusvalia_pct'], permutaciones: 999 }, x: 430, y: 200 },
      { id: 'lm', op: 'espacial.diagnostico', etiqueta: '¿SAR o SEM?', params: { y: 'log_precio_m2', x: ['escolaridad_anios', 'empleo_formal_pct'] }, x: 430, y: 360 },
      { id: 'sar', op: 'espacial.sar', etiqueta: 'Modelo SAR', params: { y: 'log_precio_m2', x: ['escolaridad_anios', 'empleo_formal_pct'] }, x: 430, y: 520 },
      { id: 'li', op: 'espacial.lisa', etiqueta: 'Conglomerados', params: { columna: 'log_precio_m2' }, x: 800, y: 200 },
    ], [
      ['d1', 'datos', 't1', 'datos'], ['t1', 'datos', 'u1', 'datos'],
      ['u1', 'datos', 'w1', 'datos'],
      ['u1', 'datos', 'mo', 'datos'], ['w1', 'pesos', 'mo', 'pesos'],
      ['u1', 'datos', 'lm', 'datos'], ['w1', 'pesos', 'lm', 'pesos'],
      ['u1', 'datos', 'sar', 'datos'], ['w1', 'pesos', 'sar', 'pesos'],
      ['u1', 'datos', 'li', 'datos'], ['w1', 'pesos', 'li', 'pesos'],
    ]),
  },
  {
    id: 'macro',
    titulo: 'Pronóstico del PIB y respuesta a un choque',
    descripcion: 'Raíz unitaria, ARIMA con banda de pronóstico, VAR con impulso-respuesta y brecha del producto.',
    grafo: () => armar('PIB: pronóstico y respuesta a choques', [
      { id: 'd1', op: 'datos.ejemplo', etiqueta: 'Macro trimestral', params: { conjunto: 'mexico_macro' }, x: 60, y: 60 },
      { id: 's1', op: 'datos.serie_temporal', etiqueta: 'Serie trimestral', params: { columna_fecha: 'fecha', frecuencia: 'QS' }, x: 60, y: 190 },
      { id: 'ru', op: 'series.estacionariedad', etiqueta: 'Raíz unitaria', params: { columnas: ['pib_indice', 'inflacion_anual', 'tasa_objetivo'] }, x: 430, y: 60 },
      { id: 'ar', op: 'series.arima', etiqueta: 'ARIMA del PIB', params: { variable: 'pib_indice', p: 2, d: 1, q: 1, horizonte: 12 }, x: 430, y: 200 },
      { id: 'va', op: 'series.var', etiqueta: 'VAR macro', params: { variables: ['inflacion_anual', 'tasa_objetivo', 'desempleo'], rezagos: 4, periodos_irf: 12 }, x: 430, y: 360 },
      { id: 'ci', op: 'series.ciclo', etiqueta: 'Brecha del producto', params: { variable: 'pib_indice', metodo: 'hp', lamb: 1600 }, x: 430, y: 520 },
      { id: 'p1', op: 'graficos.lienzo', etiqueta: 'Lienzo', params: { x: 'fecha', y: 'pronostico' }, x: 800, y: 200 },
      { id: 'p2', op: 'graficos.banda', etiqueta: '+ Banda', params: { limite_bajo: 'banda_baja', limite_alto: 'banda_alta' }, x: 800, y: 320 },
      { id: 'p3', op: 'graficos.linea', etiqueta: '+ Línea', params: { es_estimado: true }, x: 800, y: 430 },
      { id: 'p4', op: 'graficos.tema', etiqueta: 'Títulos', params: { titulo: 'PIB: pronóstico a 12 trimestres', modo: 'oscuro', nota: 'Serie simulada de ejemplo. Todo lo pronosticado es estimación.' }, x: 800, y: 540 },
      { id: 'p5', op: 'graficos.dibujar', etiqueta: 'Dibujar', params: {}, x: 800, y: 650 },
    ], [
      ['d1', 'datos', 's1', 'datos'], ['s1', 'datos', 'ru', 'datos'],
      ['s1', 'datos', 'ar', 'datos'], ['s1', 'datos', 'va', 'datos'],
      ['s1', 'datos', 'ci', 'datos'], ['ar', 'pronostico', 'p1', 'datos'],
      ['p1', 'grafico', 'p2', 'grafico'], ['p2', 'grafico', 'p3', 'grafico'],
      ['p3', 'grafico', 'p4', 'grafico'], ['p4', 'grafico', 'p5', 'grafico'],
    ]),
  },
  {
    id: 'insumo',
    titulo: '¿Qué arrastra la construcción? (insumo-producto)',
    descripcion: 'Leontief, multiplicadores, encadenamientos de Rasmussen e impacto de un choque de demanda.',
    grafo: () => armar('¿Qué arrastra la construcción?', [
      { id: 'd1', op: 'datos.ejemplo', etiqueta: 'Matriz insumo-producto', params: { conjunto: 'insumo_producto' }, x: 60, y: 60 },
      { id: 'io', op: 'macro.insumo_producto', etiqueta: 'Sistema resuelto', params: { columna_sectores: 'sector', columnas_matriz: SECTORES, produccion_total: 'produccion_total', demanda_final: 'demanda_final', empleo: 'empleo_miles', remuneraciones: 'remuneraciones' }, x: 60, y: 200 },
      { id: 'en', op: 'macro.encadenamientos', etiqueta: 'Encadenamientos', params: {}, x: 430, y: 130 },
      { id: 'im', op: 'macro.impacto', etiqueta: 'Choque a construcción', params: { choques: { Construccion: 500000 } }, x: 430, y: 280 },
      { id: 'ke', op: 'macro.multiplicador_keynesiano', etiqueta: 'Multiplicador del gasto', params: { propension_consumo: 0.68, tasa_impuestos: 0.16, propension_importar: 0.32, gasto_adicional: 500000 }, x: 430, y: 430 },
    ], [
      ['d1', 'datos', 'io', 'datos'], ['io', 'sistema', 'en', 'sistema'], ['io', 'sistema', 'im', 'sistema'],
    ]),
  },
  {
    id: 'panel',
    titulo: 'Inversión y crecimiento (panel de entidades)',
    descripcion: 'Efectos fijos con errores agrupados y prueba de Hausman contra efectos aleatorios.',
    grafo: () => armar('Inversión y crecimiento por entidad', [
      { id: 'd1', op: 'datos.ejemplo', etiqueta: 'Panel de entidades', params: { conjunto: 'panel_estados' }, x: 60, y: 60 },
      { id: 't1', op: 'transformar.calcular', etiqueta: 'Log PIB per cápita', params: { operacion: 'log', columna_a: 'pib_per_capita' }, x: 60, y: 190 },
      { id: 't2', op: 'transformar.calcular', etiqueta: 'Log inversión', params: { operacion: 'log', columna_a: 'inversion_pc' }, x: 60, y: 310 },
      { id: 'pa', op: 'datos.panel', etiqueta: 'Panel definido', params: { entidad: 'entidad', periodo: 'anio' }, x: 60, y: 430 },
      { id: 'fe', op: 'econometria.panel', etiqueta: 'Efectos fijos', params: { y: 'log_pib_per_capita', x: ['log_inversion_pc', 'empleo_formal_pct'], efectos: 'fijos', errores: 'agrupados_por_entidad', prueba_hausman: true }, x: 430, y: 430 },
    ], [
      ['d1', 'datos', 't1', 'datos'], ['t1', 'datos', 't2', 'datos'],
      ['t2', 'datos', 'pa', 'datos'], ['pa', 'datos', 'fe', 'datos'],
    ]),
  },
  {
    id: 'ml',
    titulo: 'Predecir el gasto en vivienda (XGBoost)',
    descripcion: 'Partición honesta, XGBoost, métricas dentro y fuera de muestra, e importancia de variables.',
    grafo: () => armar('Predecir el gasto en vivienda', [
      { id: 'd1', op: 'datos.ejemplo', etiqueta: 'Hogares', params: { conjunto: 'hogares' }, x: 60, y: 60 },
      { id: 't1', op: 'transformar.calcular', etiqueta: 'Log ingreso', params: { operacion: 'log', columna_a: 'ingreso_mensual' }, x: 60, y: 190 },
      { id: 'pa', op: 'ml.particion', etiqueta: 'Entrenamiento y prueba', params: { proporcion_prueba: 0.25, aleatoria: true }, x: 60, y: 310 },
      { id: 'xg', op: 'ml.xgboost', etiqueta: 'XGBoost', params: { y: 'gasto_vivienda', x: ['log_ingreso_mensual', 'edad_jefe', 'escolaridad_anios', 'tamano_hogar', 'urbano'], n_arboles: 300, profundidad: 4 }, x: 430, y: 310 },
    ], [
      ['d1', 'datos', 't1', 'datos'], ['t1', 'datos', 'pa', 'datos'],
      ['pa', 'entrenamiento', 'xg', 'entrenamiento'], ['pa', 'prueba', 'xg', 'prueba'],
    ]),
  },
];
