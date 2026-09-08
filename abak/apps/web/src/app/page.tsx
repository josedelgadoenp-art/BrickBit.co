'use client';

import { useEffect } from 'react';

import BarraSuperior from '@/components/panels/BarraSuperior';
import Inspector from '@/components/panels/Inspector';
import Paleta from '@/components/panels/Paleta';
import Pestanas from '@/components/panels/Pestanas';
import { usarLienzo } from '@/store/lienzo';

export default function Pagina() {
  const cargarCatalogo = usarLienzo((s) => s.cargarCatalogo);
  const errorCatalogo = usarLienzo((s) => s.errorCatalogo);
  const pestana = usarLienzo((s) => s.pestana);
  const hayNodos = usarLienzo((s) => s.nodos.length > 0);
  const manual = usarLienzo((s) => s.manual);
  const revisarIA = usarLienzo((s) => s.revisarIA);

  useEffect(() => { cargarCatalogo(); revisarIA(); }, [cargarCatalogo, revisarIA]);

  // La paleta y el inspector sirven para ARMAR. Fuera del lienzo no hacen nada
  // y se llevaban 600 px de ancho: leer una tabla de regresión por una rendija
  // mientras dos columnas muestran herramientas que ahí no se pueden usar.
  const armando = pestana === 'lienzo' && (hayNodos || manual);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-tierra">
      <BarraSuperior />
      {errorCatalogo && (
        <div className="border-b border-terracota/40 bg-terracota/10 px-4 py-2 text-sm text-arcilla">
          {errorCatalogo}
        </div>
      )}
      <div className="flex min-h-0 flex-1">
        {armando && <Paleta />}
        <main className="flex min-w-0 flex-1 flex-col">
          <Pestanas />
        </main>
        {armando && <Inspector />}
      </div>
    </div>
  );
}
