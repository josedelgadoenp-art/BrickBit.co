'use client';

import { RenderArtefacto, Vacio } from '@/components/panels/PanelResultados';
import BotonPdf from '@/components/ui/BotonPdf';
import { usarLienzo } from '@/store/lienzo';

export default function PanelGraficos() {
  const ejecucion = usarLienzo((s) => s.ejecucion);

  const figuras = Object.entries(ejecucion?.nodos ?? {}).flatMap(([id, r]) =>
    Object.entries(r.artefactos ?? {})
      .filter(([, a]) => a.tipo === 'figura' || a.tipo === 'proyeccion')
      .map(([puerto, a]) => ({ id, puerto, etiqueta: r.etiqueta ?? id, artefacto: a })));

  if (!figuras.length) {
    return (
      <Vacio texto="Aún no hay gráficas. Casi todo lo que estima dibuja la suya sola en cuanto ejecutas: coeficientes, ajuste, pronóstico. Y con el bloque «Lienzo» armas la que quieras a mano." />
    );
  }

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto max-w-5xl space-y-6">
        {figuras.map((f) => (
          <section key={`${f.id}-${f.puerto}`}>
            <div className="mb-2 flex items-center gap-2">
              <h3 className="text-[13px] text-crema">{f.etiqueta}</h3>
              <div className="ml-auto">
                <BotonPdf nodo={f.id} />
              </div>
            </div>
            <RenderArtefacto artefacto={f.artefacto} />
          </section>
        ))}
      </div>
    </div>
  );
}
