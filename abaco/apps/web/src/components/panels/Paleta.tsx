'use client';

import { useMemo, useState } from 'react';

import { usarLienzo } from '@/store/lienzo';

/**
 * La paleta de herramientas.
 *
 * No está escrita aquí: se descarga de `GET /api/v1/registro`. Una herramienta
 * nueva en el backend aparece en esta lista sin tocar el frontend.
 *
 * Cada tarjeta lleva su nombre Y una línea de qué hace, porque el nombre solo
 * («SEM», «LISA», «VECM») no le dice nada a quien no es econometrista, y esa
 * persona es justo el usuario que este producto quiere ganar.
 */
export default function Paleta() {
  const catalogo = usarLienzo((s) => s.catalogo);
  const agregarNodo = usarLienzo((s) => s.agregarNodo);
  const [familiaActiva, setFamiliaActiva] = useState<string | null>(null);
  const [busqueda, setBusqueda] = useState('');

  const familias = catalogo?.familias ?? [];
  const activa = familiaActiva ?? familias[0]?.id ?? null;

  const visibles = useMemo(() => {
    const nodos = catalogo?.nodos ?? [];
    const q = busqueda.trim().toLowerCase();
    if (q) {
      return nodos.filter((n) =>
        n.titulo.toLowerCase().includes(q) ||
        n.ayuda.que_hace.toLowerCase().includes(q) ||
        n.ayuda.cuando_usarlo.toLowerCase().includes(q) ||
        Object.values(n.ayuda.equivalente).some((v) => v.toLowerCase().includes(q)));
    }
    return nodos.filter((n) => n.familia === activa);
  }, [catalogo, activa, busqueda]);

  const familiaActual = familias.find((f) => f.id === activa);

  return (
    <aside className="flex w-[292px] shrink-0 flex-col border-r border-borde bg-superficie">
      <div className="border-b border-borde p-3">
        <input
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Buscar herramienta…  (regresión, mapa, xtreg)"
          className="w-full rounded border border-borde bg-tierra px-2.5 py-1.5 text-[13px] text-crema placeholder:text-tenue/70 focus:border-salvia focus:outline-none"
        />
        {busqueda && (
          <p className="mt-1.5 text-[11px] text-tenue">
            {visibles.length} resultado{visibles.length === 1 ? '' : 's'}. También busca por el nombre
            del comando en Stata o R.
          </p>
        )}
      </div>

      {/* Pestañas de familia: dicen a qué área del análisis pertenece cada cosa. */}
      {!busqueda && (
        <nav className="flex flex-wrap gap-1 border-b border-borde p-2">
          {familias.map((f) => {
            const esActiva = f.id === activa;
            return (
              <button
                key={f.id}
                onClick={() => setFamiliaActiva(f.id)}
                title={f.descripcion}
                className={`rounded px-2 py-1 text-[11px] transition-colors ${
                  esActiva ? 'text-tierra' : 'text-tenue hover:text-crema'
                }`}
                style={esActiva ? { background: f.color } : { background: 'rgba(58,48,42,.5)' }}
              >
                {f.titulo}
              </button>
            );
          })}
        </nav>
      )}

      {!busqueda && familiaActual && (
        <p className="border-b border-borde px-3 py-2 text-[11px] leading-snug text-tenue">
          {familiaActual.descripcion}
        </p>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {visibles.map((n) => {
          const familia = familias.find((f) => f.id === n.familia);
          return (
            <button
              key={n.op}
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData('application/abaco-op', n.op);
                e.dataTransfer.effectAllowed = 'move';
              }}
              onClick={() => agregarNodo(n.op)}
              className="mb-1.5 w-full cursor-grab rounded border border-borde bg-tierra/60 p-2.5 text-left transition-colors hover:border-salvia/60 active:cursor-grabbing"
            >
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 shrink-0 rounded-sm"
                      style={{ background: familia?.color ?? '#6b6259' }} />
                <span className="truncate text-[13px] font-medium text-crema">{n.titulo}</span>
              </div>
              <p className="mt-1 line-clamp-2 text-[11px] leading-snug text-tenue">
                {n.ayuda.que_hace}
              </p>
              {n.ayuda.equivalente.stata && (
                <p className="mt-1 font-mono text-[10px] text-tenue/70">
                  Stata: {n.ayuda.equivalente.stata}
                </p>
              )}
            </button>
          );
        })}
        {visibles.length === 0 && (
          <p className="p-3 text-[12px] text-tenue">
            Nada coincide con «{busqueda}».
          </p>
        )}
      </div>

      <div className="border-t border-borde px-3 py-2 text-[11px] text-tenue">
        {catalogo ? `${catalogo.nodos.length} herramientas` : 'Cargando herramientas…'}
        <span className="ml-2 text-tenue/60">· arrastra o haz clic</span>
      </div>
    </aside>
  );
}
