'use client';

import { useMemo, useRef, useState } from 'react';

import BotonPdf from '@/components/ui/BotonPdf';
import Explicacion from '@/components/ui/Explicacion';
import Grafica from '@/components/ui/Grafica';
import { IconoAbajo } from '@/components/ui/Icono';
import Proyeccion from '@/components/ui/Proyeccion';
import Tabla from '@/components/ui/Tabla';
import TablaModelo from '@/components/ui/TablaModelo';
import { num } from '@/lib/formato';
import type { Artefacto } from '@/lib/tipos';
import { usarLienzo } from '@/store/lienzo';

export function RenderArtefacto({ artefacto }: { artefacto: Artefacto }) {
  switch (artefacto.tipo) {
    case 'tabla': return <Tabla artefacto={artefacto} />;
    case 'modelo': return <TablaModelo artefacto={artefacto} />;
    case 'figura': return <Grafica artefacto={artefacto} />;
    case 'proyeccion': return <Proyeccion artefacto={artefacto} />;
    case 'escalar':
      return (
        <div className="inline-flex items-center rounded-lg border border-borde bg-superficie px-4 py-2.5 text-[13px]">
          <span className="text-tenue">{artefacto.titulo}</span>
          <Explicacion clave={artefacto.titulo ?? ''} />
          <span className="ml-2 text-crema">{String(artefacto.valor)}</span>
        </div>
      );
    case 'detalle':
      return (
        <div className="rounded-lg border border-borde bg-superficie">
          <div className="border-b border-borde px-4 py-2.5 text-[13px] font-medium text-crema">
            {artefacto.titulo}
          </div>
          <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-6 gap-y-2 px-4 py-3 text-[12px]">
            {Object.entries(artefacto.datos).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="inline-flex items-start text-tenue">
                  <span className="leading-relaxed">{k.replace(/_/g, ' ')}</span>
                  <Explicacion clave={k} />
                </dt>
                <dd className="text-right leading-relaxed text-crema">
                  {typeof v === 'number' ? num(v) : String(v)}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      );
    default:
      return (
        <pre className="overflow-x-auto rounded border border-borde bg-superficie p-3 text-[11px] text-tenue">
          {artefacto.tipo === 'objeto' ? artefacto.texto : JSON.stringify(artefacto, null, 2)}
        </pre>
      );
  }
}

/**
 * Lo que se preguntó y lo que la IA entendió, encima de las tablas.
 *
 * Aterrizar directo en el resultado ahorra el paso de descubrir «Ejecutar»,
 * pero deja a la persona frente a una regresión sin contexto. Este bloque
 * cierra esa distancia: la frase que escribió, lo que Abak armó con ella, y en
 * ámbar lo que conviene mirar con desconfianza.
 */
function RespuestaDeLaIA() {
  const respuesta = usarLienzo((s) => s.respuestaIA);
  const irA = usarLienzo((s) => s.irA);
  if (!respuesta) return null;

  return (
    <div className="mb-6 rounded-xl2 border border-borde bg-superficie p-4">
      <p className="text-[11px] uppercase tracking-[0.14em] text-tenue">Preguntaste</p>
      <p className="mt-1 text-[14px] leading-relaxed text-crema">«{respuesta.peticion}»</p>
      <p className="mt-3 text-[12px] uppercase tracking-[0.14em] text-tenue">Esto se hizo</p>
      <p className="mt-1 text-[13px] leading-relaxed text-crema/90">{respuesta.explicacion}</p>
      {respuesta.advertencias.length > 0 && (
        <ul className="mt-3 space-y-1 border-t border-borde pt-3">
          {respuesta.advertencias.map((a, i) => (
            <li key={i} className="text-[12px] leading-relaxed text-ambar">{a}</li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          onClick={() => irA('lienzo')}
          className="rounded-lg border border-borde px-2.5 py-1 text-[11px] text-tenue
                     transition-colors hover:border-salvia/50 hover:text-crema"
        >
          Ver los pasos
        </button>
        <button
          onClick={() => irA('metodologia')}
          className="rounded-lg border border-borde px-2.5 py-1 text-[11px] text-tenue
                     transition-colors hover:border-salvia/50 hover:text-crema"
        >
          Cómo se hizo
        </button>
      </div>
    </div>
  );
}

/** Familias que sólo preparan el terreno: su tabla no es la respuesta. */
const PREPARAN = new Set(['datos', 'fuentes', 'transformar', 'graficos', 'salida']);
/** Familias que estiman algo. Cuentan para «N estimaciones»; `explorar` no. */
const ESTIMAN = new Set(['econometria', 'causal', 'series', 'espacial', 'macro',
                         'inmobiliario', 'ml']);

export default function PanelResultados() {
  const [verIntermedios, setVerIntermedios] = useState(false);
  const ejecucion = usarLienzo((s) => s.ejecucion);
  const ejecutando = usarLienzo((s) => s.ejecutando);
  const errorEjecucion = usarLienzo((s) => s.errorEjecucion);
  const orden = usarLienzo((s) => s.orden);
  const seleccionar = usarLienzo((s) => s.seleccionar);
  const irA = usarLienzo((s) => s.irA);
  const ejecutar = usarLienzo((s) => s.ejecutar);
  const hayNodos = usarLienzo((s) => s.nodos.length > 0);
  const nodos = usarLienzo((s) => s.nodos);
  const descriptor = usarLienzo((s) => s.descriptor);
  const secciones = useRef<Record<string, HTMLElement | null>>({});

  const ids = useMemo(
    () => (orden.length ? orden : Object.keys(ejecucion?.nodos ?? {})),
    [orden, ejecucion],
  );

  /**
   * Los pasos que de verdad enseñan algo, ya clasificados.
   *
   * `clase` separa lo que se estimó de lo que sólo preparó datos. Un análisis
   * real trae doce pasos y sólo dos o tres son el resultado; sin esa marca hay
   * que bajar leyendo tabla por tabla hasta dar con el modelo.
   *
   * La clase sale de la FAMILIA de la herramienta, no del tipo de artefacto
   * que devuelve. Se intentó por artefacto y clasificaba mal: las pruebas de
   * supuestos devuelven una tabla, igual que un `head()`, y acababan en el
   * montón de «preparar datos» aunque sean parte de la respuesta.
   */
  const familia = useMemo(() => {
    const m: Record<string, string> = {};
    for (const n of nodos) m[n.id] = descriptor(n.data.op)?.familia ?? '';
    return m;
  }, [nodos, descriptor]);

  const pasos = useMemo(() => {
    if (!ejecucion) return [];
    return ids.flatMap((id) => {
      const r = ejecucion.nodos[id];
      if (!r) return [];
      // Las figuras ya NO se filtran. Vivían sólo en la pestaña «Gráficos», y
      // eso obligaba a leer la tabla en una pantalla y su gráfica en otra: la
      // gráfica de coeficientes explica la tabla que tiene justo encima.
      const artefactos = Object.entries(r.artefactos ?? {});
      if (!artefactos.length && !r.error) return [];
      const f = familia[id];
      const clase: 'error' | 'modelo' | 'dato' = r.error
        ? 'error'
        : f
          ? (PREPARAN.has(f) ? 'dato' : 'modelo')
          // Sin catálogo cargado se cae al criterio antiguo, que acierta en la
          // mayoría de los casos y nunca deja un paso fuera de la lista.
          : artefactos.some(([, a]) => a.tipo === 'modelo' || a.tipo === 'detalle')
            ? 'modelo'
            : 'dato';
      return [{ id, r, artefactos, clase }];
    });
  }, [ejecucion, ids, familia]);

  if (!ejecucion) {
    return (
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-3xl p-4 pt-6">
          <RespuestaDeLaIA />
          <div className="rounded-xl2 border border-borde bg-superficie p-5 text-center">
            <p className="text-[13px] leading-relaxed text-tenue">
              {ejecutando
                ? 'Ejecutando el análisis. Los resultados aparecen aquí en cuanto terminen.'
                : errorEjecucion
                  ? errorEjecucion
                  : hayNodos
                    ? 'El análisis está armado pero todavía no se ha corrido.'
                    : 'Todavía no hay nada que mostrar. Escribe qué quieres analizar.'}
            </p>
            {/* Un panel vacío que sólo describe el problema obliga a salir a
                buscar el botón. Si lo que falta es ejecutar, se ejecuta aquí. */}
            {hayNodos && !ejecutando && (
              <button
                onClick={() => ejecutar(undefined, { llevarAResultados: true })}
                className="mt-3 rounded-lg bg-salvia px-4 py-2 text-[13px] font-medium text-tierra
                           transition-colors hover:bg-salviaProfunda"
              >
                Ejecutar ahora
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  const estimados = pasos.filter((x) => ESTIMAN.has(familia[x.id])).length;
  const conError = pasos.filter((x) => x.clase === 'error').length;

  // Lo que contesta la pregunta arriba (errores y estimaciones, en el orden del
  // análisis); lo que sólo preparó datos, al final y plegado. Reordenar este
  // bloque no cambia lo que se hizo: el orden real sigue en el lienzo, en el
  // código y en la nota metodológica, y las pastillas de arriba también.
  // Cuatro escalones, no dos: los errores primero, luego lo que ESTIMA, luego
  // lo que sólo describe, y al final lo que preparó datos. Sin el escalón de en
  // medio, «Descriptivos» quedaba encima del modelo que contesta la pregunta.
  const peso = (x: { id: string; clase: string }) =>
    x.clase === 'error' ? 0 : ESTIMAN.has(familia[x.id]) ? 1 : x.clase === 'modelo' ? 2 : 3;
  const ordenados = [...pasos].sort((a, b) => peso(a) - peso(b));
  const corte = ordenados.findIndex((x) => x.clase === 'dato');
  const primerIntermedio = corte > 0 ? corte : -1;
  const intermedios = primerIntermedio >= 0 ? ordenados.length - primerIntermedio : 0;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl p-4">
        <RespuestaDeLaIA />
        <div className="sticky top-0 z-20 -mx-4 mb-6 border-b border-borde bg-tierra/95 px-4 pb-3 pt-1 backdrop-blur">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <span className="text-[12px] text-tenue">
              {pasos.length} paso{pasos.length === 1 ? '' : 's'} con resultado
              {estimados > 0 && <> · {estimados} estimación{estimados === 1 ? '' : 'es'}</>}
              {conError > 0 && <span className="text-arcilla"> · {conError} con error</span>}
            </span>
            <div className="ml-auto">
              <BotonPdf completo etiqueta="Informe completo en PDF" />
            </div>
          </div>

          {pasos.length > 1 && (
            <nav aria-label="Ir a un resultado" className="mt-2 flex flex-wrap gap-1.5">
              {pasos.map(({ id, r, clase }) => (
                <button
                  key={id}
                  onClick={() => {
                    if (clase === 'dato') setVerIntermedios(true);
                    requestAnimationFrame(() => secciones.current[id]?.scrollIntoView({
                      behavior: 'smooth', block: 'start',
                    }));
                  }}
                  title={r.etiqueta ?? id}
                  className={`max-w-[15rem] truncate rounded-full border px-2.5 py-1 text-[11px]
                              transition-colors ${
                    clase === 'error'
                      ? 'border-terracota/50 text-arcilla hover:bg-terracota/10'
                      : clase === 'modelo'
                        ? 'border-salvia/50 text-salvia hover:bg-salvia/10'
                        : 'border-borde text-tenue hover:border-salvia/50 hover:text-crema'
                  }`}
                >
                  {r.etiqueta ?? id}
                </button>
              ))}
            </nav>
          )}
        </div>

        <div className="space-y-6">
          {ordenados.map(({ id, r, artefactos, clase }, i) => (
            <div key={id} className="contents">
              {/* La pregunta era «explícame el precio», y la respuesta es el
                  modelo. Antes lo primero en pantalla era la tabla de 32
                  renglones que sólo sirvió para llegar hasta él: había que
                  bajar cuatro pantallas para leer lo que se preguntó. */}
              {i === primerIntermedio && (
                <button
                  onClick={() => setVerIntermedios((v) => !v)}
                  className="flex w-full items-center gap-2 rounded-xl2 border border-borde
                             bg-superficie px-3.5 py-2.5 text-left text-[12px] text-tenue
                             transition-colors hover:border-salvia/40 hover:text-crema"
                >
                  <IconoAbajo className={`h-3 w-3 transition-transform ${verIntermedios ? '' : '-rotate-90'}`} />
                  {/* Rotulado en una sola expresión: partido en varias líneas,
                      JSX come el salto entre el texto y la interpolación y sale
                      «pasosque prepararon». */}
                  {`${verIntermedios ? 'Ocultar' : 'Ver'} los ${intermedios} `
                    + `${intermedios === 1 ? 'paso' : 'pasos'} que prepararon los datos`}
                </button>
              )}
            <section
              ref={(el) => { secciones.current[id] = el; }}
              hidden={primerIntermedio >= 0 && i >= primerIntermedio && !verIntermedios}
              className="scroll-mt-24"
            >
              <div className="mb-2 flex items-baseline gap-2">
                <span
                  aria-hidden
                  className={`h-1.5 w-1.5 shrink-0 translate-y-[-2px] rounded-full ${
                    clase === 'error' ? 'bg-terracota'
                      : clase === 'modelo' ? 'bg-salvia' : 'bg-borde'
                  }`}
                />
                <button onClick={() => { seleccionar(id); irA('lienzo'); }}
                        title="Ver este bloque en el lienzo"
                        className="text-[14px] font-medium text-crema hover:text-salvia">
                  {r.etiqueta ?? id}
                </button>
                {r.ms !== undefined && <span className="text-[11px] text-tenue">{r.ms} ms</span>}
                <div className="ml-auto">
                  <BotonPdf nodo={id} />
                </div>
              </div>
              {r.error && (
                <div className="rounded border border-terracota/40 bg-terracota/8 p-3">
                  <p className="text-[13px] font-medium text-arcilla">{r.error.titulo}</p>
                  <p className="mt-1 text-[12px] text-crema/85">{r.error.detalle}</p>
                  {r.error.sugerencia && (
                    <p className="mt-2 text-[12px] text-crema/75">{r.error.sugerencia}</p>
                  )}
                </div>
              )}
              <div className="space-y-3">
                {artefactos.map(([puerto, a]) => (
                  <RenderArtefacto key={puerto} artefacto={a} />
                ))}
              </div>
            </section>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function Vacio({ texto }: { texto: string }) {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <p className="max-w-md text-center text-[13px] leading-relaxed text-tenue">{texto}</p>
    </div>
  );
}
