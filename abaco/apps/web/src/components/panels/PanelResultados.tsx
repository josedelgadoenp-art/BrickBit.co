'use client';

import Grafica from '@/components/ui/Grafica';
import Tabla from '@/components/ui/Tabla';
import TablaModelo from '@/components/ui/TablaModelo';
import { num } from '@/lib/formato';
import type { Artefacto } from '@/lib/tipos';
import { usarLienzo } from '@/store/lienzo';

export function RenderArtefacto({ artefacto }: { artefacto: Artefacto }) {
  switch (artefacto.tipo) {
    case 'tabla': return <Tabla artefacto={artefacto} />;
    case 'modelo': return <TablaModelo artefacto={artefacto} />;
    case 'figura': return <Grafica artefacto={artefacto} />;
    case 'escalar':
      return (
        <div className="rounded border border-borde bg-superficie px-3 py-2 text-[13px]">
          <span className="text-tenue">{artefacto.titulo}: </span>
          <span className="text-crema">{String(artefacto.valor)}</span>
        </div>
      );
    case 'detalle':
      return (
        <div className="rounded border border-borde bg-superficie">
          <div className="border-b border-borde px-3 py-2 text-[13px] text-crema">{artefacto.titulo}</div>
          <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 px-3 py-2 text-[12px]">
            {Object.entries(artefacto.datos).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-tenue">{k.replace(/_/g, ' ')}</dt>
                <dd className="text-right text-crema">{typeof v === 'number' ? num(v) : String(v)}</dd>
              </div>
            ))}
          </dl>
        </div>
      );
    default:
      return (
        <pre className="overflow-x-auto rounded border border-borde bg-superficie p-3 text-[11px] text-tenue">
          {artefacto.tipo === 'objeto' ? artefacto.texto : JSON.stringify(artefacto, null, 2)}
        </pre>
      );
  }
}

export default function PanelResultados() {
  const ejecucion = usarLienzo((s) => s.ejecucion);
  const orden = usarLienzo((s) => s.orden);
  const seleccionar = usarLienzo((s) => s.seleccionar);
  const irA = usarLienzo((s) => s.irA);

  if (!ejecucion) {
    return (
      <Vacio texto="Todavía no has ejecutado el análisis. Arma el lienzo y presiona Ejecutar." />
    );
  }

  const ids = orden.length ? orden : Object.keys(ejecucion.nodos);

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto max-w-5xl space-y-6">
        {ids.map((id) => {
          const r = ejecucion.nodos[id];
          if (!r) return null;
          const artefactos = Object.entries(r.artefactos ?? {}).filter(([, a]) => a.tipo !== 'figura');
          if (!artefactos.length && !r.error) return null;
          return (
            <section key={id}>
              <div className="mb-2 flex items-baseline gap-2">
                <button onClick={() => { seleccionar(id); irA('lienzo'); }}
                        className="text-[14px] font-medium text-crema hover:text-salvia">
                  {r.etiqueta ?? id}
                </button>
                {r.ms !== undefined && <span className="text-[11px] text-tenue">{r.ms} ms</span>}
              </div>
              {r.error && (
                <div className="rounded border border-terracota/40 bg-terracota/8 p-3">
                  <p className="text-[13px] font-medium text-arcilla">{r.error.titulo}</p>
                  <p className="mt-1 text-[12px] text-crema/85">{r.error.detalle}</p>
                  {r.error.sugerencia && (
                    <p className="mt-2 text-[12px] text-crema/75">{r.error.sugerencia}</p>
                  )}
                </div>
              )}
              <div className="space-y-3">
                {artefactos.map(([puerto, a]) => (
                  <RenderArtefacto key={puerto} artefacto={a} />
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

export function Vacio({ texto }: { texto: string }) {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <p className="max-w-md text-center text-[13px] leading-relaxed text-tenue">{texto}</p>
    </div>
  );
}
