'use client';

import { useMemo, useRef } from 'react';

import BotonPdf from '@/components/ui/BotonPdf';
import Explicacion from '@/components/ui/Explicacion';
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
        <div className="inline-flex items-center rounded-lg border border-borde bg-superficie px-4 py-2.5 text-[13px]">
          <span className="text-tenue">{artefacto.titulo}</span>
          <Explicacion clave={artefacto.titulo ?? ''} />
          <span className="ml-2 text-crema">{String(artefacto.valor)}</span>
        </div>
      );
    case 'detalle':
      return (
        <div className="rounded-lg border border-borde bg-superficie">
          <div className="border-b border-borde px-4 py-2.5 text-[13px] font-medium text-crema">
            {artefacto.titulo}
          </div>
          <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-6 gap-y-2 px-4 py-3 text-[12px]">
            {Object.entries(artefacto.datos).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="inline-flex items-start text-tenue">
                  <span className="leading-relaxed">{k.replace(/_/g, ' ')}</span>
                  <Explicacion clave={k} />
                </dt>
                <dd className="text-right leading-relaxed text-crema">
                  {typeof v === 'number' ? num(v) : String(v)}
                </dd>
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
  const secciones = useRef<Record<string, HTMLElement | null>>({});

  const ids = useMemo(
    () => (orden.length ? orden : Object.keys(ejecucion?.nodos ?? {})),
    [orden, ejecucion],
  );

  /**
   * Los pasos que de verdad enseñan algo, ya clasificados.
   *
   * `clase` separa lo que se estimó de lo que sólo preparó datos. Un análisis
   * real trae doce pasos y sólo dos o tres son el resultado; sin esa marca hay
   * que bajar leyendo tabla por tabla hasta dar con el modelo.
   */
  const pasos = useMemo(() => {
    if (!ejecucion) return [];
    return ids.flatMap((id) => {
      const r = ejecucion.nodos[id];
      if (!r) return [];
      const artefactos = Object.entries(r.artefactos ?? {}).filter(([, a]) => a.tipo !== 'figura');
      if (!artefactos.length && !r.error) return [];
      const clase: 'error' | 'modelo' | 'dato' = r.error
        ? 'error'
        : artefactos.some(([, a]) => a.tipo === 'modelo' || a.tipo === 'detalle')
          ? 'modelo'
          : 'dato';
      return [{ id, r, artefactos, clase }];
    });
  }, [ejecucion, ids]);

  if (!ejecucion) {
    return (
      <Vacio texto="Todavía no has ejecutado el análisis. Arma el lienzo y presiona Ejecutar." />
    );
  }

  const estimados = pasos.filter((x) => x.clase === 'modelo').length;
  const conError = pasos.filter((x) => x.clase === 'error').length;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl p-4">
        <div className="sticky top-0 z-20 -mx-4 mb-6 border-b border-borde bg-tierra/95 px-4 pb-3 pt-1 backdrop-blur">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <span className="text-[12px] text-tenue">
              {pasos.length} paso{pasos.length === 1 ? '' : 's'} con resultado
              {estimados > 0 && <> · {estimados} estimación{estimados === 1 ? '' : 'es'}</>}
              {conError > 0 && <span className="text-arcilla"> · {conError} con error</span>}
            </span>
            <div className="ml-auto">
              <BotonPdf completo etiqueta="Informe completo en PDF" />
            </div>
          </div>

          {pasos.length > 1 && (
            <nav aria-label="Ir a un resultado" className="mt-2 flex flex-wrap gap-1.5">
              {pasos.map(({ id, r, clase }) => (
                <button
                  key={id}
                  onClick={() => secciones.current[id]?.scrollIntoView({
                    behavior: 'smooth', block: 'start',
                  })}
                  title={r.etiqueta ?? id}
                  className={`max-w-[15rem] truncate rounded-full border px-2.5 py-1 text-[11px]
                              transition-colors ${
                    clase === 'error'
                      ? 'border-terracota/50 text-arcilla hover:bg-terracota/10'
                      : clase === 'modelo'
                        ? 'border-salvia/50 text-salvia hover:bg-salvia/10'
                        : 'border-borde text-tenue hover:border-salvia/50 hover:text-crema'
                  }`}
                >
                  {r.etiqueta ?? id}
                </button>
              ))}
            </nav>
          )}
        </div>

        <div className="space-y-6">
          {pasos.map(({ id, r, artefactos, clase }) => (
            <section
              key={id}
              ref={(el) => { secciones.current[id] = el; }}
              className="scroll-mt-24"
            >
              <div className="mb-2 flex items-baseline gap-2">
                <span
                  aria-hidden
                  className={`h-1.5 w-1.5 shrink-0 translate-y-[-2px] rounded-full ${
                    clase === 'error' ? 'bg-terracota'
                      : clase === 'modelo' ? 'bg-salvia' : 'bg-borde'
                  }`}
                />
                <button onClick={() => { seleccionar(id); irA('lienzo'); }}
                        title="Ver este bloque en el lienzo"
                        className="text-[14px] font-medium text-crema hover:text-salvia">
                  {r.etiqueta ?? id}
                </button>
                {r.ms !== undefined && <span className="text-[11px] text-tenue">{r.ms} ms</span>}
                <div className="ml-auto">
                  <BotonPdf nodo={id} />
                </div>
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
          ))}
        </div>
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
