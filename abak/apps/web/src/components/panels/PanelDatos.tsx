'use client';

import { useState } from 'react';

import { Vacio } from '@/components/panels/PanelResultados';
import Tabla from '@/components/ui/Tabla';
import { usarLienzo } from '@/store/lienzo';

/** Las tablas tal como quedan en cada punto del análisis, no sólo al final. */
export default function PanelDatos() {
  const ejecucion = usarLienzo((s) => s.ejecucion);
  const orden = usarLienzo((s) => s.orden);
  const [activo, setActivo] = useState<string | null>(null);

  const conTabla = (orden.length ? orden : Object.keys(ejecucion?.nodos ?? {}))
    .map((id) => ({ id, r: ejecucion?.nodos[id] }))
    .filter(({ r }) => r && Object.values(r.artefactos ?? {}).some((a) => a.tipo === 'tabla'));

  if (!conTabla.length) {
    return <Vacio texto="Ejecuta el análisis para ver cómo queda la tabla en cada paso." />;
  }

  const elegido = activo && conTabla.some((c) => c.id === activo) ? activo : conTabla[0].id;
  const resultado = ejecucion!.nodos[elegido];
  const tablas = Object.entries(resultado.artefactos ?? {}).filter(([, a]) => a.tipo === 'tabla');

  return (
    <div className="flex h-full">
      <nav className="w-60 shrink-0 overflow-y-auto border-r border-borde bg-superficie p-2">
        {conTabla.map(({ id, r }) => (
          <button
            key={id}
            onClick={() => setActivo(id)}
            className={`mb-1 block w-full rounded px-2 py-1.5 text-left text-[12px] leading-snug ${
              id === elegido ? 'bg-superficie2 text-crema' : 'text-tenue hover:text-crema'
            }`}
          >
            {r!.etiqueta ?? id}
          </button>
        ))}
      </nav>
      <div className="min-w-0 flex-1 overflow-y-auto p-4">
        <div className="space-y-4">
          {tablas.map(([puerto, a]) => (
            <Tabla key={puerto} artefacto={a as never} />
          ))}
        </div>
      </div>
    </div>
  );
}
