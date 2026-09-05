'use client';

import { num } from '@/lib/formato';
import type { Artefacto } from '@/lib/tipos';

/**
 * Una tabla de resultados.
 *
 * Las columnas marcadas como estimadas se pintan en ámbar. Esa marca viaja
 * desde el compilador —que la propaga por todo el grafo— hasta aquí, así que no
 * depende de que nadie se acuerde de ponerla.
 */
export default function Tabla({ artefacto }: { artefacto: Extract<Artefacto, { tipo: 'tabla' }> }) {
  const { columnas, filas, n_filas, truncada, titulo } = artefacto;
  const hayEstimadas = columnas.some((c) => c.estimada);

  return (
    <div className="rounded border border-borde bg-superficie">
      {titulo && (
        <div className="flex items-baseline justify-between border-b border-borde px-3 py-2">
          <span className="text-[13px] text-crema">{titulo}</span>
          <span className="text-[11px] text-tenue">
            {n_filas.toLocaleString('es-MX')} fila{n_filas === 1 ? '' : 's'}
            {truncada && ` · se muestran las primeras ${filas.length}`}
          </span>
        </div>
      )}
      <div className="max-h-[62vh] overflow-auto">
        <table className="tabla-datos w-full text-[12px]">
          <thead>
            <tr>
              {columnas.map((c) => (
                <th key={c.nombre}
                    className={c.estimada ? 'estimado' : 'text-tenue'}
                    title={c.estimada ? 'Dato estimado: no es una medición' : undefined}>
                  {c.nombre}{c.estimada ? ' ·est.' : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filas.map((fila, i) => (
              <tr key={i}>
                {fila.map((celda, j) => (
                  <td key={j}
                      className={`${columnas[j]?.estimada ? 'estimado' : 'text-crema/90'} ${
                        typeof celda === 'number' ? 'text-right tabular-nums' : ''
                      }`}>
                    {typeof celda === 'number' ? num(celda) : String(celda ?? '—')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {hayEstimadas && (
        <p className="border-t border-borde px-3 py-1.5 text-[11px] text-ambar">
          En ámbar, lo estimado: son resultados de un modelo, no mediciones. Al citarlos fuera de
          Ábaco hay que decirlo.
        </p>
      )}
    </div>
  );
}
