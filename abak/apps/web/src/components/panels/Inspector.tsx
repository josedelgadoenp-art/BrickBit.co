'use client';

import { useState } from 'react';

import Formulario from '@/components/panels/Formulario';
import { usarLienzo } from '@/store/lienzo';

type Solapa = 'configurar' | 'que_es' | 'resultado';

const NOMBRE_SISTEMA: Record<string, string> = {
  stata: 'Stata', r: 'R', spss: 'SPSS', eviews: 'EViews', python: 'Python',
};

/**
 * El panel derecho: configurar la herramienta y entender qué es.
 *
 * La solapa «Qué es» es la respuesta al problema que hunde a SPSS y a EViews:
 * el usuario encuentra el menú, corre el procedimiento y no sabe leer lo que
 * salió. Aquí, cada herramienta trae qué hace, cuándo usarla, cómo se
 * interpreta su resultado, qué supuestos impone y cómo se llama en el sistema
 * que la persona ya conocía.
 */
export default function Inspector() {
  const seleccionado = usarLienzo((s) => s.seleccionado);
  const nodo = usarLienzo((s) => s.nodos.find((n) => n.id === s.seleccionado));
  const descriptor = usarLienzo((s) => (nodo ? s.descriptor(nodo.data.op) : undefined));
  const catalogo = usarLienzo((s) => s.catalogo);
  const resultado = usarLienzo((s) => (seleccionado ? s.resultadoDe(seleccionado) : undefined));
  const { renombrar, ponerNotas, borrarNodo, duplicarNodo, ejecutar, irA } = usarLienzo();
  const [solapa, setSolapa] = useState<Solapa>('configurar');

  if (!nodo || !descriptor) {
    return (
      <aside className="w-[336px] shrink-0 border-l border-borde bg-superficie p-4">
        <p className="text-[13px] text-tenue">
          Elige un bloque del lienzo para configurarlo y ver qué hace.
        </p>
        <div className="mt-4 space-y-2 text-[12px] leading-relaxed text-tenue/80">
          <p className="text-crema">Cómo se arma un análisis</p>
          <p>1 · Trae datos (un archivo tuyo o un ejemplo).</p>
          <p>2 · Prepáralos: filtra, crea variables, declara si es serie o panel.</p>
          <p>3 · Estima: una regresión, un modelo espacial, un pronóstico.</p>
          <p>4 · Revisa los supuestos y grafica.</p>
          <p className="pt-2 text-tenue/70">
            El código de Python se va escribiendo solo mientras armas el lienzo. Está en la
            pestaña <span className="text-salvia">Código</span>, y es el mismo que se ejecuta.
          </p>
        </div>
      </aside>
    );
  }

  const familia = catalogo?.familias.find((f) => f.id === descriptor.familia);
  const ayuda = descriptor.ayuda;
  const equivalentes = Object.entries(ayuda.equivalente);

  return (
    <aside className="flex w-[336px] shrink-0 flex-col border-l border-borde bg-superficie">
      <div className="border-b border-borde p-3">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ background: familia?.color }} />
          <span className="text-[11px] uppercase tracking-wide" style={{ color: familia?.color }}>
            {familia?.titulo}
          </span>
          <span className="ml-auto font-mono text-[10px] text-tenue/60">v{descriptor.version}</span>
        </div>
        <input
          value={nodo.data.etiqueta}
          onChange={(e) => renombrar(nodo.id, e.target.value)}
          className="mt-1.5 w-full rounded border border-transparent bg-transparent px-1 py-0.5 text-[14px] font-medium text-crema hover:border-borde focus:border-salvia focus:outline-none"
          title="Este nombre es el que lleva la variable en el código generado"
        />
        <p className="px-1 text-[11px] text-tenue">{descriptor.titulo}</p>
      </div>

      <nav className="flex border-b border-borde">
        {([['configurar', 'Configurar'], ['que_es', 'Qué es'], ['resultado', 'Resultado']] as const).map(
          ([id, texto]) => (
            <button
              key={id}
              onClick={() => setSolapa(id)}
              className={`flex-1 border-b-2 px-2 py-2 text-[12px] transition-colors ${
                solapa === id
                  ? 'border-salvia text-crema'
                  : 'border-transparent text-tenue hover:text-crema'
              }`}
            >
              {texto}
            </button>
          ),
        )}
      </nav>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {solapa === 'configurar' && (
          <>
            <Formulario nodoId={nodo.id} descriptor={descriptor} params={nodo.data.params} />
            <div className="mt-4">
              <label className="mb-1 block text-[11px] font-medium text-tenue">
                Nota de este paso
              </label>
              <textarea
                rows={2}
                value={nodo.data.notas ?? ''}
                onChange={(e) => ponerNotas(nodo.id, e.target.value)}
                placeholder="Por qué hiciste esto. Aparece como comentario en el código y en la metodología."
                className="w-full rounded border border-borde bg-tierra px-2 py-1.5 text-[12px] text-crema placeholder:text-tenue/60 focus:border-salvia focus:outline-none"
              />
            </div>
            <div className="mt-4 flex gap-2">
              <button onClick={() => ejecutar(nodo.id)}
                      className="flex-1 rounded border border-borde px-2 py-1.5 text-[12px] text-crema hover:border-salvia"
                      title="Ejecuta sólo lo necesario para llegar hasta este bloque">
                Ejecutar hasta aquí
              </button>
              <button onClick={() => duplicarNodo(nodo.id)}
                      className="rounded border border-borde px-2 py-1.5 text-[12px] text-tenue hover:text-crema">
                Duplicar
              </button>
              <button onClick={() => borrarNodo(nodo.id)}
                      className="rounded border border-borde px-2 py-1.5 text-[12px] text-arcilla hover:border-terracota">
                Borrar
              </button>
            </div>
          </>
        )}

        {solapa === 'que_es' && (
          <div className="space-y-4 text-[12px] leading-relaxed">
            <section>
              <h3 className="mb-1 text-[11px] uppercase tracking-wide text-tenue">Qué hace</h3>
              <p className="text-crema">{ayuda.que_hace}</p>
            </section>
            <section>
              <h3 className="mb-1 text-[11px] uppercase tracking-wide text-tenue">Cuándo usarlo</h3>
              <p className="text-crema/90">{ayuda.cuando_usarlo}</p>
            </section>
            <section>
              <h3 className="mb-1 text-[11px] uppercase tracking-wide text-tenue">
                Cómo se lee el resultado
              </h3>
              <p className="text-crema/90">{ayuda.interpretacion}</p>
            </section>

            {ayuda.supuestos.length > 0 && (
              <section>
                <h3 className="mb-1 text-[11px] uppercase tracking-wide text-tenue">
                  Supuestos que impone
                </h3>
                <ul className="space-y-1">
                  {ayuda.supuestos.map((s, i) => (
                    <li key={i} className="flex gap-2 text-crema/85">
                      <span className="text-salvia">·</span>{s}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {ayuda.advertencias.length > 0 && (
              <section className="rounded border border-ambar/30 bg-ambar/5 p-2.5">
                <h3 className="mb-1 text-[11px] uppercase tracking-wide text-ambar">Ten cuidado con</h3>
                <ul className="space-y-1.5">
                  {ayuda.advertencias.map((a, i) => (
                    <li key={i} className="text-crema/85">{a}</li>
                  ))}
                </ul>
              </section>
            )}

            {equivalentes.length > 0 && (
              <section>
                <h3 className="mb-1 text-[11px] uppercase tracking-wide text-tenue">
                  Si vienes de otro sistema
                </h3>
                <div className="space-y-1">
                  {equivalentes.map(([sistema, comando]) => (
                    <div key={sistema} className="flex gap-2">
                      <span className="w-16 shrink-0 text-tenue">{NOMBRE_SISTEMA[sistema] ?? sistema}</span>
                      <code className="font-mono text-[11px] text-salvia">{comando}</code>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {ayuda.referencia && (
              <section>
                <h3 className="mb-1 text-[11px] uppercase tracking-wide text-tenue">Para leer más</h3>
                <p className="text-crema/80">{ayuda.referencia}</p>
              </section>
            )}

            <section>
              <h3 className="mb-1 text-[11px] uppercase tracking-wide text-tenue">Qué recibe y qué entrega</h3>
              <div className="space-y-1">
                {descriptor.entradas.map((p) => (
                  <div key={p.nombre} className="flex gap-2">
                    <span className="w-4 shrink-0 text-tenue">←</span>
                    <span className="text-crema">{p.titulo ?? p.nombre}</span>
                    <span className="ml-auto text-right text-[11px] text-tenue">{p.ayuda_tipo}</span>
                  </div>
                ))}
                {descriptor.salidas.map((p) => (
                  <div key={p.nombre} className="flex gap-2">
                    <span className="w-4 shrink-0 text-tenue">→</span>
                    <span className="text-crema">{p.titulo ?? p.nombre}</span>
                    <span className="ml-auto text-right text-[11px] text-tenue">{p.ayuda_tipo}</span>
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}

        {solapa === 'resultado' && (
          <div className="text-[12px]">
            {!resultado && (
              <p className="text-tenue">
                Este bloque todavía no se ha ejecutado. Usa «Ejecutar» arriba, o «Ejecutar hasta aquí»
                en la solapa Configurar.
              </p>
            )}
            {resultado?.error && (
              <div className="space-y-2">
                <p className="font-medium text-arcilla">{resultado.error.titulo}</p>
                <p className="text-crema/85">{resultado.error.detalle}</p>
                {resultado.error.sugerencia && (
                  <p className="rounded border border-borde bg-tierra p-2 text-crema/80">
                    {resultado.error.sugerencia}
                  </p>
                )}
                <button onClick={() => irA('bitacora')} className="text-salvia underline">
                  Ver el detalle técnico en la bitácora
                </button>
              </div>
            )}
            {resultado && !resultado.error && (
              <div className="space-y-2">
                <p className="text-tenue">
                  Estado: <span className="text-crema">{resultado.estado}</span>
                  {resultado.ms !== undefined && ` · ${resultado.ms} ms`}
                </p>
                <p className="text-tenue">
                  Produjo: {Object.keys(resultado.artefactos ?? {}).join(', ') || '—'}
                </p>
                <button onClick={() => irA('resultados')} className="text-salvia underline">
                  Ver los resultados completos
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
