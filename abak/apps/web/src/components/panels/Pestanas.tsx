'use client';

import { useEffect } from 'react';

import Lienzo from '@/components/canvas/Lienzo';
import PanelBitacora from '@/components/panels/PanelBitacora';
import PanelCodigo from '@/components/panels/PanelCodigo';
import PanelDatos from '@/components/panels/PanelDatos';
import PanelGraficos from '@/components/panels/PanelGraficos';
import PanelMetodologia from '@/components/panels/PanelMetodologia';
import PanelResultados from '@/components/panels/PanelResultados';
import { usarLienzo, type Pestana } from '@/store/lienzo';

/**
 * Las pestañas del área de trabajo.
 *
 * Cada una responde a una pregunta distinta, y por eso están separadas en vez
 * de amontonadas en un panel: qué estoy armando (Lienzo), qué datos tengo
 * (Datos), qué salió (Resultados y Gráficos), qué código corrió (Código), cómo
 * lo cuento (Metodología) y qué pasó por dentro (Bitácora).
 */
const PESTANAS: { id: Pestana; texto: string; ayuda: string }[] = [
  { id: 'lienzo', texto: 'Lienzo', ayuda: 'Arma el análisis conectando bloques' },
  { id: 'datos', texto: 'Datos', ayuda: 'Las tablas en cada punto del análisis' },
  { id: 'resultados', texto: 'Resultados', ayuda: 'Modelos, pruebas y tablas' },
  { id: 'graficos', texto: 'Gráficos', ayuda: 'Las figuras que produjo el análisis' },
  { id: 'codigo', texto: 'Código', ayuda: 'El Python que se ejecuta. Es el mismo que exportas.' },
  { id: 'metodologia', texto: 'Metodología', ayuda: 'Qué se hizo, con qué supuestos y advertencias' },
  { id: 'bitacora', texto: 'Bitácora', ayuda: 'El detalle técnico, incluidos los errores completos' },
];

export default function Pestanas() {
  const pestana = usarLienzo((s) => s.pestana);
  const irA = usarLienzo((s) => s.irA);
  const pedirCodigo = usarLienzo((s) => s.pedirCodigo);
  const pedirMetodologia = usarLienzo((s) => s.pedirMetodologia);
  const nodos = usarLienzo((s) => s.nodos.length);
  const ejecucion = usarLienzo((s) => s.ejecucion);

  useEffect(() => {
    if (pestana === 'codigo' && nodos) pedirCodigo();
    if (pestana === 'metodologia' && nodos) pedirMetodologia();
  }, [pestana, nodos, pedirCodigo, pedirMetodologia]);

  const cuentaFiguras = Object.values(ejecucion?.nodos ?? {}).reduce(
    (n, r) => n + Object.values(r.artefactos ?? {}).filter((a) => a.tipo === 'figura').length, 0);

  return (
    <>
      <nav className="flex shrink-0 items-center gap-0.5 border-b border-borde bg-superficie px-2">
        {PESTANAS.map((p) => {
          const activa = p.id === pestana;
          return (
            <button
              key={p.id}
              onClick={() => irA(p.id)}
              title={p.ayuda}
              className={`border-b-2 px-3 py-2 text-[12px] transition-colors ${
                activa ? 'border-salvia text-crema' : 'border-transparent text-tenue hover:text-crema'
              }`}
            >
              {p.texto}
              {p.id === 'graficos' && cuentaFiguras > 0 && (
                <span className="ml-1.5 rounded bg-borde px-1 text-[10px] text-tenue">
                  {cuentaFiguras}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <div className="min-h-0 flex-1 overflow-hidden">
        {pestana === 'lienzo' && <Lienzo />}
        {pestana === 'datos' && <PanelDatos />}
        {pestana === 'resultados' && <PanelResultados />}
        {pestana === 'graficos' && <PanelGraficos />}
        {pestana === 'codigo' && <PanelCodigo />}
        {pestana === 'metodologia' && <PanelMetodologia />}
        {pestana === 'bitacora' && <PanelBitacora />}
      </div>
    </>
  );
}
