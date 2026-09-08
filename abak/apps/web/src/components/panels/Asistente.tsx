'use client';

import { useCallback, useRef, useState } from 'react';

import { IconoDerecha, IconoIA, IconoSubir } from '@/components/ui/Icono';
import { api, ErrorApi } from '@/lib/api';
import { EJEMPLOS } from '@/lib/ejemplos';
import { usarLienzo } from '@/store/lienzo';

/**
 * Pide el análisis en español, lo arma y lo corre.
 *
 * Es la puerta de entrada, no un accesorio. Con el lienzo vacío ocupa toda la
 * pantalla, porque escribir una frase es lo único que alguien sabe hacer sin
 * haber aprendido nada de la herramienta. Cuando ya hay un análisis se
 * convierte en una barra fija bajo las pestañas: siempre el mismo sitio para
 * pedir lo siguiente.
 *
 * El cambio que más se nota: **no se detiene al armar el grafo**. Antes
 * dejaba a la persona mirando doce cajas conectadas y un botón «Ejecutar» que
 * había que descubrir. Ahora valida, ejecuta y aterriza en el resultado, que
 * es lo que se preguntó. El grafo sigue ahí, a una pestaña de distancia, para
 * quien quiera revisarlo o corregirlo.
 *
 * Lo que hace que esto sea seguro y no una caja negra: el modelo **no escribe
 * código, escribe un grafo** de bloques del catálogo. Ese grafo pasa por la
 * misma validación de tipos y el mismo compilador que uno armado a mano, así
 * que el peor caso de una alucinación es un bloque en rojo con su mensaje.
 */

const SUGERENCIAS = [
  'Explica el precio por m² con el ingreso del hogar y la escolaridad, en logaritmos',
  'Construye un índice de precios de calidad constante por trimestre',
  '¿La ubicación importa? Prueba si los precios se agrupan en el espacio',
  'Pronostica el PIB a ocho trimestres y grafica la banda',
];

type Fase = 'quieto' | 'armando' | 'ejecutando';

/**
 * `portada` es la pantalla de entrada; `barra`, la fila fija bajo las pestañas.
 *
 * Se pasa como propiedad en vez de deducirlo de «¿hay bloques?» porque hay un
 * caso donde las dos cosas no coinciden: quien pide armarlo a mano tiene el
 * taller abierto y el lienzo vacío, y ahí la portada no va.
 */
