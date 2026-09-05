'use client';

import { useState } from 'react';

import { Vacio } from '@/components/panels/PanelResultados';
import { duracion } from '@/lib/formato';
import { usarLienzo } from '@/store/lienzo';

/**
 * El detalle técnico completo.
 *
 * Traducir un error a español no es esconderlo: el economista lee el
 * diagnóstico en el bloque, y quien tenga que depurar lee el traceback aquí.
 */
export default function PanelBitacora() {
  const ejecucion = usarLienzo((s) => s.ejecucion);
  const diagnosticos = usarLienzo((s) => s.diagnosticos);
  const [abierto, setAbierto] = useState<string | null>(null);

  if (!ejecucion && !diagnosticos.length) {
    return <Vacio texto="Aquí queda el registro técnico de cada ejecución, con los errores completos." />;
  }

  const conError = Object.entries(ejecucion?.nodos ?? {}).filter(([, r]) => r.error);

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto max-w-4xl space-y-4">
        {ejecucion && (
          <div className="rounded border border-borde bg-superficie px-3 py-2 text-[12px]">
            <span className="text-tenue">Ejecución </span>
            <code className="font-mono text-crema">{ejecucion.id}</code>
            <span className="ml-3 text-tenue">estado: </span>
            <span className="text-crema">{ejecucion.estado}</span>
            {ejecucion.ms_total != null && (
              <span className="ml-3 text-tenue">total: {duracion(ejecucion.ms_total)}</span>
            )}
          </div>
        )}

        {diagnosticos.length > 0 && (
          <section>
            <h3 className="mb-2 text-[13px] text-crema">Revisión del lienzo</h3>
            <div className="space-y-1">
              {diagnosticos.map((d, i) => (
                <div key={i} className="rounded border border-borde bg-superficie px-3 py-1.5 text-[12px]">
                  <span className={d.severidad === 'error' ? 'text-arcilla' : 'text-ambar'}>
                    {d.severidad}
                  </span>
                  <code className="ml-2 font-mono text-[11px] text-tenue">{d.codigo}</code>
                  <span className="ml-2 text-crema/85">{d.mensaje}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {conError.length > 0 && (
          <section>
            <h3 className="mb-2 text-[13px] text-crema">Errores con su traza completa</h3>
            {conError.map(([id, r]) => (
              <div key={id} className="mb-2 rounded border border-terracota/40 bg-superficie">
                <button
                  onClick={() => setAbierto(abierto === id ? null : id)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left"
                >
                  <span className="text-[13px] text-arcilla">{r.etiqueta ?? id}</span>
                  <span className="text-[12px] text-tenue">{r.error!.titulo}</span>
                  <span className="ml-auto text-[11px] text-tenue">{abierto === id ? '−' : '+'}</span>
                </button>
                {abierto === id && (
                  <pre className="overflow-x-auto border-t border-borde bg-tierra p-3 font-mono text-[11px] leading-relaxed text-tenue">
                    {r.error!.traceback}
                  </pre>
                )}
              </div>
            ))}
          </section>
        )}

        {ejecucion?.bitacora?.length ? (
          <section>
            <h3 className="mb-2 text-[13px] text-crema">Registro</h3>
            <pre className="overflow-x-auto rounded border border-borde bg-superficie p-3 font-mono text-[11px] leading-relaxed text-tenue">
              {ejecucion.bitacora.join('\n')}
            </pre>
          </section>
        ) : null}
      </div>
    </div>
  );
}
