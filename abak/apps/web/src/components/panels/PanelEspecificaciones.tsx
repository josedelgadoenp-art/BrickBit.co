'use client';

import { useCallback, useEffect, useState } from 'react';

import { Vacio } from '@/components/panels/PanelResultados';
import { api } from '@/lib/api';
import { num } from '@/lib/formato';
import type { ResumenEspecificaciones, VariableEspecificada } from '@/lib/tipos';
import { usarLienzo } from '@/store/lienzo';

/**
 * Cuántos modelos probaste antes de reportar uno.
 *
 * Es el fraude involuntario más extendido de la economía aplicada: alguien
 * prueba veinte especificaciones y publica la que «funcionó». Nadie miente;
 * nadie cuenta. Con veinte intentos, un p-valor por debajo de 0.05 es lo
 * esperable aunque no haya nada.
 *
 * Abak puede contarlo porque cada ejecución pasa por su registro. Esta pestaña
 * no acusa a nadie: enseña el rango completo del coeficiente entre todo lo que
 * probaste, para que el número que reportes lleve su contexto.
 */
export default function PanelEspecificaciones() {
  const seleccionado = usarLienzo((s) => s.seleccionado);
  const [disponibles, setDisponibles] = useState<{ resultado: string; veces: number }[]>([]);
  const [elegido, setElegido] = useState<string | null>(null);
  const [resumen, setResumen] = useState<ResumenEspecificaciones | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    api.especificacionesRegistradas()
      .then((r) => {
        setDisponibles(r.resultados);
        setElegido((actual) => actual ?? r.resultados[0]?.resultado ?? null);
      })
      .catch(() => setDisponibles([]))
      .finally(() => setCargando(false));
  }, []);

  const cargar = useCallback(() => {
    if (!elegido) return;
    api.especificaciones(elegido, seleccionado ?? undefined)
      .then(setResumen)
      .catch(() => setResumen(null));
  }, [elegido, seleccionado]);

  useEffect(cargar, [cargar]);

  if (cargando) {
    return <Vacio texto="Leyendo el registro de especificaciones…" />;
  }
  if (!disponibles.length) {
    return (
      <Vacio texto="Aquí se van contando los modelos que estimas. En cuanto corras una regresión aparece el registro: cuántas especificaciones llevas para cada variable explicada y cómo se mueve cada coeficiente entre ellas." />
    );
  }

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto max-w-4xl space-y-5">
        <div>
          <h2 className="text-[14px] font-medium text-crema">Lo que has probado</h2>
          <p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-tenue">
            Un coeficiente elegido entre muchas especificaciones no es lo mismo que un coeficiente
            solo. Esto no acusa de nada: pone al lado el rango completo, que es lo que hace falta
            para reportarlo con honestidad.
          </p>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {disponibles.map((d) => (
            <button
              key={d.resultado}
              onClick={() => setElegido(d.resultado)}
              className={`rounded-full border px-2.5 py-1 text-[11px] transition-colors ${
                d.resultado === elegido
                  ? 'border-salvia text-salvia'
                  : 'border-borde text-tenue hover:border-salvia/50 hover:text-crema'
              }`}
            >
              {d.resultado} · {d.veces}
            </button>
          ))}
        </div>

        {resumen && resumen.n_especificaciones > 0 && (
          <>
            <p className="text-[12px] text-crema/85">
              Llevas <span className="text-crema">{resumen.n_especificaciones}</span>{' '}
              {resumen.n_especificaciones === 1 ? 'especificación' : 'especificaciones'} para
              explicar <span className="text-crema">«{resumen.resultado}»</span>.
            </p>
            <div className="space-y-2">
              {resumen.variables.map((v) => <Fila key={v.variable} v={v} />)}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Fila({ v }: { v: VariableEspecificada }) {
  const rango = v.maximo - v.minimo;
  // Dónde cae el valor actual dentro del rango, en porcentaje.
  const posicion = (x: number) => (rango === 0 ? 50 : ((x - v.minimo) / rango) * 100);
  const alerta = v.actual_es_extremo || v.cambia_de_signo;

  return (
    <div className={`rounded-lg border bg-superficie p-3 ${
      alerta ? 'border-ambar/40' : 'border-borde'}`}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-[13px] text-crema">{v.variable}</span>
        <span className="text-[11px] text-tenue">
          en {v.veces} {v.veces === 1 ? 'especificación' : 'especificaciones'} ·
          significativa {v.veces_significativa} {v.veces_significativa === 1 ? 'vez' : 'veces'}
        </span>
        {v.actual !== null && (
          <span className="ml-auto text-[12px] text-crema">
            esta: <span className="tabular-nums">{num(v.actual, 4)}</span>
          </span>
        )}
      </div>

      {v.veces > 1 && (
        <>
          <div className="relative mt-2.5 h-1.5 rounded-full bg-tierra">
            <div className="absolute inset-y-0 rounded-full bg-salvia/25"
                 style={{ left: '0%', right: '0%' }} />
            {rango > 0 && v.minimo < 0 && v.maximo > 0 && (
              <div className="absolute inset-y-[-3px] w-px bg-terracota/70"
                   style={{ left: `${posicion(0)}%` }} title="Cero: aquí el efecto cambia de signo" />
            )}
            {v.actual !== null && (
              <div className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-tierra bg-crema"
                   style={{ left: `${posicion(v.actual)}%` }} />
            )}
          </div>
          <div className="mt-1 flex justify-between text-[10px] tabular-nums text-tenue">
            <span>{num(v.minimo, 4)}</span>
            <span>mediana {num(v.mediana, 4)}</span>
            <span>{num(v.maximo, 4)}</span>
          </div>
        </>
      )}

      {v.cambia_de_signo && (
        <p className="mt-2 text-[11px] leading-relaxed text-ambar">
          El signo cambia entre especificaciones: en unas el efecto es positivo y en otras negativo.
          Eso no es un hallazgo que se pueda reportar; es una señal de que el modelo no está
          identificando nada estable.
        </p>
      )}
      {v.actual_es_extremo && !v.cambia_de_signo && (
        <p className="mt-2 text-[11px] leading-relaxed text-ambar">
          El valor de esta especificación es el extremo de todas las que probaste. Si lo reportas,
          conviene decir también el rango: es la diferencia entre informar y seleccionar.
        </p>
      )}
    </div>
  );
}
