'use client';

import { useState } from 'react';

import { Vacio } from '@/components/panels/PanelResultados';
import { usarLienzo } from '@/store/lienzo';

/**
 * El shadow code.
 *
 * Este panel es el argumento entero del producto: lo que se ve aquí no es un
 * código "equivalente" que alguien escribió para enseñar, es exactamente el
 * mismo árbol de sintaxis que se ejecuta. Por eso se actualiza mientras armas
 * el lienzo, sin haber corrido nada.
 */
export default function PanelCodigo() {
  const codigo = usarLienzo((s) => s.codigo);
  const nodos = usarLienzo((s) => s.nodos.length);
  const aGrafo = usarLienzo((s) => s.aGrafo);
  const titulo = usarLienzo((s) => s.titulo);
  const [copiado, setCopiado] = useState(false);

  if (!nodos) {
    return <Vacio texto="El código aparece aquí conforme armas el lienzo, antes de ejecutar nada." />;
  }
  if (!codigo) {
    return <Vacio texto="El análisis todavía tiene bloques sin configurar. Corrige lo marcado en rojo y el código aparecerá." />;
  }

  async function copiar() {
    await navigator.clipboard.writeText(codigo!);
    setCopiado(true);
    setTimeout(() => setCopiado(false), 1600);
  }

  async function descargar() {
    const r = await fetch('/api/v1/grafos/exportar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ grafo: aGrafo() }),
    });
    if (!r.ok) return;
    const url = URL.createObjectURL(await r.blob());
    const a = document.createElement('a');
    a.href = url;
    a.download = `${titulo.toLowerCase().replace(/\s+/g, '-').slice(0, 60)}.zip`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-center gap-3 border-b border-borde bg-superficie px-4 py-2">
        <p className="text-[12px] text-tenue">
          Este es el código que se ejecuta, no una reconstrucción.{' '}
          <span className="text-crema">{codigo.split('\n').length} líneas.</span>
        </p>
        <div className="ml-auto flex gap-2">
          <button onClick={copiar}
                  className="rounded border border-borde px-2.5 py-1 text-[12px] text-tenue hover:text-crema">
            {copiado ? 'Copiado' : 'Copiar'}
          </button>
          <button onClick={descargar}
                  title="Un .zip con el script, sus datos, la metodología y los requisitos"
                  className="rounded border border-borde px-2.5 py-1 text-[12px] text-tenue hover:text-crema">
            Descargar paquete
          </button>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto bg-tierra">
        <pre className="p-4 font-mono text-[12px] leading-relaxed text-crema/90">
          <code>{codigo}</code>
        </pre>
      </div>
    </div>
  );
}
