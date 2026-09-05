/** Cliente de la API. Todo pasa por /api gracias al reescrito de Next. */

import type {
  Catalogo, Ejecucion, Esquema, Grafo, RespuestaCodigo, RespuestaValidacion,
} from './tipos';

const BASE = '/api/v1';

async function pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
  const respuesta = await fetch(`${BASE}${ruta}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  if (!respuesta.ok) {
    let detalle: unknown;
    try { detalle = await respuesta.json(); } catch { detalle = await respuesta.text(); }
    throw new ErrorApi(respuesta.status, detalle);
  }
  return respuesta.json() as Promise<T>;
}

export class ErrorApi extends Error {
  constructor(public estado: number, public detalle: unknown) {
    super(`La API respondió ${estado}`);
  }
  /** Mensaje en español listo para enseñar, sin códigos de estado crudos. */
  get mensaje(): string {
    const d = this.detalle as { detail?: { mensaje?: string } | string; detalle?: string };
    if (typeof d?.detail === 'string') return d.detail;
    if (d?.detail?.mensaje) return d.detail.mensaje;
    if (d?.detalle) return d.detalle;
    return this.estado === 0 ? 'No se pudo contactar al servidor.' : this.message;
  }
}

export const api = {
  catalogo: () => pedir<Catalogo>('/registro'),
  salud: () => pedir<{ ok: boolean; herramientas: number; modo_ejecucion: string }>('/salud'),

  validar: (grafo: Grafo) =>
    pedir<RespuestaValidacion>('/grafos/validar', {
      method: 'POST', body: JSON.stringify({ grafo }),
    }),

  codigo: (grafo: Grafo) =>
    pedir<RespuestaCodigo>('/grafos/codigo', {
      method: 'POST', body: JSON.stringify({ grafo }),
    }),

  metodologia: (grafo: Grafo) =>
    pedir<{ markdown: string }>('/grafos/metodologia', {
      method: 'POST', body: JSON.stringify({ grafo }),
    }),

  ejecutar: (grafo: Grafo, objetivo?: string) =>
    pedir<{ id: string; pasos: number; modo: string }>('/ejecuciones', {
      method: 'POST', body: JSON.stringify({ grafo, objetivo: objetivo ?? null }),
    }),

  ejecucion: (id: string) => pedir<Ejecucion>(`/ejecuciones/${id}`),

  cancelar: (id: string) =>
    pedir<{ ok: boolean }>(`/ejecuciones/${id}/cancelar`, { method: 'POST' }),

  async subir(archivo: File) {
    const cuerpo = new FormData();
    cuerpo.append('archivo', archivo);
    const r = await fetch(`${BASE}/datos/subir`, { method: 'POST', body: cuerpo });
    if (!r.ok) throw new ErrorApi(r.status, await r.json().catch(() => null));
    return r.json() as Promise<{
      archivo_id: string; nombre: string; bytes: number;
      esquema: Esquema; vista_previa: Record<string, unknown>[];
    }>;
  },

  /** La exportación es un .zip: se descarga, no se parsea. */
  urlExportar: () => `${BASE}/grafos/exportar`,
};
