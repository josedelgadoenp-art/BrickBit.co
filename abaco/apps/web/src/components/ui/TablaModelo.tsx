'use client';

import { num, pValor } from '@/lib/formato';
import type { Artefacto } from '@/lib/tipos';

/** Los coeficientes de un modelo, en el formato en el que se publican. */
export default function TablaModelo({
  artefacto,
}: { artefacto: Extract<Artefacto, { tipo: 'modelo' }> }) {
  const { coeficientes, diagnosticos, titulo, tipo_errores } = artefacto;

  return (
    <div className="rounded border border-borde bg-superficie">
      <div className="flex items-baseline justify-between border-b border-borde px-3 py-2">
        <span className="text-[13px] text-crema">{titulo ?? 'Modelo'}</span>
        {tipo_errores && (
          <span className="text-[11px] text-tenue" title="Cómo se calcularon los errores estándar">
            errores {tipo_errores}
          </span>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="tabla-datos w-full text-[12px]">
          <thead>
            <tr className="text-tenue">
              <th>Variable</th>
              <th className="text-right">Coeficiente</th>
              <th className="text-right">Error est.</th>
              <th className="text-right">Estadístico</th>
              <th className="text-right">p</th>
              <th className="text-right">IC 95%</th>
            </tr>
          </thead>
          <tbody>
            {coeficientes.map((c) => (
              <tr key={c.variable}>
                <td className="text-crema">{c.variable}</td>
                <td className="text-right tabular-nums text-crema">
                  {num(c.coeficiente)}
                  <span className="ml-1 text-salvia">{c.estrellas}</span>
                </td>
                <td className="text-right tabular-nums text-tenue">{num(c.error_estandar)}</td>
                <td className="text-right tabular-nums text-tenue">{num(c.estadistico, 2)}</td>
                <td className="text-right tabular-nums text-tenue">{pValor(c.p_valor)}</td>
                <td className="text-right tabular-nums text-tenue/80">
                  {c.ic_bajo === null ? '—' : `[${num(c.ic_bajo, 3)}, ${num(c.ic_alto, 3)}]`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-1 border-t border-borde px-3 py-2 text-[11px] text-tenue">
        {Object.entries(diagnosticos).map(([k, v]) => (
          <span key={k}>{k}: <span className="text-crema">{typeof v === 'number' ? num(v, 3) : v}</span></span>
        ))}
      </div>
      <p className="border-t border-borde px-3 py-1.5 text-[11px] text-tenue">
        *** significativo al 1%, ** al 5%, * al 10%. Que un coeficiente sea significativo no lo
        vuelve grande: mira también su tamaño en las unidades del problema.
      </p>
    </div>
  );
}
