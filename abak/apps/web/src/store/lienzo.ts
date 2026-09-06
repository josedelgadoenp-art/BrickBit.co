/**
 * Estado del lienzo (Zustand).
 *
 * Una decisión importante: el estado guarda el grafo en el formato de React
 * Flow (que es lo que el lienzo necesita para dibujar) y lo traduce al contrato
 * `Grafo` sólo al hablar con el backend. Así, cambiar de biblioteca de lienzo
 * no toca ni la API ni el resto de la aplicación.
 *
 * La validación va con retardo (250 ms): se dispara en cada cambio y alimenta
 * los subrayados rojos y los desplegables de columnas, pero no en cada tecla.
 */

'use client';

import {
  addEdge, applyEdgeChanges, applyNodeChanges,
  type Connection, type Edge, type EdgeChange, type Node, type NodeChange,
} from '@xyflow/react';
import { create } from 'zustand';

import { api, ErrorApi } from '@/lib/api';
import type {
  Catalogo, DescriptorNodo, Diagnostico, Ejecucion, Esquema, Glosario, Grafo, Indicador,
  Puerto, ResultadoNodo,
} from '@/lib/tipos';

/** «R² ajustada» y «r2_ajustada» tienen que encontrar la misma ficha. */
function normalizarClave(clave: string): string {
  return clave
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/²/g, '2')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
}

export type Pestana = 'lienzo' | 'datos' | 'resultados' | 'graficos' | 'codigo' | 'metodologia' | 'bitacora';

export interface DatosNodo extends Record<string, unknown> {
  op: string;
  etiqueta: string;
  params: Record<string, unknown>;
  notas?: string | null;
}

export type NodoLienzo = Node<DatosNodo, 'abak'>;

interface Estado {
  // --- catálogo
  catalogo: Catalogo | null;
  glosario: Glosario;
  cargandoCatalogo: boolean;
  errorCatalogo: string | null;

  // --- documento
  titulo: string;
  semilla: number;
  nodos: NodoLienzo[];
  aristas: Edge[];
  seleccionado: string | null;

  // --- derivado del backend
  diagnosticos: Diagnostico[];
  esquemas: Record<string, Record<string, Esquema>>;
  orden: string[];
  podados: string[];
  codigo: string | null;
  validando: boolean;

  // --- ejecución
  ejecucion: Ejecucion | null;
  ejecutando: boolean;
  errorEjecucion: string | null;

  // --- interfaz
  pestana: Pestana;
  metodologia: string | null;

  // --- acciones
  cargarCatalogo: () => Promise<void>;
  descriptor: (op: string) => DescriptorNodo | undefined;
  /** La ficha de un indicador, o undefined si no hay. No se inventa nada. */
  indicador: (clave: string) => Indicador | undefined;
  agregarNodo: (op: string, posicion?: { x: number; y: number }) => void;
  duplicarNodo: (id: string) => void;
  borrarNodo: (id: string) => void;
  cambiarNodos: (cambios: NodeChange<NodoLienzo>[]) => void;
  cambiarAristas: (cambios: EdgeChange[]) => void;
  conectar: (conexion: Connection) => void;
  seleccionar: (id: string | null) => void;
  actualizarParams: (id: string, params: Record<string, unknown>) => void;
  renombrar: (id: string, etiqueta: string) => void;
  ponerNotas: (id: string, notas: string) => void;
  ponerTitulo: (titulo: string) => void;
  ponerSemilla: (semilla: number) => void;
  irA: (pestana: Pestana) => void;
  limpiar: () => void;
  cargarGrafo: (grafo: Grafo) => void;

  aGrafo: () => Grafo;
  validar: () => Promise<void>;
  pedirCodigo: () => Promise<void>;
  pedirMetodologia: () => Promise<void>;
  ejecutar: (objetivo?: string) => Promise<void>;
  cancelar: () => Promise<void>;

  // --- consultas de conveniencia
  esquemaDeEntrada: (nodoId: string, puerto: string) => Esquema | null;
  /**
   * Ojo: NO llamar desde un selector de Zustand. Devuelve un arreglo nuevo en
   * cada invocación y `useSyncExternalStore` compara por identidad, así que un
   * selector que lo use entra en bucle infinito. Se selecciona `diagnosticos`
   * y se filtra con `useMemo` en el componente.
   */
  diagnosticosDe: (nodoId: string) => Diagnostico[];
  resultadoDe: (nodoId: string) => ResultadoNodo | undefined;
}

