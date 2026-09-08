'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

import { num } from '@/lib/formato';
import type { Artefacto } from '@/lib/tipos';

type Datos = Extract<Artefacto, { tipo: 'proyeccion' }>;

/**
 * Una proyección que se mueve con un control.
 *
 * El deslizador **no calcula nada**. Todas las curvas llegaron ya estimadas por
 * el motor, están en la tabla de al lado, en el script exportado y en el
 * informe; el control sólo escoge cuál se resalta. Si el navegador estimara,
 * sería un modelo en la sombra: nadie podría auditarlo, exportarlo ni citarlo,
 * y el número que se ve en pantalla no coincidiría con el del PDF.
 *
 * Las curvas que no están seleccionadas se dibujan tenues en vez de esconderse.
 * Ver el abanico entero es la mitad del argumento: dice de un vistazo cuánto
 * mueve la variable del control, que es justo lo que un coeficiente aislado no
 * deja ver.
 */
export default function Proyeccion({ artefacto }: { artefacto: Datos }) {
  const destino = useRef<HTMLDivElement>(null);
  const [i, setI] = useState(0);

  const series = artefacto.series ?? [];
  const control = artefacto.control;
  const seleccion = Math.min(i, Math.max(series.length - 1, 0));

  const trazos = useMemo(() => {
    const x = artefacto.x?.valores ?? [];
    const AMBAR = '#F5C277';
    const salida: Record<string, unknown>[] = [];

    // Primero las tenues, para que la seleccionada quede encima.
    series.forEach((s, k) => {
      if (k === seleccion) return;
      salida.push({
        x, y: s.y, mode: 'lines', type: 'scatter', hoverinfo: 'skip',
        line: { color: 'rgba(245,194,119,.22)', width: 1.2 },
        name: control && s.escenario !== null
          ? `${control.nombre} = ${num(s.escenario)}` : 'escenario',
        showlegend: false,
      });
    });

    const s = series[seleccion];
    if (s) {
      salida.push({
        x: [...x, ...[...x].reverse()],
        y: [...s.alto, ...[...s.bajo].reverse()],
        fill: 'toself', fillcolor: 'rgba(245,194,119,.16)',
        line: { width: 0 }, type: 'scatter', hoverinfo: 'skip',
        name: 'Banda 95%', showlegend: false,
      });
      salida.push({
        x, y: s.y, mode: 'lines', type: 'scatter',
        line: { color: AMBAR, width: 2.4 },
        name: 'Proyección (est.)',
        hovertemplate: `${artefacto.x?.nombre} %{x:.4g}<br>${artefacto.respuesta} %{y:.4g}<extra></extra>`,
        showlegend: false,
      });
    }
    return salida;
  }, [artefacto, series, seleccion, control]);

  useEffect(() => {
    let vivo = true;
    let nodo: HTMLDivElement | null = null;
    (async () => {
      const Plotly = (await import('plotly.js-dist-min')).default;
      if (!vivo || !destino.current) return;
      nodo = destino.current;
      await Plotly.react(nodo, trazos as never, {
        height: 360,
        margin: { l: 62, r: 22, t: 16, b: 46 },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { family: 'Geist, ui-sans-serif, system-ui, sans-serif', size: 11, color: '#8f8880' },
        xaxis: { title: { text: artefacto.x?.nombre }, gridcolor: 'rgba(143,136,128,.20)',
                 zeroline: false, linecolor: 'rgba(143,136,128,.20)' },
        yaxis: { title: { text: artefacto.respuesta }, gridcolor: 'rgba(143,136,128,.20)',
                 zeroline: false, linecolor: 'rgba(143,136,128,.20)' },
        showlegend: false,
      } as never, {
        displaylogo: false, responsive: true, locale: 'es',
        modeBarButtonsToRemove: ['select2d', 'lasso2d'],
      });
    })();
    return () => {
      vivo = false;
      if (nodo) import('plotly.js-dist-min').then((m) => m.default.purge(nodo!));
    };
  }, [trazos, artefacto]);

  const actual = series[seleccion];
  const valorControl = control?.valores?.[seleccion];

  return (
    <div className="rounded-xl2 border border-borde bg-superficie">
      {artefacto.titulo && (
        <div className="border-b border-borde px-4 py-2.5 text-[13px] font-medium text-crema">
          {artefacto.titulo}
        </div>
      )}
      <div className="px-2 pt-2">
        <div ref={destino} data-abak="proyeccion" className="h-[360px] w-full" />
      </div>

      {control && series.length > 1 && (
        <div className="border-t border-borde px-4 py-3">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-[12px] text-tenue">{control.nombre}</span>
            <span className="font-mono text-[14px] text-ambar">
              {valorControl !== undefined ? num(valorControl) : '—'}
            </span>
            <span className="ml-auto text-[11px] text-tenue">
              escenario {seleccion + 1} de {series.length}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={series.length - 1}
            step={1}
            value={seleccion}
            onChange={(e) => setI(Number(e.target.value))}
            aria-label={`Escenario de ${control.nombre}`}
            className="mt-2 w-full accent-[#F5C277]"
          />
          <div className="mt-1 flex justify-between text-[10px] text-tenue">
            <span>{num(control.valores[0])}</span>
            <span>{num(control.valores[control.valores.length - 1])}</span>
          </div>
        </div>
      )}

      <p className="border-t border-borde px-4 py-2 text-[11px] leading-relaxed text-tenue">
        {artefacto.nota ?? 'Todo lo dibujado es estimación del modelo.'}
        {actual && (
          <> Cada punto de cada curva está en la tabla que la acompaña y en el script exportado:
          el control elige cuál se enseña, no la calcula.</>
        )}
      </p>
    </div>
  );
}
