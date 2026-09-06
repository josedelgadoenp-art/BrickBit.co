'use client';

import { useEffect, useRef } from 'react';

import type { Artefacto } from '@/lib/tipos';

/**
 * Una figura de Plotly.
 *
 * Se carga con `import()` dinámico porque Plotly pesa y no tiene por qué estar
 * en el paquete inicial: quien no grafica, no lo descarga.
 */
export default function Grafica({
  artefacto,
}: { artefacto: Extract<Artefacto, { tipo: 'figura' }> }) {
  const destino = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let vivo = true;
    let nodo: HTMLDivElement | null = null;

    (async () => {
      const Plotly = (await import('plotly.js-dist-min')).default;
      if (!vivo || !destino.current) return;
      nodo = destino.current;
      const { data, layout } = artefacto.figura;
      await Plotly.react(nodo, data as never, layout as never, {
        displaylogo: false,
        responsive: true,
        locale: 'es',
        modeBarButtonsToRemove: ['select2d', 'lasso2d'],
        toImageButtonOptions: { format: 'png', scale: 2, filename: 'abak' },
      });
    })();

    return () => {
      vivo = false;
      if (nodo) import('plotly.js-dist-min').then((m) => m.default.purge(nodo!));
    };
  }, [artefacto]);

  return <div ref={destino} className="h-[520px] w-full rounded border border-borde bg-superficie" />;
}
