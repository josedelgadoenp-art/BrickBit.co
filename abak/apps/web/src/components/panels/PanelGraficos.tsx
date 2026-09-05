'use client';

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
            <h3 className="mb-2 text-[13px] text-crema">{f.etiqueta}</h3>
            <Grafica artefacto={f.artefacto as never} />
          </section>
        ))}
      </div>
    </div>
  );
}
