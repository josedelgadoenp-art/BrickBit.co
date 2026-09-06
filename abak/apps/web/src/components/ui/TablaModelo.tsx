'use client';

import Explicacion from '@/components/ui/Explicacion';
import { esProbabilidad, num, pValor } from '@/lib/formato';
import type { Artefacto } from '@/lib/tipos';

const COLUMNAS: { clave: string; etiqueta: string; alinear: 'left' | 'right' }[] = [
  { clave: 'variable', etiqueta: 'Variable', alinear: 'left' },
  { clave: 'coeficiente', etiqueta: 'Coeficiente', alinear: 'right' },
  { clave: 'error_estandar', etiqueta: 'Error est.', alinear: 'right' },
  { clave: 'estadistico', etiqueta: 'Estadístico', alinear: 'right' },
  { clave: 'p_valor', etiqueta: 'p', alinear: 'right' },
  { clave: 'ic_95', etiqueta: 'IC 95%', alinear: 'right' },
];

/**
 * Los coeficientes de un modelo, en el formato en el que se publican.
 *
 * Cada encabezado trae su ventana de explicación: qué es ese número, cómo se
 * lee y qué error se comete con él. Es lo que permite que alguien que no es
 * econometrista sepa qué está viendo sin salir de la pantalla.
 */
export default function TablaModelo({
  artefacto,
}: { artefacto: Extract<Artefacto, { tipo: 'modelo' }> }) {
  const { coeficientes, diagnosticos, titulo, tipo_errores } = artefacto;

  return (
    <div className="rounded-lg border border-borde bg-superficie">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-borde px-4 py-2.5">
        <span className="text-[13px] font-medium text-crema">{titulo ?? 'Modelo'}</span>
        {tipo_errores && (
          <span className="text-[11px] text-tenue" title="Cómo se calcularon los errores estándar">
            errores {tipo_errores}
          </span>
        )}
        <span className="ml-auto text-[11px] text-tenue">
          {coeficientes.length} coeficiente{coeficientes.length === 1 ? '' : 's'}
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="tabla-datos w-full text-[12px]">
          <thead>
            <tr>
              {COLUMNAS.map((c) => (
                <th key={c.clave} className={c.alinear === 'right' ? 'text-right' : 'text-left'}>
                  <span className="inline-flex items-center whitespace-nowrap">
                    {c.etiqueta}
                    <Explicacion clave={c.clave} alineacion={c.alinear === 'right' ? 'derecha' : 'izquierda'} />
                  </span>
                </th>
              ))}
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

      {Object.keys(diagnosticos).length > 0 && (
        <div className="flex flex-wrap gap-x-5 gap-y-1.5 border-t border-borde px-4 py-2.5 text-[11px]">
          {Object.entries(diagnosticos).map(([k, v]) => (
            <span key={k} className="inline-flex items-center text-tenue">
              {k}:&nbsp;
              <span className="text-crema">
                {typeof v !== 'number' ? v : esProbabilidad(k) ? pValor(v) : num(v, 3)}
              </span>
              <Explicacion clave={k} />
            </span>
          ))}
        </div>
      )}

      <p className="border-t border-borde px-4 py-2 text-[11px] leading-relaxed text-tenue">
        *** significativo al 1%, ** al 5%, * al 10%. Que un coeficiente sea significativo no lo
        vuelve grande: mira también su tamaño en las unidades del problema.
      </p>
    </div>
  );
}
