'use client';

import { useRef, useState } from 'react';

import { IconoAbajo, IconoSubir } from '@/components/ui/Icono';
import { api, descargar, ErrorApi } from '@/lib/api';
import { EJEMPLOS } from '@/lib/ejemplos';
import { duracion } from '@/lib/formato';
import { usarLienzo } from '@/store/lienzo';

/**
 * La barra de arriba.
 *
 * Tenía nueve controles del mismo tamaño, y ocho de ellos no sirven de nada
 * hasta que hay un análisis corrido. Ahora aparecen por etapas: con el lienzo
 * vacío quedan los dos que sí se pueden usar (subir datos, abrir un ejemplo), y
 * lo que se hace UNA vez —la semilla, vaciar, las descargas— se agrupa en menús
 * en lugar de competir por atención con «Ejecutar».
 */
export default function BarraSuperior() {
  const {
    titulo, ponerTitulo, semilla, ponerSemilla, ejecutar, cancelar, ejecutando,
    ejecucion, validando, diagnosticos, nodos, limpiar, cargarGrafo, aGrafo, errorEjecucion,
    seleccionar, irA, agregarNodo, actualizarParams,
  } = usarLienzo();
  const [menu, setMenu] = useState<'ejemplos' | 'descargas' | 'ajustes' | null>(null);
  const [bajando, setBajando] = useState<'zip' | 'pdf' | null>(null);
  const [problema, setProblema] = useState<string | null>(null);
  const [subiendo, setSubiendo] = useState(false);
  const campoArchivo = useRef<HTMLInputElement>(null);

  const hayNodos = nodos.length > 0;

  /**
   * Subir datos en un solo gesto.
   *
   * Antes había que saber que la herramienta se llama «Cargar archivo», buscarla
   * en la paleta, ponerla en el lienzo y recién entonces aparecía el botón de
   * subir. Traer tus propios datos es lo primero que hace cualquiera: no puede
   * estar a cuatro pasos de distancia y detrás de un nombre que hay que adivinar.
   */
  async function subirDatos(archivo: File) {
    setSubiendo(true);
    setProblema(null);
    try {
      const cuerpo = new FormData();
      cuerpo.append('archivo', archivo);
      const r = await fetch('/api/v1/datos/subir', { method: 'POST', body: cuerpo });
      if (!r.ok) throw new ErrorApi(r.status, await r.json().catch(() => null));
      const datos = await r.json();
      const id = agregarNodo('datos.csv');
      if (id) {
        actualizarParams(id, {
          archivo_id: datos.archivo_id, nombre: datos.nombre,
          columnas: datos.columnas, n_filas: datos.n_filas,
        });
      }
      irA('lienzo');
    } catch (e) {
      setProblema(e instanceof ErrorApi ? e.mensaje : 'No se pudo subir el archivo.');
    } finally {
      setSubiendo(false);
      if (campoArchivo.current) campoArchivo.current.value = '';
    }
  }

  const errores = diagnosticos.filter((d) => d.severidad === 'error').length;
  // El botón NO se apaga por tener problemas. Un botón muerto con un tooltip
  // es la peor señal posible: la persona hace clic, no pasa nada, y no sabe si
  // la herramienta está rota o si le falta hacer algo. Con problemas, el clic
  // lleva al bloque que los tiene y dice qué le falta.
  const puedeEjecutar = hayNodos && !ejecutando;
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
    ejecutar(undefined, { llevarAResultados: true });
  }

  async function exportar() {
    setMenu(null);
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
    setMenu(null);
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

  const secundario = 'rounded-lg border border-borde px-2.5 py-1 text-[12px] text-tenue '
    + 'transition-colors hover:border-tenue/60 hover:text-crema disabled:opacity-40';

  return (
    <header className="relative flex shrink-0 items-center gap-3 border-b border-borde bg-superficie px-4 py-2">
      {/* Un solo velo para los tres menús: sin él se quedan abiertos y tapan
          justo el control que se quería usar después. */}
      {menu && (
        <button aria-label="Cerrar el menú" onClick={() => setMenu(null)}
                className="fixed inset-0 z-20 cursor-default" />
      )}

      <div className="flex items-center gap-2">
        <span className="text-[15px] font-semibold tracking-tight text-crema">Abak</span>
        <span className="hidden text-[11px] text-tenue lg:inline">
          inteligencia económica
        </span>
      </div>

      {hayNodos ? (
        <input
          value={titulo}
          onChange={(e) => ponerTitulo(e.target.value)}
          placeholder="Título del análisis"
          className="ml-2 min-w-0 flex-1 rounded border border-transparent bg-transparent px-2 py-1
                     text-[13px] text-crema placeholder:text-tenue/50 hover:border-borde
                     focus:border-salvia focus:outline-none"
          aria-label="Título del análisis"
        />
      ) : (
        <div className="flex-1" />
      )}

      <input
        ref={campoArchivo}
        type="file"
        accept=".csv,.tsv,.txt,.xlsx,.xls,.parquet,.zip"
        className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) subirDatos(f); }}
      />
      <button
        onClick={() => campoArchivo.current?.click()}
        disabled={subiendo}
        title="Sube un CSV, Excel, Parquet o ZIP y queda listo para analizar"
        className="inline-flex items-center gap-1.5 rounded-lg border border-salvia/50 px-2.5 py-1
                   text-[12px] text-salvia transition-colors hover:bg-salvia/10 disabled:opacity-50"
      >
        <IconoSubir className="h-3.5 w-3.5" />
        {subiendo ? 'Subiendo…' : 'Subir datos'}
      </button>

      <div className="relative">
        <button onClick={() => setMenu(menu === 'ejemplos' ? null : 'ejemplos')}
                className={`inline-flex items-center gap-1.5 ${secundario}`}>
          Ejemplos
          <IconoAbajo className="h-3 w-3" />
        </button>
        {menu === 'ejemplos' && (
          <div className="absolute right-0 z-30 mt-1 w-80 rounded-xl2 border border-borde bg-superficie shadow-panel">
            {EJEMPLOS.map((e) => (
              <button
                key={e.id}
                onClick={() => { cargarGrafo(e.grafo()); setMenu(null); irA('lienzo'); }}
                className="block w-full border-b border-borde/60 px-3 py-2 text-left last:border-0 hover:bg-superficie2"
              >
                <div className="text-[13px] text-crema">{e.titulo}</div>
                <div className="mt-0.5 text-[11px] leading-snug text-tenue">{e.descripcion}</div>
              </button>
            ))}
          </div>
        )}
      </div>

      {hayNodos && (
        <>
          <span className="text-[11px] text-tenue">
            {validando ? 'revisando…'
              : errores ? <span className="text-arcilla">{errores} problema{errores === 1 ? '' : 's'}</span>
              : 'sin problemas'}
          </span>

          <div className="relative">
            <button onClick={() => setMenu(menu === 'descargas' ? null : 'descargas')}
                    disabled={bajando !== null}
                    className={`inline-flex items-center gap-1.5 ${secundario}`}>
              {bajando === 'zip' ? 'Preparando…' : bajando === 'pdf' ? 'Generando…' : 'Descargar'}
              <IconoAbajo className="h-3 w-3" />
            </button>
            {menu === 'descargas' && (
              <div className="absolute right-0 z-30 mt-1 w-72 rounded-xl2 border border-borde bg-superficie shadow-panel">
                <button onClick={exportar}
                        className="block w-full border-b border-borde/60 px-3 py-2 text-left hover:bg-superficie2">
                  <div className="text-[13px] text-crema">Proyecto en .zip</div>
                  <div className="mt-0.5 text-[11px] leading-snug text-tenue">
                    El script de Python, sus datos y la nota metodológica. Corre sin Abak.
                  </div>
                </button>
                <button onClick={informePdf} disabled={ejecucion?.estado !== 'listo'}
                        className="block w-full px-3 py-2 text-left hover:bg-superficie2 disabled:opacity-40">
                  <div className="text-[13px] text-crema">Informe en PDF</div>
                  <div className="mt-0.5 text-[11px] leading-snug text-tenue">
                    {ejecucion?.estado === 'listo'
                      ? 'Portada, resultados, gráficas, metodología y código.'
                      : 'Ejecuta el análisis para poder generarlo.'}
                  </div>
                </button>
              </div>
            )}
          </div>

          <div className="relative">
            <button onClick={() => setMenu(menu === 'ajustes' ? null : 'ajustes')}
                    title="Semilla y vaciar" aria-label="Más opciones"
                    className={secundario}>
              ⋯
            </button>
            {menu === 'ajustes' && (
              <div className="absolute right-0 z-30 mt-1 w-72 rounded-xl2 border border-borde bg-superficie p-3 shadow-panel">
                <label className="flex items-center justify-between gap-2 text-[12px] text-crema">
                  Semilla
                  <input
                    type="number"
                    value={semilla}
                    onChange={(e) => ponerSemilla(Number(e.target.value) || 0)}
                    className="w-20 rounded border border-borde bg-tierra px-1.5 py-0.5 text-[12px] text-crema focus:border-salvia focus:outline-none"
                  />
                </label>
                <p className="mt-1 text-[11px] leading-snug text-tenue">
                  Con la misma semilla y los mismos datos, el resultado se repite exactamente.
                </p>
                <button onClick={() => { limpiar(); setMenu(null); }}
                        className="mt-3 w-full rounded-lg border border-borde px-2.5 py-1.5 text-[12px] text-tenue transition-colors hover:border-terracota/60 hover:text-arcilla">
                  Vaciar y empezar de nuevo
                </button>
              </div>
            )}
          </div>

          {ejecutando ? (
            <button onClick={cancelar} className="rounded-lg bg-terracota/85 px-3 py-1 text-[12px] font-medium text-tierra hover:bg-terracota">
              Detener
            </button>
          ) : (
            <button
              onClick={alEjecutar}
              disabled={!puedeEjecutar}
              title={errores ? 'Te lleva al bloque que falta configurar' : 'Ejecuta el análisis completo'}
              className="rounded-lg bg-salvia px-3 py-1 text-[12px] font-medium text-tierra transition-colors hover:bg-salviaProfunda disabled:cursor-not-allowed disabled:opacity-40"
            >
              Ejecutar
            </button>
          )}

          {ejecucion?.ms_total != null && !ejecutando && (
            <span className="text-[11px] text-tenue">{duracion(ejecucion.ms_total)}</span>
          )}
        </>
      )}

      {(errorEjecucion || problema) && (
        <span className="max-w-[22rem] truncate text-[11px] text-arcilla"
              title={errorEjecucion ?? problema ?? ''}>
          {errorEjecucion ?? problema}
        </span>
      )}
    </header>
  );
}
