'use client';

import { useState } from 'react';

import { EJEMPLOS } from '@/lib/ejemplos';
import { duracion } from '@/lib/formato';
import { usarLienzo } from '@/store/lienzo';

export default function BarraSuperior() {
  const {
    titulo, ponerTitulo, semilla, ponerSemilla, ejecutar, cancelar, ejecutando,
    ejecucion, validando, diagnosticos, nodos, limpiar, cargarGrafo, aGrafo, errorEjecucion,
  } = usarLienzo();
  const [abiertoEjemplos, setAbiertoEjemplos] = useState(false);

  const errores = diagnosticos.filter((d) => d.severidad === 'error').length;
  const puedeEjecutar = nodos.length > 0 && errores === 0 && !ejecutando;

  async function exportar() {
    const r = await fetch('/api/v1/grafos/exportar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ grafo: aGrafo() }),
    });
    if (!r.ok) return;
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${titulo.toLowerCase().replace(/\s+/g, '-').slice(0, 60)}.zip`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <header className="flex shrink-0 items-center gap-3 border-b border-borde bg-superficie px-4 py-2">
      <div className="flex items-center gap-2">
        <span className="text-[15px] font-semibold tracking-tight text-crema">Ábaco</span>
        <span className="hidden text-[11px] text-tenue lg:inline">
          análisis económico sin código
        </span>
      </div>

      <input
        value={titulo}
        onChange={(e) => ponerTitulo(e.target.value)}
        className="ml-2 min-w-0 flex-1 rounded border border-transparent bg-transparent px-2 py-1 text-[13px] text-crema hover:border-borde focus:border-salvia focus:outline-none"
        aria-label="Título del análisis"
      />

      <div className="relative">
        <button
          onClick={() => setAbiertoEjemplos((v) => !v)}
          className="rounded border border-borde px-2.5 py-1 text-[12px] text-tenue hover:text-crema"
        >
          Ejemplos ▾
        </button>
        {abiertoEjemplos && (
          <div className="absolute right-0 z-20 mt-1 w-80 rounded border border-borde bg-superficie shadow-panel">
            {EJEMPLOS.map((e) => (
              <button
                key={e.id}
                onClick={() => { cargarGrafo(e.grafo()); setAbiertoEjemplos(false); }}
                className="block w-full border-b border-borde/60 px-3 py-2 text-left last:border-0 hover:bg-superficie2"
              >
                <div className="text-[13px] text-crema">{e.titulo}</div>
                <div className="mt-0.5 text-[11px] leading-snug text-tenue">{e.descripcion}</div>
              </button>
            ))}
          </div>
        )}
      </div>

      <label className="flex items-center gap-1.5 text-[11px] text-tenue" title="Con la misma semilla y los mismos datos, el resultado se repite exactamente.">
        semilla
        <input
          type="number"
          value={semilla}
          onChange={(e) => ponerSemilla(Number(e.target.value) || 0)}
          className="w-16 rounded border border-borde bg-tierra px-1.5 py-0.5 text-[11px] text-crema focus:border-salvia focus:outline-none"
        />
      </label>

      <span className="text-[11px] text-tenue">
        {validando ? 'revisando…'
          : errores ? <span className="text-arcilla">{errores} problema{errores === 1 ? '' : 's'}</span>
          : nodos.length ? 'sin problemas' : ''}
      </span>

      <button onClick={limpiar} className="rounded border border-borde px-2.5 py-1 text-[12px] text-tenue hover:text-crema">
        Vaciar
      </button>
      <button onClick={exportar} disabled={!nodos.length}
              title="Descarga un .zip con el script de Python, sus datos y la nota metodológica"
              className="rounded border border-borde px-2.5 py-1 text-[12px] text-tenue hover:text-crema disabled:opacity-40">
        Exportar
      </button>

      {ejecutando ? (
        <button onClick={cancelar} className="rounded bg-terracota/85 px-3 py-1 text-[12px] font-medium text-tierra hover:bg-terracota">
          Detener
        </button>
      ) : (
        <button
          onClick={() => ejecutar()}
          disabled={!puedeEjecutar}
          title={errores ? 'Corrige los problemas marcados en rojo' : 'Ejecuta el análisis completo'}
          className="rounded bg-salvia px-3 py-1 text-[12px] font-medium text-tierra hover:bg-salviaProfunda disabled:cursor-not-allowed disabled:opacity-40"
        >
          Ejecutar
        </button>
      )}

      {ejecucion?.ms_total != null && !ejecutando && (
        <span className="text-[11px] text-tenue">{duracion(ejecucion.ms_total)}</span>
      )}
      {errorEjecucion && <span className="text-[11px] text-arcilla">{errorEjecucion}</span>}
    </header>
  );
}
