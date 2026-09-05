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

  useEffect(() => { cargarCatalogo(); }, [cargarCatalogo]);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-tierra">
      <BarraSuperior />
      {errorCatalogo && (
        <div className="border-b border-terracota/40 bg-terracota/10 px-4 py-2 text-sm text-arcilla">
          {errorCatalogo}
        </div>
      )}
      <div className="flex min-h-0 flex-1">
        <Paleta />
        <main className="flex min-w-0 flex-1 flex-col">
          <Pestanas />
        </main>
        <Inspector />
      </div>
    </div>
  );
}
