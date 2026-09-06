/** Cliente de la API. Todo pasa por /api gracias al reescrito de Next. */

import type {
  Catalogo, Ejecucion, Esquema, Glosario, Grafo, RespuestaCodigo, RespuestaValidacion,
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
  glosario: () => pedir<Glosario>('/glosario'),
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

  /** El informe en PDF de una ejecución, completo o de un solo bloque. */
  urlInforme: (ejecucionId: string, opciones?: { nodo?: string; codigo?: boolean; metodologia?: boolean }) => {
    const q = new URLSearchParams();
    if (opciones?.nodo) q.set('nodo', opciones.nodo);
    if (opciones?.codigo === false) q.set('codigo', 'false');
    if (opciones?.metodologia === false) q.set('metodologia', 'false');
    const cola = q.toString();
    return `${BASE}/ejecuciones/${ejecucionId}/informe${cola ? `?${cola}` : ''}`;
  },
};

/**
 * Descarga un archivo que devuelve la API.
 *
 * Se hace con fetch y no con un `<a href>` porque así se puede distinguir un
 * error del servidor de una descarga vacía: con un enlace directo, un 409
 * termina en una pestaña con un JSON de error, que no le dice nada a nadie.
 * El nombre lo pone el servidor en Content-Disposition.
 */
export async function descargar(
  url: string,
  opciones?: { metodo?: 'GET' | 'POST'; cuerpo?: unknown; nombrePorOmision?: string },
): Promise<void> {
  const respuesta = await fetch(url, {
    method: opciones?.metodo ?? 'GET',
    headers: opciones?.cuerpo ? { 'Content-Type': 'application/json' } : undefined,
    body: opciones?.cuerpo ? JSON.stringify(opciones.cuerpo) : undefined,
  });
  if (!respuesta.ok) {
    let detalle: unknown;
    try { detalle = await respuesta.json(); } catch { detalle = null; }
    throw new ErrorApi(respuesta.status, detalle);
  }

  const cabecera = respuesta.headers.get('content-disposition') ?? '';
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(cabecera)?.[1];
  const simple = /filename="([^"]+)"/i.exec(cabecera)?.[1];
  const nombre = utf8 ? decodeURIComponent(utf8) : simple ?? opciones?.nombrePorOmision ?? 'abak';

  const objeto = URL.createObjectURL(await respuesta.blob());
  const enlace = document.createElement('a');
  enlace.href = objeto;
  enlace.download = nombre;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  URL.revokeObjectURL(objeto);
}