let contador = 0;
const nuevoId = () => `n${++contador}_${Math.random().toString(36).slice(2, 6)}`;

let temporizador: ReturnType<typeof setTimeout> | null = null;
let sondeo: ReturnType<typeof setInterval> | null = null;

export const usarLienzo = create<Estado>((set, get) => ({
  catalogo: null,
  glosario: {},
  cargandoCatalogo: false,
  errorCatalogo: null,
  titulo: 'Análisis sin título',
  semilla: 42,
  nodos: [],
  aristas: [],
  seleccionado: null,
  diagnosticos: [],
  esquemas: {},
  orden: [],
  podados: [],
  codigo: null,
  validando: false,
  ejecucion: null,
  ejecutando: false,
  errorEjecucion: null,
  pestana: 'lienzo',
  metodologia: null,

  async cargarCatalogo() {
    if (get().catalogo || get().cargandoCatalogo) return;
    set({ cargandoCatalogo: true, errorCatalogo: null });
    try {
      // El glosario no es indispensable para trabajar: si falla, la aplicación
      // sigue y sólo se quedan sin explicación las fichas de los indicadores.
      const [catalogo, glosario] = await Promise.all([
        api.catalogo(),
        api.glosario().catch(() => ({})),
      ]);
      set({ catalogo, glosario, cargandoCatalogo: false });
    } catch (e) {
      set({
        cargandoCatalogo: false,
        errorCatalogo: e instanceof ErrorApi ? e.mensaje
          : 'No se pudo cargar el catálogo de herramientas. ¿Está corriendo la API en el puerto 8000?',
      });
    }
  },

  descriptor: (op) => get().catalogo?.nodos.find((n) => n.op === op),

  indicador: (clave) => get().glosario[normalizarClave(clave)],

  agregarNodo(op, posicion) {
    const d = get().descriptor(op);
    if (!d) return;
    // Valores por omisión del esquema: el nodo nace configurado, no vacío.
    const params: Record<string, unknown> = {};
    for (const [clave, campo] of Object.entries(d.params_schema.properties ?? {})) {
      if (campo.default !== undefined) params[clave] = campo.default;
    }

    // Se busca de dónde colgarlo ANTES de colocarlo, para ponerlo a la derecha
    // de su fuente y que el análisis se lea de izquierda a derecha.
    const enlace = posicion ? null : buscarFuente(get(), d);
    const origen = enlace ? get().nodos.find((n) => n.id === enlace.nodoId) : undefined;

    const nodo: NodoLienzo = {
      id: nuevoId(),
      type: 'abak',
      position: posicion
        ?? (origen
          ? { x: origen.position.x + 330, y: origen.position.y }
          : { x: 120 + get().nodos.length * 40, y: 80 + get().nodos.length * 70 }),
      data: { op, etiqueta: d.titulo, params },
    };

    set((s) => ({
      nodos: [...s.nodos, nodo],
      // Conectarlo solo. Antes el bloque caía suelto y había que arrastrar un
      // hilo entre dos puntos de seis píxeles para que sirviera de algo; quien
      // no descubría ese gesto veía «Ejecutar» apagado y se quedaba sin saber
      // si la herramienta estaba rota o si él no sabía usarla.
      aristas: enlace
        ? addEdge({
            source: enlace.nodoId, sourceHandle: enlace.salida,
            target: nodo.id, targetHandle: enlace.entrada,
            type: 'smoothstep',
          }, s.aristas)
        : s.aristas,
      seleccionado: nodo.id,
    }));
    get().validar();
  },

  duplicarNodo(id) {
    const original = get().nodos.find((n) => n.id === id);
    if (!original) return;
    const copia: NodoLienzo = {
      ...original,
      id: nuevoId(),
      position: { x: original.position.x + 40, y: original.position.y + 40 },
      data: { ...original.data, params: { ...original.data.params } },
      selected: false,
    };
    set((s) => ({ nodos: [...s.nodos, copia], seleccionado: copia.id }));
    get().validar();
  },

  borrarNodo(id) {
    set((s) => ({
      nodos: s.nodos.filter((n) => n.id !== id),
      aristas: s.aristas.filter((a) => a.source !== id && a.target !== id),
      seleccionado: s.seleccionado === id ? null : s.seleccionado,
    }));
    get().validar();
  },

  cambiarNodos(cambios) {
    set((s) => ({ nodos: applyNodeChanges(cambios, s.nodos) }));
    // Mover un nodo no cambia el análisis: sólo se revalida si hubo algo más.
    if (cambios.some((c) => c.type !== 'position' && c.type !== 'select' && c.type !== 'dimensions')) {
      get().validar();
    }
  },

  cambiarAristas(cambios) {
    set((s) => ({ aristas: applyEdgeChanges(cambios, s.aristas) }));
    get().validar();
  },

  conectar(conexion) {
    set((s) => ({ aristas: addEdge({ ...conexion, type: 'smoothstep' }, s.aristas) }));
    get().validar();
  },

  seleccionar: (id) => set({ seleccionado: id }),

  actualizarParams(id, params) {
    set((s) => ({
      nodos: s.nodos.map((n) =>
        n.id === id ? { ...n, data: { ...n.data, params: { ...n.data.params, ...params } } } : n),
    }));
    get().validar();
  },

  renombrar(id, etiqueta) {
    set((s) => ({
      nodos: s.nodos.map((n) => (n.id === id ? { ...n, data: { ...n.data, etiqueta } } : n)),
    }));
    get().validar();
  },

  ponerNotas(id, notas) {
    set((s) => ({
      nodos: s.nodos.map((n) => (n.id === id ? { ...n, data: { ...n.data, notas } } : n)),
    }));
  },

  ponerTitulo: (titulo) => set({ titulo }),
  ponerSemilla: (semilla) => set({ semilla }),
  irA: (pestana) => set({ pestana }),

  limpiar: () => set({
    nodos: [], aristas: [], seleccionado: null, diagnosticos: [], esquemas: {},
    codigo: null, ejecucion: null, metodologia: null, orden: [], podados: [],
  }),

  cargarGrafo(grafo) {
    set({
      titulo: grafo.titulo,
      semilla: grafo.semilla,
      nodos: grafo.nodos.map((n) => ({
        id: n.id, type: 'abak' as const, position: n.posicion,
        data: { op: n.op, etiqueta: n.etiqueta ?? '', params: n.params, notas: n.notas },
      })),
      aristas: grafo.aristas.map((a, i) => ({
        id: a.id ?? `a${i}`, source: a.origen, sourceHandle: a.puerto_origen,
        target: a.destino, targetHandle: a.puerto_destino, type: 'smoothstep',
      })),
      seleccionado: null, ejecucion: null, codigo: null, metodologia: null,
    });
    get().validar();
  },

  aGrafo() {
    const s = get();
    return {
      version_esquema: '1',
      titulo: s.titulo,
      semilla: s.semilla,
      nodos: s.nodos.map((n) => ({
        id: n.id, op: n.data.op, etiqueta: n.data.etiqueta || null,
        params: n.data.params, posicion: { x: n.position.x, y: n.position.y },
        notas: n.data.notas ?? null,
      })),
      aristas: s.aristas.map((a) => ({
        id: a.id, origen: a.source, puerto_origen: a.sourceHandle ?? 'salida',
        destino: a.target, puerto_destino: a.targetHandle ?? 'entrada',
      })),
    };
  },

  async validar() {
    if (temporizador) clearTimeout(temporizador);
    temporizador = setTimeout(async () => {
      if (get().nodos.length === 0) {
        set({ diagnosticos: [], esquemas: {}, codigo: null, orden: [], podados: [] });
        return;
      }
      set({ validando: true });
      try {
        const r = await api.validar(get().aGrafo());
        set({
          diagnosticos: r.diagnosticos, esquemas: r.esquemas,
          orden: r.orden, podados: r.podados, validando: false,
        });
        if (get().pestana === 'codigo') get().pedirCodigo();
      } catch {
        set({ validando: false });
      }
    }, 250);
  },

  async pedirCodigo() {
    try {
      const r = await api.codigo(get().aGrafo());
      set({ codigo: r.codigo });
    } catch {
      set({ codigo: null });
    }
  },

  async pedirMetodologia() {
    try {
      set({ metodologia: (await api.metodologia(get().aGrafo())).markdown });
    } catch (e) {
      set({ metodologia: e instanceof ErrorApi ? `_${e.mensaje}_` : null });
    }
  },

  async ejecutar(objetivo) {
    if (get().ejecutando) return;
    set({ ejecutando: true, errorEjecucion: null });
    try {
      const { id } = await api.ejecutar(get().aGrafo(), objetivo);
      if (sondeo) clearInterval(sondeo);
      const consultar = async () => {
        try {
          const e = await api.ejecucion(id);
          set({ ejecucion: e });
          if (e.estado === 'listo' || e.estado === 'error' || e.estado === 'cancelado') {
            if (sondeo) clearInterval(sondeo);
            sondeo = null;
            set({ ejecutando: false });
            // Si algo produjo una figura, la pestaña de gráficos es lo que
            // el usuario quiere ver; si no, los resultados.
            const hayFigura = Object.values(e.nodos).some((n) =>
              Object.values(n.artefactos ?? {}).some((a) => a.tipo === 'figura'));
            if (get().pestana === 'lienzo') set({ pestana: hayFigura ? 'graficos' : 'resultados' });
          }
        } catch { /* la siguiente vuelta reintenta */ }
      };
      await consultar();
      if (get().ejecutando) sondeo = setInterval(consultar, 700);
    } catch (e) {
      set({
        ejecutando: false,
        errorEjecucion: e instanceof ErrorApi ? e.mensaje : 'No se pudo ejecutar el análisis.',
      });
    }
  },

  async cancelar() {
    const id = get().ejecucion?.id;
    if (!id) return;
    try { await api.cancelar(id); } catch { /* ya había terminado */ }
  },

  esquemaDeEntrada(nodoId, puerto) {
    const s = get();
    const arista = s.aristas.find((a) => a.target === nodoId && (a.targetHandle ?? 'entrada') === puerto);
    if (!arista) return null;
    return s.esquemas[arista.source]?.[arista.sourceHandle ?? 'salida'] ?? null;
  },

  diagnosticosDe: (nodoId) => get().diagnosticos.filter((d) => d.nodo_id === nodoId),
  resultadoDe: (nodoId) => get().ejecucion?.nodos?.[nodoId],
}));


