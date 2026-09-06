'use client';

import Explicacion from '@/components/ui/Explicacion';
import { esProbabilidad, num, pValor } from '@/lib/formato';
import type { Artefacto } from '@/lib/tipos';

/**
 * Una tabla de resultados.
 *
 * Dos cosas que no son adorno: las columnas estimadas van en ámbar con el
 * sufijo «est.» —la marca viaja desde el compilador, así que no depende de que
 * nadie se acuerde—, y cada encabezado que Abak sabe explicar trae su ventana
 * con qué es y cómo se lee.
 */
export default function Tabla({ artefacto }: { artefacto: Extract<Artefacto, { tipo: 'tabla' }> }) {
  const { columnas, filas, n_filas, truncada, titulo } = artefacto;
  const hayEstimadas = columnas.some((c) => c.estimada);

  return (
    <div className="rounded-lg border border-borde bg-superficie">
      {titulo && (
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-b border-borde px-4 py-2.5">
          <span className="text-[13px] font-medium text-crema">{titulo}</span>
          <span className="text-[11px] text-tenue">
            {n_filas.toLocaleString('es-MX')} fila{n_filas === 1 ? '' : 's'} ·{' '}
            {columnas.length} columna{columnas.length === 1 ? '' : 's'}
            {truncada && ` · se muestran las primeras ${filas.length}`}
          </span>
        </div>
      )}

      <div className="max-h-[58vh] overflow-auto">
        <table className="tabla-datos w-full text-[12px]">
          <thead>
            <tr>
              {columnas.map((c) => (
                <th key={c.nombre} className={c.estimada ? 'estimado' : 'text-tenue'}>
                  <span className="inline-flex items-center whitespace-nowrap">
                    <span title={c.estimada ? 'Dato estimado: no es una medición' : undefined}>
                      {c.nombre}
                      {c.estimada && <span className="ml-1 text-[10px]">est.</span>}
                    </span>
                    <Explicacion clave={c.nombre} />
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filas.map((fila, i) => (
              <tr key={i}>
                {fila.map((celda, j) => (
                  <td
                    key={j}
                    className={`${columnas[j]?.estimada ? 'estimado' : 'text-crema/90'} ${
                      typeof celda === 'number' ? 'text-right tabular-nums' : ''
                    }`}
                  >
                    {typeof celda !== 'number' ? String(celda ?? '—')
                      : esProbabilidad(columnas[j]?.nombre ?? '') ? pValor(celda)
                      : num(celda)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {hayEstimadas && (
        <p className="border-t border-borde px-4 py-2 text-[11px] leading-relaxed text-ambar">
          En ámbar, lo estimado: son resultados de un modelo, no mediciones. Al citarlos fuera de
          Abak hay que decirlo.
        </p>
      )}
    </div>
  );
}
