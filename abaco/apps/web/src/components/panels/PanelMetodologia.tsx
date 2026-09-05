'use client';

import { Vacio } from '@/components/panels/PanelResultados';
import { usarLienzo } from '@/store/lienzo';

/**
 * Un render mínimo de Markdown.
 *
 * Deliberadamente sin biblioteca: la nota metodológica la genera Ábaco con un
 * subconjunto conocido (títulos, listas, negritas, citas), así que traer un
 * parser completo sería cargar 40 KB para no usarlos.
 */
function Markdown({ texto }: { texto: string }) {
  const lineas = texto.split('\n');
  return (
    <div className="space-y-2">
      {lineas.map((linea, i) => {
        const negritas = (t: string) =>
          t.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g).map((parte, j) => {
            if (parte.startsWith('**')) return <strong key={j} className="text-crema">{parte.slice(2, -2)}</strong>;
            if (parte.startsWith('`')) return <code key={j} className="rounded bg-superficie2 px-1 font-mono text-[11px] text-salvia">{parte.slice(1, -1)}</code>;
            if (parte.startsWith('*') && parte.length > 2) return <em key={j} className="text-tenue">{parte.slice(1, -1)}</em>;
            return parte;
          });

        if (linea.startsWith('# ')) return <h1 key={i} className="pt-2 text-[18px] font-semibold text-crema">{linea.slice(2)}</h1>;
        if (linea.startsWith('## ')) return <h2 key={i} className="pt-4 text-[14px] font-medium text-salvia">{linea.slice(3)}</h2>;
        if (linea.startsWith('> ')) return <blockquote key={i} className="border-l-2 border-borde pl-3 text-[13px] text-tenue">{negritas(linea.slice(2))}</blockquote>;
        if (linea.startsWith('- ')) return <li key={i} className="ml-4 list-disc text-[13px] leading-relaxed text-crema/85">{negritas(linea.slice(2))}</li>;
        if (linea.startsWith('---')) return <hr key={i} className="border-borde" />;
        if (!linea.trim()) return <div key={i} className="h-1" />;
        return <p key={i} className="text-[13px] leading-relaxed text-crema/85">{negritas(linea)}</p>;
      })}
    </div>
  );
}

export default function PanelMetodologia() {
  const metodologia = usarLienzo((s) => s.metodologia);
  const nodos = usarLienzo((s) => s.nodos.length);

  if (!nodos) return <Vacio texto="La nota metodológica se escribe sola a partir del lienzo." />;
  if (!metodologia) return <Vacio texto="Preparando la nota metodológica…" />;

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-3xl">
        <div className="mb-4 rounded border border-borde bg-superficie px-3 py-2 text-[12px] text-tenue">
          Ábaco escribe esto a partir de tu lienzo: qué se hizo, con qué supuestos, con qué
          advertencias y qué columnas son estimaciones. Cópialo a tu documento y edítalo.
          <button
            onClick={() => navigator.clipboard.writeText(metodologia)}
            className="ml-2 text-salvia underline"
          >
            Copiar
          </button>
        </div>
        <Markdown texto={metodologia} />
      </div>
    </div>
  );
}
