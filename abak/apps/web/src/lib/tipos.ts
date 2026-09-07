/**
 * Tipos del contrato con el backend.
 *
 * Espejan los modelos Pydantic de `abak_core.graph.spec` y los descriptores
 * del registro. La fuente de verdad está en Python: aquí sólo se declara la
 * forma para que TypeScript ayude.
 */

export type TipoPuerto =
  | 'cualquiera' | 'tabla' | 'serie' | 'panel' | 'geotabla'
  | 'modelo' | 'pesos' | 'mio' | 'capa' | 'figura' | 'escalar';

export interface Puerto {
  nombre: string;
  tipo: TipoPuerto;
  requerido: boolean;
  multiple: boolean;
  titulo: string | null;
  descripcion: string | null;
  ayuda_tipo: string;
}

export interface Ayuda {
  que_hace: string;
  cuando_usarlo: string;
  interpretacion: string;
  supuestos: string[];
  advertencias: string[];
  referencia: string | null;
  /** Cómo se llama esto en los sistemas que la gente ya conoce. */
  equivalente: Record<string, string>;
}

export interface EsquemaParam {
  type?: string | string[];
  title?: string;
  description?: string;
  default?: unknown;
  enum?: string[];
  anyOf?: EsquemaParam[];
  items?: EsquemaParam;
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
  const?: string;
  /** Pista de interfaz que pone el backend: qué control dibujar. */
  abak?: {
    control: 'columna' | 'columnas' | 'opcion' | 'archivo' | 'mapa_sectores' | 'claves' | 'arcos';
    puerto?: string;
    tipo_columna?: string | null;
    etiquetas?: Record<string, string>;
    /** Claves frecuentes de una fuente oficial: atajos, no un catálogo cerrado. */
    sugerencias?: Record<string, string>;
  };
}

export interface DescriptorNodo {
  op: string;
  version: string;
  familia: string;
  titulo: string;
  terminal: boolean;
  ayuda: Ayuda;
  entradas: Puerto[];
  salidas: Puerto[];
  params_schema: {
    properties?: Record<string, EsquemaParam>;
    required?: string[];
    $defs?: Record<string, EsquemaParam>;
  };
}

export interface Familia {
  id: string;
  titulo: string;
  descripcion: string;
  color: string;
  orden: number;
  icono: string;
}

/** La ficha de un indicador: qué es, cómo se lee y con qué hay que tener cuidado. */
export interface Indicador {
  titulo: string;
  que_es: string;
  como_se_lee: string;
  ojo_con: string | null;
  referencia: string | null;
}

export type Glosario = Record<string, Indicador>;

export interface Catalogo {
  familias: Familia[];
  nodos: DescriptorNodo[];
  tipos: Record<string, { descripcion: string; padre: string | null; color: string }>;
}

export interface ColumnaEsquema {
  nombre: string;
  tipo: 'numerica' | 'categorica' | 'fecha' | 'booleana' | 'texto' | 'geometria';
  es_estimado: boolean;
  fuente: string | null;
  nota: string | null;
}

export interface Esquema {
  columnas: ColumnaEsquema[];
  indice_temporal: string | null;
  id_entidad: string | null;
  n_filas: number | null;
}

/** Lo que devuelve la subida de un archivo, ya convertido a columnar. */
export interface Subida {
  archivo_id: string;
  nombre: string;
  n_filas: number;
  n_columnas: number;
  bytes_origen: number;
  bytes_parquet: number;
  compresion: number;
  sha256: string;
  columnas: { nombre: string; tipo_arrow: string; faltantes: number }[];
  avisos: string[];
  vista_previa: Record<string, unknown>[];
}

export interface Diagnostico {
  severidad: 'error' | 'aviso' | 'info';
  codigo: string;
  mensaje: string;
  nodo_id: string | null;
  puerto: string | null;
  param: string | null;
  sugerencia: string | null;
}

export interface NodoGrafo {
  id: string;
  op: string;
  etiqueta: string | null;
  params: Record<string, unknown>;
  posicion: { x: number; y: number };
  notas?: string | null;
}

export interface AristaGrafo {
  id?: string | null;
  origen: string;
  puerto_origen: string;
  destino: string;
  puerto_destino: string;
}

export interface Grafo {
  version_esquema: '1';
  titulo: string;
  nodos: NodoGrafo[];
  aristas: AristaGrafo[];
  semilla: number;
}

export interface RespuestaValidacion {
  ok: boolean;
  diagnosticos: Diagnostico[];
  orden: string[];
  podados: string[];
  huella: string;
  esquemas: Record<string, Record<string, Esquema>>;
}

export interface RespuestaCodigo {
  ok: boolean;
  codigo: string | null;
  lineas?: number;
  imports?: string[];
  ayudantes?: string[];
  diagnosticos: Diagnostico[];
}

export type Artefacto =
  | { tipo: 'tabla'; titulo: string | null; columnas: { nombre: string; tipo: string; estimada: boolean }[]; filas: unknown[][]; n_filas: number; truncada: boolean }
  | { tipo: 'modelo'; titulo: string | null; coeficientes: Coeficiente[]; diagnosticos: Record<string, number | string>; texto: string | null; tipo_errores: string }
  | { tipo: 'figura'; titulo: string | null; figura: { data: unknown[]; layout: Record<string, unknown> } }
  | { tipo: 'escalar'; titulo: string | null; valor: unknown }
  | { tipo: 'detalle'; titulo: string | null; datos: Record<string, unknown> }
  | { tipo: 'objeto'; titulo: string | null; clase: string; texto: string };

export interface Coeficiente {
  variable: string;
  coeficiente: number | null;
  error_estandar: number | null;
  estadistico: number | null;
  p_valor: number | null;
  ic_bajo: number | null;
  ic_alto: number | null;
  estrellas: string;
}

export type EstadoNodo = 'en_cola' | 'corriendo' | 'listo' | 'cacheado' | 'error' | 'omitido';

export interface ResultadoNodo {
  estado: EstadoNodo;
  ms?: number;
  etiqueta?: string;
  op?: string;
  artefactos?: Record<string, Artefacto>;
  error?: {
    titulo: string; detalle: string; sugerencia: string | null;
    excepcion: string; traceback: string;
  } | null;
}

export interface Ejecucion {
  id: string;
  estado: 'en_cola' | 'corriendo' | 'listo' | 'error' | 'cancelado';
  creado: number;
  terminado?: number;
  ms_total: number | null;
  bitacora: string[];
  nodos: Record<string, ResultadoNodo>;
  diagnosticos?: Diagnostico[];
}


/** Una variable, vista entre TODAS las especificaciones que la incluyeron. */
export interface VariableEspecificada {
  variable: string;
  veces: number;
  minimo: number;
  maximo: number;
  mediana: number;
  veces_significativa: number;
  cambia_de_signo: boolean;
  actual: number | null;
  actual_es_extremo: boolean;
}

export interface ResumenEspecificaciones {
  resultado: string;
  n_especificaciones: number;
  desde?: number;
  variables: VariableEspecificada[];
}