export default function Asistente({ modo = 'portada' }: { modo?: 'portada' | 'barra' }) {
  const cargarGrafo = usarLienzo((s) => s.cargarGrafo);
  const ponerRespuestaIA = usarLienzo((s) => s.ponerRespuestaIA);
  const validarYa = usarLienzo((s) => s.validarYa);
  const ejecutar = usarLienzo((s) => s.ejecutar);
  const esquemas = usarLienzo((s) => s.esquemas);
  const nodos = usarLienzo((s) => s.nodos);
  const aGrafo = usarLienzo((s) => s.aGrafo);
  const irA = usarLienzo((s) => s.irA);
  const seleccionar = usarLienzo((s) => s.seleccionar);
  const ponerManual = usarLienzo((s) => s.ponerManual);
  const disponible = usarLienzo((s) => s.iaDisponible);
  const motivo = usarLienzo((s) => s.iaMotivo);
  const huella = usarLienzo((s) => s.iaLlave);

  const [prueba, setPrueba] = useState<string | null>(null);
  const [texto, setTexto] = useState('');
  const [fase, setFase] = useState<Fase>('quieto');
  const [problema, setProblema] = useState<string | null>(null);
  const [aRevisar, setARevisar] = useState<string | null>(null);
  const caja = useRef<HTMLTextAreaElement>(null);

  const pensando = fase !== 'quieto';

  const construir = useCallback(async (peticionDada?: string) => {
    const peticion = (peticionDada ?? texto).trim();
    if (peticion.length < 3 || pensando) return;
    setFase('armando');
    setProblema(null);
    setARevisar(null);
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
      ponerRespuestaIA({ peticion, explicacion: r.explicacion, advertencias: r.advertencias });
      setTexto('');

      // Se valida ANTES de ejecutar. Mandar a correr un grafo con un hueco
      // devuelve un error de servidor en letra chica; revisarlo aquí permite
      // decir qué bloque le falta y llevar a la persona hasta él.
      const diagnosticos = await validarYa();
      const falla = diagnosticos.find((d) => d.severidad === 'error');
      if (falla) {
        setProblema(falla.sugerencia ? `${falla.mensaje} — ${falla.sugerencia}` : falla.mensaje);
        setARevisar(falla.nodo_id ?? null);
        irA('lienzo');
        return;
      }

      setFase('ejecutando');
      await ejecutar(undefined, { llevarAResultados: true });
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
      setFase('quieto');
    }
  }, [texto, pensando, nodos, esquemas, aGrafo, cargarGrafo, ponerRespuestaIA,
      validarYa, ejecutar, irA]);

  if (disponible === null) return null;

  const leyenda = fase === 'armando' ? 'Armando el análisis…'
    : fase === 'ejecutando' ? 'Ejecutando…'
    : null;

  // --- El aviso de un problema, igual en las dos presentaciones --------------
  const avisoProblema = problema && (
    <div className="rounded-xl2 border border-terracota/40 bg-terracota/8 px-3.5 py-2.5 text-left">
      <p className="text-[12px] leading-relaxed text-arcilla">{problema}</p>
      {aRevisar && (
        <button
          onClick={() => { seleccionar(aRevisar); irA('lienzo'); }}
          className="mt-2 rounded-lg border border-borde px-2.5 py-1 text-[11px] text-tenue
                     transition-colors hover:border-salvia/50 hover:text-crema"
        >
          Ver el bloque que falta
        </button>
      )}
      {/* Qué llave tiene EL SERVIDOR, no la que hay en el registro de Windows.
          `setx` no toca los procesos abiertos: un servidor arrancado antes de
          configurarla se queda con la vieja, y sin este renglón se ve idéntico
          a una llave mal escrita. */}
      {!aRevisar && huella?.longitud !== undefined && (
        <p className="mt-1.5 font-mono text-[11px] leading-relaxed text-tenue">
          El servidor está usando una llave de {huella.longitud} caracteres que empieza
          con «{huella.prefijo}». Si no coincide con la que acabas de guardar, la ventana
          del API se abrió antes: ciérrala y vuelve a arrancarla.
        </p>
      )}
      {/* Una llamada mínima, sin salida estructurada ni caché ni razonamiento.
          Separa tres cosas que en pantalla se ven iguales: llave inválida,
          organización sin acceso al modelo, y algo de la petición grande que a
          la API no le gusta. */}
      {!aRevisar && (
        <button
          onClick={async () => {
            setPrueba('Probando…');
            try {
              const r = await api.probarIA();
              setPrueba(r.ok
                ? `Conexión correcta con ${r.modelo}. El problema no es la llave.`
                : `Falló en «${r.etapa}»${r.codigo ? ` (${r.codigo})` : ''}: ${r.detalle}`);
            } catch (e) {
              // Un 404 aquí no es un fallo de Anthropic: es que ESTE servidor no
              // tiene la función todavía. Pasó de verdad, y «Not Found» a secas
              // mandaba a buscar el problema del lado equivocado.
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
      )}
      {prueba && (
        <p className="mt-1.5 font-mono text-[11px] leading-relaxed text-crema/85">{prueba}</p>
      )}
    </div>
  );

  // --- Paso 1: el lienzo está vacío y esto es lo único en pantalla ----------
  if (modo === 'portada') {
    return (
      <div className="flex h-full items-center justify-center overflow-y-auto p-6">
        <div className="w-full max-w-2xl py-6">
          <div className="mb-6 text-center">
            {/* Sin llave no hay paso de «preguntar», así que tampoco se
                anuncia: prometer una ruta que no está disponible es peor que
                no prometer ninguna. */}
            {disponible && (
              <p className="mb-3 text-[11px] uppercase tracking-[0.14em] text-tenue">
                Paso 1 de 3 · Pregunta
              </p>
            )}
            <h1 className="text-[30px] font-semibold leading-tight tracking-apretado text-crema">
              {disponible ? '¿Qué quieres analizar?' : '¿Por dónde empezamos?'}
            </h1>
            <p className="mx-auto mt-2.5 max-w-lg text-[13px] leading-relaxed text-tenue">
              {disponible
                ? 'Escríbelo en español, como se lo dirías a un colega. Abak arma el análisis, lo corre y te deja en el resultado.'
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
              <p className="mt-2.5 text-[12px] leading-relaxed text-crema/85">
                Mientras tanto Abak funciona igual: abre uno de los análisis de abajo, o sube
                tus datos y ármalo a mano.
              </p>
            </div>
          )}

          {/* Sin llave de IA la pantalla no puede quedarse en un aviso: al
              vaciarse el lienzo también se esconde la paleta, así que sin esta
              lista no habría por dónde empezar. */}
          {!disponible && (
            <div className="mt-4 flex flex-col gap-1.5">
              {EJEMPLOS.map((e) => (
                <button
                  key={e.id}
                  onClick={() => { cargarGrafo(e.grafo()); irA('lienzo'); }}
                  className="rounded-xl2 border border-bordeSuave bg-superficie/60 px-3.5 py-2.5
                             text-left transition-colors hover:border-salvia/40"
                >
                  <div className="text-[13px] text-crema">{e.titulo}</div>
                  <div className="mt-0.5 text-[11px] leading-snug text-tenue">{e.descripcion}</div>
                </button>
              ))}
            </div>
          )}

          {disponible && (
            <div className="rounded-xl2 border border-borde bg-superficie p-3.5 shadow-alto">
              <textarea
                ref={caja}
                value={texto}
                onChange={(e) => setTexto(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                    e.preventDefault();
                    construir();
                  }
                }}
                rows={3}
                autoFocus
                disabled={pensando}
                placeholder="Explica el precio por m² con el ingreso y la escolaridad, y grafica el ajuste."
                className="w-full resize-y rounded-xl2 border border-borde bg-tierra px-3.5 py-3
                           text-[14px] leading-relaxed text-crema placeholder:text-tenue/60
                           focus:border-salvia focus:outline-none disabled:opacity-60"
              />
              <div className="mt-2.5 flex flex-wrap items-center gap-2">
                <span className="text-[11px] text-tenue">
                  {leyenda ?? 'Lo arma, lo revisa y lo ejecuta. Tú lees el resultado.'}
                </span>
                <button
                  onClick={() => construir()}
                  disabled={pensando || texto.trim().length < 3}
                  className="ml-auto inline-flex items-center gap-1.5 rounded-lg bg-salvia px-4 py-2
                             text-[13px] font-medium text-tierra transition-colors
                             hover:bg-salviaProfunda disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {pensando ? (leyenda ?? 'Trabajando…') : 'Analizar'}
                  {!pensando && <IconoDerecha className="h-3.5 w-3.5" />}
                </button>
              </div>
              {problema && <div className="mt-2.5">{avisoProblema}</div>}
            </div>
          )}

          {disponible && !pensando && (
            <div className="mt-5">
              <p className="mb-2 text-center text-[11px] uppercase tracking-wide text-tenue">
                O prueba con una de éstas
              </p>
              <div className="flex flex-col gap-1.5">
                {SUGERENCIAS.map((s) => (
                  <button
                    key={s}
                    onClick={() => { setTexto(s); construir(s); }}
                    className="rounded-lg border border-bordeSuave bg-superficie/60 px-3.5 py-2.5 text-left
                               text-[12px] leading-relaxed text-tenue transition-colors
                               hover:border-salvia/40 hover:text-crema"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          <p className="mt-6 flex flex-wrap items-center justify-center gap-1.5 text-center text-[12px] text-tenue">
            <IconoSubir className="h-3.5 w-3.5" />
            ¿Tienes tus propios datos? Súbelos con
            <span className="text-salvia">Subir datos</span>
            {disponible ? 'y vuelve a preguntar.' : 'y ármalo a mano.'}
          </p>

          <p className="mt-2 text-center text-[12px] text-tenue">
            <button
              onClick={() => { ponerManual(true); irA('lienzo'); }}
              className="underline decoration-borde underline-offset-4 transition-colors hover:text-crema"
            >
              Prefiero armarlo a mano, bloque por bloque
            </button>
          </p>
        </div>
      </div>
    );
  }

  // --- Ya hay análisis: una barra fija, siempre en el mismo sitio -----------
  if (!disponible) return null;

  return (
    <div className="shrink-0 border-b border-borde bg-superficie2/60 px-4 py-2">
      <div className="mx-auto flex max-w-5xl items-center gap-2">
        <IconoIA className="h-4 w-4 shrink-0 text-salvia" />
        <textarea
          ref={caja}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); construir(); }
          }}
          rows={1}
          disabled={pensando}
          placeholder="Pide un cambio o un análisis nuevo: «ahora en logaritmos», «agrega la prueba de heterocedasticidad»…"
          className="min-w-0 flex-1 resize-none rounded-lg border border-borde bg-tierra px-3 py-1.5
                     text-[12px] leading-relaxed text-crema placeholder:text-tenue/60
                     focus:border-salvia focus:outline-none disabled:opacity-60"
        />
        <button
          onClick={() => construir()}
          disabled={pensando || texto.trim().length < 3}
          className="shrink-0 rounded-lg bg-salvia px-3.5 py-1.5 text-[12px] font-medium text-tierra
                     transition-colors hover:bg-salviaProfunda
                     disabled:cursor-not-allowed disabled:opacity-40"
        >
          {pensando ? (leyenda ?? 'Trabajando…') : 'Pedir'}
        </button>
      </div>
      {problema && <div className="mx-auto mt-2 max-w-5xl">{avisoProblema}</div>}
    </div>
  );
}
