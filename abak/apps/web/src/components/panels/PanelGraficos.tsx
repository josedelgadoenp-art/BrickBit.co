'use client';

import BotonPdf from '@/components/ui/BotonPdf';
import Grafica from '@/components/ui/Grafica';
import { Vacio } from '@/components/panels/PanelResultados';
import { usarLienzo } from '@/store/lienzo';

export default function PanelGraficos() {
  const ejecucion = usarLienzo((s) => s.ejecucion);

  const figuras = Object.entries(ejecucion?.nodos ?? {}).flatMap(([id, r]) =>
    Object.entries(r.artefactos ?? {})
      .filter(([, a]) => a.tipo === 'figura')
      .map(([puerto, a]) => ({ id, puerto, etiqueta: r.etiqueta ?? id, artefacto: a })));

  if (!figuras.length) {
    return (
      <Vacio texto="Aún no hay gráficas. Arma una con el bloque «Lienzo», apila las capas que quieras (puntos, línea, banda) y termina con «Dibujar»." />
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
            <Grafica artefacto={f.artefacto as never} />
          </section>
        ))}
      </div>
    </div>
  );
}
