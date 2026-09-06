'use client';

import { useState } from 'react';

import { api, descargar, ErrorApi } from '@/lib/api';
import { usarLienzo } from '@/store/lienzo';

/**
 * Descarga en PDF los resultados de un bloque, o del análisis completo.
 *
 * Está donde está el resultado, no escondido en un menú: si alguien acaba de
 * ver una tabla que le sirve, el botón para llevársela tiene que estar ahí.
 */
export default function BotonPdf({
  nodo,
  etiqueta = 'PDF',
  completo = false,
}: { nodo?: string; etiqueta?: string; completo?: boolean }) {
  const ejecucion = usarLienzo((s) => s.ejecucion);
  const [estado, setEstado] = useState<'listo' | 'bajando' | 'error'>('listo');

  if (!ejecucion || ejecucion.estado !== 'listo') return null;

  async function bajar() {
    setEstado('bajando');
    try {
      await descargar(api.urlInforme(ejecucion!.id, completo ? {} : { nodo, codigo: false, metodologia: false }));
      setEstado('listo');
    } catch (e) {
      setEstado('error');
      // El detalle va a la consola: el botón sólo tiene espacio para el hecho.
      console.error(e instanceof ErrorApi ? e.mensaje : e);
      setTimeout(() => setEstado('listo'), 2500);
    }
  }

  return (
    <button
      onClick={bajar}
      disabled={estado === 'bajando'}
      title={completo
        ? 'Informe completo: portada, resultados, gráficas, metodología y el código'
        : 'Sólo los resultados de este bloque, en PDF'}
      className="rounded border border-borde px-2 py-0.5 text-[11px] text-tenue transition-colors hover:border-salvia hover:text-crema disabled:opacity-50"
    >
      {estado === 'bajando' ? 'Generando…' : estado === 'error' ? 'Falló' : etiqueta}
    </button>
  );
}