/**
 * ¿Un dato de tipo `origen` sirve donde se pide `destino`?
 *
 * Los tipos forman una jerarquía: `serie`, `panel` y `geotabla` son casos
 * particulares de `tabla`, así que encajan donde se pide una tabla. El catálogo
 * trae esa jerarquía en `tipos[x].padre` y aquí se sube por ella.
 */
function aceptaTipo(
  origen: string,
  destino: string,
  tipos: Record<string, { padre: string | null }>,
): boolean {
  if (destino === 'cualquiera' || origen === destino) return true;
  let actual: string | null = origen;
  const vistos = new Set<string>();
  while (actual && !vistos.has(actual)) {
    if (actual === destino) return true;
    vistos.add(actual);
    actual = tipos[actual]?.padre ?? null;
  }
  return false;
}

/**
 * De dónde colgar un bloque recién agregado.
 *
 * Se prefiere el bloque seleccionado —es lo que la persona estaba mirando— y
 * si no encaja, el más reciente que sí. Sólo se ocupa la PRIMERA entrada
 * obligatoria: un nodo que junta dos tablas se conecta a una y deja la otra a
 * la vista, que es la decisión que sí hay que tomar a mano.
 */
function buscarFuente(
  estado: Estado,
  destino: DescriptorNodo,
): { nodoId: string; salida: string; entrada: string } | null {
  const entrada = destino.entradas.find((e) => e.requerido) ?? destino.entradas[0];
  if (!entrada) return null;
  const tipos = estado.catalogo?.tipos ?? {};

  const candidatos = [
    ...(estado.seleccionado ? [estado.seleccionado] : []),
    ...[...estado.nodos].reverse().map((n) => n.id),
  ];
  for (const nodoId of candidatos) {
    const nodo = estado.nodos.find((n: NodoLienzo) => n.id === nodoId);
    if (!nodo) continue;
    const fuente = estado.catalogo?.nodos.find((x: DescriptorNodo) => x.op === nodo.data.op);
    if (!fuente) continue;
    const salida = fuente.salidas.find((sa: Puerto) => aceptaTipo(sa.tipo, entrada.tipo, tipos));
    if (salida) return { nodoId, salida: salida.nombre, entrada: entrada.nombre };
  }
  return null;
}
