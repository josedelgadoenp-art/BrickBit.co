'use client';

import { useState } from 'react';

import { api, descargar, ErrorApi } from '@/lib/api';
import { EJEMPLOS } from '@/lib/ejemplos';
import { duracion } from '@/lib/formato';
import { usarLienzo } from '@/store/lienzo';

export default function BarraSuperior() {
  const {
    titulo, ponerTitulo, semilla, ponerSemilla, ejecutar, cancelar, ejecutando,
    ejecucion, validando, diagnosticos, nodos, limpiar, cargarGrafo, aGrafo, errorEjecucion,
    seleccionar, irA,
  } = usarLienzo();
  const [abiertoEjemplos, setAbiertoEjemplos] = useState(false);
  const [bajando, setBajando] = useState<'zip' | 'pdf' | null>(null);
  const [problema, setProblema] = useState<string | null>(null);

  const errores = diagnosticos.filter((d) => d.severidad === 'error').length;
  // El botón NO se apaga por tener problemas. Un botón muerto con un tooltip
  // es la peor señal posible: la persona hace clic, no pasa nada, y no sabe si
  // la herramienta está rota o si le falta hacer algo. Con problemas, el clic
  // lleva al bloque que los tiene y dice qué le falta.
  const puedeEjecutar = nodos.length > 0 && !ejecutando;
  const primerProblema = diagnosticos.find((d) => d.severidad === 'error');

  function alEjecutar() {
    if (errores > 0 && primerProblema) {
      if (primerProblema.nodo_id) seleccionar(primerProblema.nodo_id);
      irA('lienzo');
      setProblema(primerProblema.sugerencia
        ? `${primerProblema.mensaje} — ${primerProblema.sugerencia}`
        : primerProblema.mensaje);
      return;
    }
    setProblema(null);
    ejecutar();
  }

  async function exportar() {
    setBajando('zip');
    setProblema(null);
    try {
      await descargar(api.urlExportar(), { metodo: 'POST', cuerpo: { grafo: aGrafo() } });
    } catch (e) {
      setProblema(e instanceof ErrorApi ? e.mensaje : 'No se pudo exportar.');
    } finally {
      setBajando(null);
    }
  }

  async function informePdf() {
    if (!ejecucion) return;
    setBajando('pdf');
    setProblema(null);
    try {
      await descargar(api.urlInforme(ejecucion.id));
    } catch (e) {
      setProblema(e instanceof ErrorApi ? e.mensaje : 'No se pudo generar el informe.');
    } finally {
      setBajando(null);
    }
  }

  return (
    <header className="flex shrink-0 items-center gap-3 border-b border-borde bg-superficie px-4 py-2">
      <div className="flex items-center gap-2">
        <span className="text-[15px] font-semibold tracking-tight text-crema">Abak</span>
        <span className="hidden text-[11px] text-tenue lg:inline">
          análisis económico sin código
        </span>
      </div>

      <input
        value={titulo}
        onChange={(e) => ponerTitulo(e.target.value)}
        className="ml-2 min-w-0 flex-1 rounded border border-transparent bg-transparent px-2 py-1 text-[13px] text-crema hover:border-borde focus:border-salvia focus:outline-none"
        aria-label="Título del análisis"
      />

      <div className="relative">
        <button
          onClick={() => setAbiertoEjemplos((v) => !v)}
          className="rounded border border-borde px-2.5 py-1 text-[12px] text-tenue hover:text-crema"
        >
          Ejemplos ▾
        </button>
        {abiertoEjemplos && (
          <div className="absolute right-0 z-20 mt-1 w-80 rounded border border-borde bg-superficie shadow-panel">
            {EJEMPLOS.map((e) => (
              <button
                key={e.id}
                onClick={() => { cargarGrafo(e.grafo()); setAbiertoEjemplos(false); }}
                className="block w-full border-b border-borde/60 px-3 py-2 text-left last:border-0 hover:bg-superficie2"
              >
                <div className="text-[13px] text-crema">{e.titulo}</div>
                <div className="mt-0.5 text-[11px] leading-snug text-tenue">{e.descripcion}</div>
              </button>
            ))}
          </div>
        )}
      </div>

      <label className="flex items-center gap-1.5 text-[11px] text-tenue" title="Con la misma semilla y los mismos datos, el resultado se repite exactamente.">
        semilla
        <input
          type="number"
          value={semilla}
          onChange={(e) => ponerSemilla(Number(e.target.value) || 0)}
          className="w-16 rounded border border-borde bg-tierra px-1.5 py-0.5 text-[11px] text-crema focus:border-salvia focus:outline-none"
        />
      </label>

      <span className="text-[11px] text-tenue">
        {validando ? 'revisando…'
          : errores ? <span className="text-arcilla">{errores} problema{errores === 1 ? '' : 's'}</span>
          : nodos.length ? 'sin problemas' : ''}
      </span>

      <button onClick={limpiar} className="rounded border border-borde px-2.5 py-1 text-[12px] text-tenue hover:text-crema">
        Vaciar
      </button>
      <button onClick={exportar} disabled={!nodos.length || bajando !== null}
              title="Descarga un .zip con el script de Python, sus datos y la nota metodológica"
              className="rounded border border-borde px-2.5 py-1 text-[12px] text-tenue hover:text-crema disabled:opacity-40">
        {bajando === 'zip' ? 'Preparando…' : 'Exportar .zip'}
      </button>
      <button onClick={informePdf}
              disabled={!ejecucion || ejecucion.estado !== 'listo' || bajando !== null}
              title={ejecucion?.estado === 'listo'
                ? 'Informe en PDF con portada, resultados, gráficas, metodología y el código'
                : 'Ejecuta el análisis para poder generar el informe'}
              className="rounded border border-borde px-2.5 py-1 text-[12px] text-tenue hover:text-crema disabled:opacity-40">
        {bajando === 'pdf' ? 'Generando…' : 'Informe PDF'}
      </button>

      {ejecutando ? (
        <button onClick={cancelar} className="rounded bg-terracota/85 px-3 py-1 text-[12px] font-medium text-tierra hover:bg-terracota">
          Detener
        </button>
      ) : (
        <button
          onClick={alEjecutar}
          disabled={!puedeEjecutar}
          title={errores ? 'Te lleva al bloque que falta configurar' : 'Ejecuta el análisis completo'}
          className="rounded bg-salvia px-3 py-1 text-[12px] font-medium text-tierra hover:bg-salviaProfunda disabled:cursor-not-allowed disabled:opacity-40"
        >
          Ejecutar
        </button>
      )}

      {ejecucion?.ms_total != null && !ejecutando && (
        <span className="text-[11px] text-tenue">{duracion(ejecucion.ms_total)}</span>
      )}
      {(errorEjecucion || problema) && (
        <span className="text-[11px] text-arcilla">{errorEjecucion ?? problema}</span>
      )}
    </header>
  );
}
