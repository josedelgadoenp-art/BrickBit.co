'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { IconoCerrar, IconoIA, IconoSubir } from '@/components/ui/Icono';
import { api, ErrorApi } from '@/lib/api';
import { usarLienzo } from '@/store/lienzo';

/**
 * Pide el análisis en español y Abak lo arma.
 *
 * Es la puerta de entrada, no un accesorio: con el lienzo vacío ocupa el centro
 * de la pantalla, porque escribir una frase es lo único que alguien sabe hacer
 * sin haber aprendido nada de la herramienta. Cuando ya hay un análisis se
 * repliega a una pastilla arriba, para no estorbar el trabajo.
 *
 * Lo que hace que esto sea seguro y no una caja negra: el modelo **no escribe
 * código, escribe un grafo** de bloques del catálogo. Ese grafo pasa por la
 * misma validación de tipos y el mismo compilador que uno armado a mano, así
 * que el peor caso de una alucinación es un bloque en rojo con su mensaje. Y el
 * análisis queda EN EL LIENZO: se ve, se corrige y se ejecuta como cualquier
 * otro. La IA propone el punto de partida; el trabajo sigue siendo auditable.
 */

const SUGERENCIAS = [
  'Explica el precio por m² con el ingreso del hogar y la escolaridad, en logaritmos',
  'Construye un índice de precios de calidad constante por trimestre',
  '¿La ubicación importa? Prueba si los precios se agrupan en el espacio',
  'Pronostica el PIB a ocho trimestres y grafica la banda',
];

