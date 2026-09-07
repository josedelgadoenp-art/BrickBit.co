'use client';

import { useEffect, useRef, useState } from 'react';

import { api, ErrorApi } from '@/lib/api';
import { usarLienzo } from '@/store/lienzo';

/**
 * Pide el análisis en español y Abak lo arma solo.
 *
 * La propiedad que hace esto seguro: el modelo **no escribe código**, escribe
 * un grafo de bloques del catálogo. Ese grafo pasa por la misma validación de
 * tipos y el mismo compilador que uno armado a mano, así que el peor caso de
 * una alucinación es un bloque en rojo con su mensaje — nunca código
 * ejecutándose. Y el análisis queda en el lienzo: se ve, se corrige y se
 * ejecuta como cualquier otro. No es una caja negra que escupe un número.
 */
export default function Asistente() {
  const cargarGrafo = usarLienzo((s) => s.cargarGrafo);
  const esquemas = usarLienzo((s) => s.esquemas);
  const nodos = usarLienzo((s) => s.nodos);
  const aGrafo = usarLienzo((s) => s.aGrafo);
  const irA = usarLienzo((s) => s.irA);

  const [abierto, setAbierto] = useState(false);
  const [disponible, setDisponible] = useState<boolean | null>(null);
  const [texto, setTexto] = useState('');
  const [pensando, setPensando] = useState(false);
  const [respuesta, setRespuesta] = useState<{ explicacion: string; advertencias: string[] } | null>(null);
  const [problema, setProblema] = useState<string | null>(null);
  const caja = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api.asistenteDisponible()
      .then((r) => setDisponible(r.disponible))
      .catch(() => setDisponible(false));
  }, []);

  useEffect(() => {
    if (abierto) caja.current?.focus();
  }, [abierto]);

  async function construir() {
    const peticion = texto.trim();
    if (peticion.length < 3 || pensando) return;
    setPensando(true);
    setProblema(null);
    setRespuesta(null);
    try {
      // Se le pasan las columnas que de verdad existen en cada bloque: sin eso
      // el modelo adivina nombres, y adivinar un nombre de columna es la
      // manera más fácil de producir un análisis que parece correcto.
      const columnas = nodos.flatMap((n) =>
        Object.entries(esquemas[n.id] ?? {}).map(([, e]) => ({
          nodo_id: n.id, etiqueta: n.data.etiqueta, columnas: e.columnas,
        })));
      const r = await api.asistente(peticion, columnas, nodos.length ? aGrafo() : null);
      cargarGrafo(r.grafo);
      setRespuesta({ explicacion: r.explicacion, advertencias: r.advertencias });
      irA('lienzo');
    } catch (e) {
      setProblema(e instanceof ErrorApi ? e.mensaje : 'No se pudo construir el análisis.');
    } finally {
      setPensando(false);
    }
  }

  if (disponible === false) return null;

  return (
    <div className="pointer-events-none absolute inset-x-0 top-3 z-20 flex justify-center px-4">
      <div className="pointer-events-auto w-full max-w-2xl">
        {!abierto ? (
          <button
            onClick={() => setAbierto(true)}
            className="mx-auto flex items-center gap-2 rounded-full border border-salvia/40 bg-superficie/95 px-4 py-2 text-[12px] text-salvia shadow-panel backdrop-blur transition-colors hover:border-salvia hover:bg-superficie"
          >
            <span aria-hidden>✦</span>
            Pídelo en español y Abak lo arma
          </button>
        ) : (
          <div className="rounded-xl border border-borde bg-superficie/97 p-3 shadow-panel backdrop-blur">
            <div className="mb-2 flex items-baseline gap-2">
              <span className="text-[12px] font-medium text-crema">
                <span className="text-salvia" aria-hidden>✦</span> Pídelo en español
              </span>
              <button
                onClick={() => { setAbierto(false); setRespuesta(null); setProblema(null); }}
                className="ml-auto rounded px-1.5 text-[12px] text-tenue hover:text-crema"
                aria-label="Cerrar el asistente"
              >
                ✕
              </button>
            </div>

            <textarea
              ref={caja}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); construir(); }
                if (e.key === 'Escape') setAbierto(false);
              }}
              rows={3}
              placeholder="Explica el precio por m² con el ingreso y la escolaridad, en logaritmos, y grafica el ajuste."
              className="w-full resize-y rounded-lg border border-borde bg-tierra px-3 py-2 text-[13px] leading-relaxed text-crema placeholder:text-tenue/70 focus:border-salvia focus:outline-none"
            />

            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="text-[11px] text-tenue">
                Arma el análisis en el lienzo. Lo revisas y lo ejecutas tú.
              </span>
              <button
                onClick={construir}
                disabled={pensando || texto.trim().length < 3}
                className="ml-auto rounded bg-salvia px-3 py-1 text-[12px] font-medium text-tierra hover:bg-salviaProfunda disabled:cursor-not-allowed disabled:opacity-40"
              >
                {pensando ? 'Armando…' : 'Armar análisis'}
              </button>
            </div>

            {problema && (
              <p className="mt-2 rounded border border-terracota/40 bg-terracota/8 px-2.5 py-1.5 text-[12px] leading-relaxed text-arcilla">
                {problema}
              </p>
            )}

            {respuesta && (
              <div className="mt-2 rounded border border-borde bg-tierra px-2.5 py-2">
                <p className="text-[12px] leading-relaxed text-crema/90">{respuesta.explicacion}</p>
                {respuesta.advertencias.length > 0 && (
                  <ul className="mt-1.5 space-y-1">
                    {respuesta.advertencias.map((a, i) => (
                      <li key={i} className="text-[11px] leading-relaxed text-ambar">· {a}</li>
                    ))}
                  </ul>
                )}
                <p className="mt-1.5 text-[11px] text-tenue">
                  Revisa el lienzo antes de ejecutar: lo que armó es una propuesta, no un veredicto.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
