'use client';

import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import { usarLienzo } from '@/store/lienzo';

/**
 * La ventana que explica un indicador.
 *
 * Es la respuesta al problema que hunde a SPSS y a EViews: alguien corre el
 * procedimiento y se queda mirando «R²», «Prob(F)» y «Durbin-Watson» sin saber
 * cuál importa ni qué valor es bueno. Aquí cada número trae al lado qué es,
 * cómo se lee y qué error se comete con él.
 *
 * Si el indicador no tiene ficha, el botón no aparece: no se inventa una
 * explicación para rellenar.
 *
 * Va montada en el `body` con `position: fixed` y no dentro de la celda que la
 * dispara. Colgarla del `th` la rompía de tres maneras a la vez: el encabezado
 * es `sticky`, y eso crea un contexto de apilamiento que dejaba la ventana por
 * debajo de las filas; `.tabla-datos th` trae `white-space: nowrap`, que se
 * hereda y hacía que el texto saliera en una sola línea fuera de la caja; y el
 * contenedor de la tabla recorta con `overflow`. Sacarla del árbol de la tabla
 * resuelve los tres de una vez.
 */

const ANCHO = 340; // ancho fijo de la ventana, en px
const MARGEN = 12; // aire mínimo contra el borde de la pantalla

export default function Explicacion({
  clave,
  alineacion = 'izquierda',
}: { clave: string; alineacion?: 'izquierda' | 'derecha' }) {
  const ficha = usarLienzo((s) => s.indicador(clave));
  const [abierta, setAbierta] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const boton = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const id = useId();

  /** Calcula dónde cabe la ventana: pegada al botón, pero siempre dentro de la pantalla. */
  const colocar = useCallback(() => {
    const b = boton.current;
    if (!b) return;
    const r = b.getBoundingClientRect();
    const alto = panel.current?.offsetHeight ?? 280;

    let left = alineacion === 'derecha' ? r.right - ANCHO : r.left;
    left = Math.min(left, window.innerWidth - ANCHO - MARGEN);
    left = Math.max(MARGEN, left);

    let top = r.bottom + 6;
    if (top + alto > window.innerHeight - MARGEN) {
      const arriba = r.top - alto - 6;
      top = arriba >= MARGEN ? arriba : Math.max(MARGEN, window.innerHeight - alto - MARGEN);
    }
    setPos({ top, left });
  }, [alineacion]);

  useLayoutEffect(() => {
    if (abierta) colocar();
  }, [abierta, colocar]);

  useEffect(() => {
    if (!abierta) return;
    const fuera = (e: MouseEvent) => {
      const destino = e.target as Node;
      if (boton.current?.contains(destino)) return;
      if (panel.current?.contains(destino)) return;
      setAbierta(false);
    };
    const escape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setAbierta(false);
        boton.current?.focus();
      }
    };
    // `capture` para enterarse también de los scrolls de los paneles internos.
    const seguir = () => colocar();
    document.addEventListener('mousedown', fuera);
    document.addEventListener('keydown', escape);
    window.addEventListener('scroll', seguir, true);
    window.addEventListener('resize', seguir);
    return () => {
      document.removeEventListener('mousedown', fuera);
      document.removeEventListener('keydown', escape);
      window.removeEventListener('scroll', seguir, true);
      window.removeEventListener('resize', seguir);
    };
  }, [abierta, colocar]);

  if (!ficha) return null;

  const ventana = (
    <div
      id={id}
      ref={panel}
      role="dialog"
      aria-label={ficha.titulo}
      style={{ top: pos?.top ?? -9999, left: pos?.left ?? -9999, width: ANCHO }}
      className="fixed z-[100] max-h-[70vh] overflow-y-auto whitespace-normal break-words rounded-lg
                 border border-borde bg-superficie p-3 text-left font-normal normal-case
                 tracking-normal shadow-panel"
    >
      <p className="text-[13px] font-medium text-crema">{ficha.titulo}</p>

      <p className="mt-2 text-[12px] leading-relaxed text-crema/85">{ficha.que_es}</p>

      <div className="mt-2.5">
        <p className="text-[10px] uppercase tracking-wide text-salvia">Cómo se lee</p>
        <p className="mt-0.5 text-[12px] leading-relaxed text-crema/85">{ficha.como_se_lee}</p>
      </div>

      {ficha.ojo_con && (
        <div className="mt-2.5 rounded border border-ambar/30 bg-ambar/5 p-2">
          <p className="text-[10px] uppercase tracking-wide text-ambar">Ojo con esto</p>
          <p className="mt-0.5 text-[12px] leading-relaxed text-crema/85">{ficha.ojo_con}</p>
        </div>
      )}

      {ficha.referencia && (
        <p className="mt-2.5 text-[11px] leading-relaxed text-tenue">
          Para leer más: {ficha.referencia}
        </p>
      )}
    </div>
  );

  return (
    <>
      <button
        ref={boton}
        type="button"
        aria-expanded={abierta}
        aria-controls={abierta ? id : undefined}
        aria-label={`Qué es ${ficha.titulo}`}
        onClick={(e) => { e.stopPropagation(); setAbierta((v) => !v); }}
        className={`ml-1 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border
                    align-middle text-[9px] leading-none transition-colors ${
          abierta
            ? 'border-salvia bg-salvia text-tierra'
            : 'border-borde text-tenue hover:border-salvia hover:text-salvia'
        }`}
      >
        ?
      </button>
      {abierta && typeof document !== 'undefined' && createPortal(ventana, document.body)}
    </>
  );
}