export default function Asistente() {
  const cargarGrafo = usarLienzo((s) => s.cargarGrafo);
  const esquemas = usarLienzo((s) => s.esquemas);
  const nodos = usarLienzo((s) => s.nodos);
  const aGrafo = usarLienzo((s) => s.aGrafo);
  const irA = usarLienzo((s) => s.irA);

  const vacio = nodos.length === 0;
  const [abierto, setAbierto] = useState(false);
  const [disponible, setDisponible] = useState<boolean | null>(null);
  const [motivo, setMotivo] = useState<string | null>(null);
  const [huella, setHuella] = useState<{ longitud?: number; prefijo?: string } | null>(null);
  const [prueba, setPrueba] = useState<string | null>(null);
  const [texto, setTexto] = useState('');
  const [pensando, setPensando] = useState(false);
  const [respuesta, setRespuesta] = useState<{ explicacion: string; advertencias: string[] } | null>(null);
  const [problema, setProblema] = useState<string | null>(null);
  const caja = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api.asistenteDisponible()
      .then((r) => {
        setDisponible(r.disponible);
        setMotivo(r.motivo);
        setHuella(r.llave?.hay ? r.llave : null);
      })
      .catch(() => setDisponible(false));
  }, []);

  useEffect(() => {
    if (abierto) caja.current?.focus();
  }, [abierto]);

  const construir = useCallback(async (peticionDada?: string) => {
    const peticion = (peticionDada ?? texto).trim();
    if (peticion.length < 3 || pensando) return;
    setPensando(true);
    setProblema(null);
    setRespuesta(null);
    try {
      // Se le pasan las columnas que de verdad existen en cada bloque: sin eso
      // el modelo adivina nombres, y adivinar un nombre de columna es la manera
      // más fácil de producir un análisis que parece correcto.
      const columnas = nodos.flatMap((n) =>
        Object.entries(esquemas[n.id] ?? {}).map(([, e]) => ({
          nodo_id: n.id, etiqueta: n.data.etiqueta, columnas: e.columnas,
        })));
      const r = await api.asistente(peticion, columnas, nodos.length ? aGrafo() : null);
      cargarGrafo(r.grafo);
      setRespuesta({ explicacion: r.explicacion, advertencias: r.advertencias });
      irA('lienzo');
    } catch (e) {
      // El motivo REAL, siempre. «No se pudo construir el análisis» a secas es
      // lo mismo que no decir nada: no distingue una caída de red de un fallo
      // al cargar el grafo que sí llegó, y manda a buscar del lado equivocado.
      if (e instanceof ErrorApi) {
        setProblema(e.mensaje);
      } else if (e instanceof DOMException && e.name === 'AbortError') {
        setProblema('La petición tardó más de dos minutos y se canceló. Suele pasar con '
          + 'peticiones muy largas: prueba con uno de los ejemplos de abajo, que son más cortos.');
      } else {
        const detalle = e instanceof Error ? `${e.name}: ${e.message}` : String(e);
        setProblema(`No se pudo construir el análisis — ${detalle}`);
      }
    } finally {
      setPensando(false);
    }
  }, [texto, pensando, nodos, esquemas, aGrafo, cargarGrafo, irA]);

  if (disponible === null) return null;

  const campo = (grande: boolean) => (
    <>
      <textarea
        ref={caja}
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); construir(); }
          if (e.key === 'Escape' && !vacio) setAbierto(false);
        }}
        rows={grande ? 3 : 3}
        placeholder="Explica el precio por m² con el ingreso y la escolaridad, y grafica el ajuste."
        className={`w-full resize-y rounded-xl2 border border-borde bg-tierra px-3.5 text-crema
                    placeholder:text-tenue/60 focus:border-salvia focus:outline-none
                    ${grande ? 'py-3 text-[14px] leading-relaxed' : 'py-2.5 text-[13px] leading-relaxed'}`}
      />
      <div className="mt-2.5 flex flex-wrap items-center gap-2">
        <span className="text-[11px] text-tenue">
          Arma el análisis en el lienzo. Lo revisas y lo ejecutas tú.
        </span>
        <button
          onClick={() => construir()}
          disabled={pensando || texto.trim().length < 3}
          className="ml-auto rounded-lg bg-salvia px-3.5 py-1.5 text-[12px] font-medium text-tierra
                     transition-colors hover:bg-salviaProfunda disabled:cursor-not-allowed disabled:opacity-40"
        >
          {pensando ? 'Armando…' : 'Armar análisis'}
        </button>
      </div>
    </>
  );

  const avisos = (
    <>
      {problema && (
        <div className="mt-2.5 rounded-lg border border-terracota/40 bg-terracota/8 px-3 py-2">
          <p className="text-[12px] leading-relaxed text-arcilla">{problema}</p>
          {/* Qué llave tiene EL SERVIDOR, no la que hay en el registro de
              Windows. `setx` no toca los procesos abiertos: un servidor
              arrancado antes de configurarla se queda con la vieja, y sin este
              renglón se ve idéntico a una llave mal escrita. */}
          {huella?.longitud !== undefined && (
            <p className="mt-1.5 font-mono text-[11px] leading-relaxed text-tenue">
              El servidor está usando una llave de {huella.longitud} caracteres que empieza
              con «{huella.prefijo}». Si no coincide con la que acabas de guardar, la ventana
              del API se abrió antes: ciérrala y vuelve a arrancarla.
            </p>
          )}
          {/* Una llamada mínima, sin salida estructurada ni caché ni
              razonamiento. Separa tres cosas que en pantalla se ven iguales:
              llave inválida, organización sin acceso al modelo, y algo de la
              petición grande que a la API no le gusta. */}
          <button
            onClick={async () => {
              setPrueba('Probando…');
              try {
                const r = await api.probarIA();
                setPrueba(r.ok
                  ? `Conexión correcta con ${r.modelo}. El problema no es la llave.`
                  : `Falló en «${r.etapa}»${r.codigo ? ` (${r.codigo})` : ''}: ${r.detalle}`);
              } catch (e) {
                // Un 404 aquí no es un fallo de Anthropic: es que ESTE servidor
                // no tiene la función todavía. Pasó de verdad, y «Not Found» a
                // secas mandaba a buscar el problema del lado equivocado.
                if (e instanceof ErrorApi && e.estado === 404) {
                  setPrueba('Tu servidor de Abak no tiene esta prueba todavía: quedó en una '
                    + 'versión anterior. Haz `git pull`, cierra la ventana del API y vuelve '
                    + 'a abrirla.');
                } else {
                  setPrueba(e instanceof ErrorApi ? e.mensaje : 'No se pudo probar.');
                }
              }
            }}
            className="mt-2 rounded border border-borde px-2 py-1 text-[11px] text-tenue
                       transition-colors hover:border-tenue/60 hover:text-crema"
          >
            Probar la conexión con Anthropic
          </button>
          {prueba && (
            <p className="mt-1.5 font-mono text-[11px] leading-relaxed text-crema/85">{prueba}</p>
          )}
        </div>
      )}
      {respuesta && (
        <div className="mt-2.5 rounded-lg border border-borde bg-tierra px-3 py-2.5 text-left">
          <p className="text-[12px] leading-relaxed text-crema/90">{respuesta.explicacion}</p>
          {respuesta.advertencias.length > 0 && (
            <ul className="mt-2 space-y-1">
              {respuesta.advertencias.map((a, i) => (
                <li key={i} className="text-[11px] leading-relaxed text-ambar">{a}</li>
              ))}
            </ul>
          )}
          <p className="mt-2 text-[11px] text-tenue">
            Revisa el lienzo antes de ejecutar: lo que armó es una propuesta, no un veredicto.
          </p>
        </div>
      )}
    </>
  );

  // --- Lienzo vacío: la IA ocupa el centro -----------------------------------
  if (vacio) {
    return (
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-6">
        <div className="pointer-events-auto w-full max-w-xl">
          <div className="mb-5 text-center">
            <h1 className="text-[26px] font-semibold tracking-apretado text-crema">
              ¿Qué quieres analizar?
            </h1>
            <p className="mx-auto mt-2 max-w-md text-[13px] leading-relaxed text-tenue">
              {disponible
                ? 'Descríbelo en español. La inteligencia artificial arma el análisis con las herramientas de Abak, y tú lo revisas paso por paso.'
                : 'Sube tus datos o abre un ejemplo para empezar. Cada herramienta explica qué hace y cuándo usarla.'}
            </p>
          </div>

          {/* Cuando el asistente no está disponible se DICE qué falta. Antes se
              escondía sin más, y desde la pantalla no había manera de saber si
              faltaba algo por configurar o si la función no existía. */}
          {!disponible && motivo && (
            <div className="rounded-xl2 border border-ambar/30 bg-ambar/5 p-3.5">
              <p className="text-[12px] font-medium text-ambar">
                Para pedir el análisis en español falta un paso
              </p>
              <pre className="mt-2 overflow-x-auto whitespace-pre-wrap font-mono text-[11px]
                              leading-relaxed text-crema/85">{motivo}</pre>
            </div>
          )}

          {disponible && (
            <div className="rounded-xl2 border border-borde bg-superficie/95 p-3.5 shadow-alto backdrop-blur">
              {campo(true)}
              {avisos}
            </div>
          )}

          {disponible && !respuesta && (
            <div className="mt-4">
              <p className="mb-2 text-center text-[11px] uppercase tracking-wide text-tenue">
                O prueba con una de éstas
              </p>
              <div className="flex flex-col gap-1.5">
                {SUGERENCIAS.map((s) => (
                  <button
                    key={s}
                    onClick={() => { setTexto(s); construir(s); }}
                    disabled={pensando}
                    className="rounded-lg border border-bordeSuave bg-superficie/60 px-3 py-2 text-left
                               text-[12px] leading-relaxed text-tenue transition-colors
                               hover:border-salvia/40 hover:text-crema disabled:opacity-50"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          <p className="mt-5 flex items-center justify-center gap-1.5 text-center text-[12px] text-tenue">
            <IconoSubir className="h-3.5 w-3.5" />
            ¿Tienes tus propios datos? Usa
            <span className="text-salvia">Subir datos</span>
            arriba.
          </p>
        </div>
      </div>
    );
  }

  // --- Ya hay análisis: se repliega a una pastilla ---------------------------
  if (!disponible) return null;

  return (
    <div className="pointer-events-none absolute inset-x-0 top-3 z-20 flex justify-center px-4">
      <div className="pointer-events-auto w-full max-w-2xl">
        {!abierto ? (
          <button
            onClick={() => setAbierto(true)}
            className="mx-auto flex items-center gap-2 rounded-full border border-salvia/40
                       bg-superficie/95 px-4 py-2 text-[12px] text-salvia shadow-panel backdrop-blur
                       transition-colors hover:border-salvia hover:bg-superficie"
          >
            <IconoIA className="h-3.5 w-3.5" />
            Pídele otro paso a la IA
          </button>
        ) : (
          <div className="rounded-xl2 border border-borde bg-superficie/97 p-3.5 shadow-alto backdrop-blur">
            <div className="mb-2.5 flex items-center gap-2">
              <IconoIA className="h-3.5 w-3.5 text-salvia" />
              <span className="text-[12px] font-medium text-crema">Pídelo en español</span>
              <button
                onClick={() => { setAbierto(false); setRespuesta(null); setProblema(null); }}
                className="ml-auto rounded px-1 text-tenue hover:text-crema"
                aria-label="Cerrar el asistente"
              >
                <IconoCerrar />
              </button>
            </div>
            {campo(false)}
            {avisos}
          </div>
        )}
      </div>
    </div>
  );
}
