'use client';

import { useMemo } from 'react';

import SubirArchivo from '@/components/panels/SubirArchivo';

import type { ColumnaEsquema, DescriptorNodo, EsquemaParam } from '@/lib/tipos';
import { usarLienzo } from '@/store/lienzo';

/**
 * El formulario de un nodo, generado del JSON Schema que manda el backend.
 *
 * Nada de esto está escrito a mano por herramienta: el esquema de Pydantic trae
 * los tipos, los rangos y los valores por omisión, y la pista `abak.control`
 * dice qué control dibujar. Por eso una herramienta nueva en el backend llega a
 * la interfaz con su formulario ya hecho.
 *
 * Los desplegables de columnas se llenan con el esquema PROPAGADO por el
 * compilador, no con las columnas del archivo original: muestran lo que de
 * verdad existe en ese punto del grafo, incluidas las columnas que crearon los
 * nodos de aguas arriba.
 */

interface Props {
  nodoId: string;
  descriptor: DescriptorNodo;
  params: Record<string, unknown>;
}

/** Pydantic escribe `str | None` como anyOf con null: aquí se desenvuelve. */
function desenvolver(campo: EsquemaParam): { campo: EsquemaParam; opcional: boolean } {
  if (!campo.anyOf) return { campo, opcional: false };
  const noNulos = campo.anyOf.filter((v) => v.type !== 'null');
  const literales = noNulos.filter((v) => v.const !== undefined).map((v) => v.const!);
  if (literales.length > 1) {
    return { campo: { ...campo, enum: literales }, opcional: noNulos.length !== campo.anyOf.length };
  }
  return {
    campo: { ...campo, ...(noNulos[0] ?? {}), anyOf: undefined },
    opcional: noNulos.length !== campo.anyOf.length,
  };
}

/**
 * La etiqueta que ve el usuario.
 *
 * Pydantic genera un `title` automático a partir del nombre del campo, con
 * Cada Palabra En Mayúscula: «volver_a_descargar» sale «Volver A Descargar»,
 * que en español se lee mal. Ese título automático se descarta y sólo se
 * respeta el que alguien escribió a mano.
 */
function etiquetaDe(clave: string, campo: EsquemaParam): string {
  const enOracion = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);
  const automatico = clave
    .split('_')
    .map((parte) => parte.charAt(0).toUpperCase() + parte.slice(1))
    .join(' ');
  if (campo.title && campo.title !== clave && campo.title !== automatico) return campo.title;
  return enOracion(clave.replace(/_/g, ' '));
}

export default function Formulario({ nodoId, descriptor, params }: Props) {
  const actualizar = usarLienzo((s) => s.actualizarParams);
  const esquemaDeEntrada = usarLienzo((s) => s.esquemaDeEntrada);
  const todos = usarLienzo((s) => s.diagnosticos);
  const diagnosticos = useMemo(() => todos.filter((d) => d.nodo_id === nodoId), [todos, nodoId]);

  const propiedades = descriptor.params_schema.properties ?? {};
  if (Object.keys(propiedades).length === 0) {
    return <p className="text-[12px] text-tenue">Esta herramienta no necesita configuración.</p>;
  }

  function columnasDe(campo: EsquemaParam, tipoPedido?: string | null): ColumnaEsquema[] {
    const puerto = campo.abak?.puerto ?? descriptor.entradas[0]?.nombre ?? 'datos';
    const esquema = esquemaDeEntrada(nodoId, puerto);
    if (!esquema) return [];
    const extra: ColumnaEsquema[] = [];
    // El índice temporal y el id de entidad no son columnas del DataFrame pero
    // sí se pueden usar: el backend los acepta y los gráficos los necesitan.
    for (const nombre of [esquema.indice_temporal, esquema.id_entidad]) {
      if (nombre && !esquema.columnas.some((c) => c.nombre === nombre)) {
        extra.push({ nombre, tipo: 'fecha', es_estimado: false, fuente: 'índice', nota: null });
      }
    }
    const todas = [...extra, ...esquema.columnas];
    const porTipo = tipoPedido ? todas.filter((c) => c.tipo === tipoPedido) : todas;

    // La columna explicada NO se ofrece como explicativa. Ponerla de los dos
    // lados da un ajuste perfecto —R² = 1, coeficiente 1, todo lo demás cero—
    // que parece un resultado buenísimo y no dice absolutamente nada. Es el
    // error clásico de quien empieza, y aquí simplemente no se puede cometer.
    const explicada = params['y'];
    if (typeof explicada === 'string' && explicada && campo.abak?.control === 'columnas') {
      return porTipo.filter((c) => c.nombre !== explicada);
    }
    return porTipo;
  }

  return (
    <div className="space-y-3">
      {Object.entries(propiedades).map(([clave, crudo]) => {
        const { campo, opcional } = desenvolver(crudo);
        const control = crudo.abak?.control ?? campo.abak?.control;
        // Un análisis guardado puede no traer todos los parámetros: el backend
        // les aplica el valor por omisión al validar, así que el formulario
        // tiene que enseñar ese mismo valor y no un campo vacío que miente.
        const valor = clave in params ? params[clave] : campo.default;
        const problema = diagnosticos.find((d) => d.param === clave);
        const poner = (v: unknown) => actualizar(nodoId, { [clave]: v });

        const etiqueta = (
          <label className="mb-1 block text-[11px] font-medium text-tenue">
            {etiquetaDe(clave, campo)}
            {opcional && <span className="ml-1 text-tenue/60">(opcional)</span>}
          </label>
        );

        const clase =
          `w-full rounded border bg-tierra px-2 py-1.5 text-[12px] text-crema focus:outline-none ` +
          (problema ? 'border-terracota focus:border-terracota' : 'border-borde focus:border-salvia');

        let control_jsx: React.ReactNode;

        if (control === 'columna') {
          const columnas = columnasDe(crudo, crudo.abak?.tipo_columna);
          control_jsx = (
            <select className={clase} value={(valor as string) ?? ''}
                    onChange={(e) => poner(e.target.value || null)}>
              <option value="">— elige una columna —</option>
              {columnas.map((c) => (
                <option key={c.nombre} value={c.nombre}>
                  {c.nombre}{c.es_estimado ? '  (estimado)' : ''}
                </option>
              ))}
            </select>
          );
          if (columnas.length === 0) {
            control_jsx = (
              <>
                {control_jsx}
                <p className="mt-1 text-[11px] text-tenue">
                  Conecta unos datos a este bloque para ver sus columnas.
                </p>
              </>
            );
          }
        } else if (control === 'columnas') {
          const columnas = columnasDe(crudo, crudo.abak?.tipo_columna);
          const elegidas = new Set((valor as string[]) ?? []);
          control_jsx = (
            <div className="max-h-52 overflow-y-auto rounded border border-borde bg-tierra p-1.5">
              {columnas.length === 0 && (
                <p className="px-1 py-2 text-[11px] text-tenue">
                  Conecta unos datos a este bloque para ver sus columnas.
                </p>
              )}
              {columnas.map((c) => (
                <label key={c.nombre}
                       className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 hover:bg-superficie2">
                  <input
                    type="checkbox"
                    checked={elegidas.has(c.nombre)}
                    onChange={(e) => {
                      const siguiente = new Set(elegidas);
                      if (e.target.checked) siguiente.add(c.nombre); else siguiente.delete(c.nombre);
                      // Se conserva el orden del esquema: el orden de las
                      // explicativas es el orden de la tabla de resultados.
                      poner(columnas.filter((x) => siguiente.has(x.nombre)).map((x) => x.nombre));
                    }}
                    className="accent-salvia"
                  />
                  <span className={`text-[12px] ${c.es_estimado ? 'estimado' : 'text-crema'}`}
                        title={c.es_estimado ? 'Dato estimado, no observado' : undefined}>
                    {c.nombre}
                  </span>
                  <span className="ml-auto text-[10px] text-tenue/70">{c.tipo}</span>
                </label>
              ))}
            </div>
          );
        } else if (control === 'arcos') {
          // Las flechas del grafo causal. Cada una es «causa->efecto».
          //
          // Se dibuja con dos desplegables por renglón y no con un cuadro de
          // texto a propósito: escribir nombres de columna a mano es la fuente
          // número uno de errores tontos, y el grafo causal es justo donde un
          // error tonto se convierte en una conclusión falsa bien presentada.
          const columnas = columnasDe(crudo);
          const flechas = ((valor as string[]) ?? []).map((a) => {
            const [causa = '', efecto = ''] = a.split('->');
            return { causa: causa.trim(), efecto: efecto.trim() };
          });
          // Se guardan TAMBIÉN las flechas a medio hacer. Filtrarlas aquí hacía
          // que el renglón desapareciera al elegir la causa, antes de poder
          // elegir el efecto: era imposible dibujar una flecha. El compilador
          // ignora las incompletas, y abajo se avisa de que están ahí.
          const guardar = (xs: { causa: string; efecto: string }[]) =>
            poner(xs.map((f) => `${f.causa}->${f.efecto}`));
          const incompletas = flechas.filter((f) => !f.causa || !f.efecto).length;

          control_jsx = (
            <div className="space-y-1.5">
              {columnas.length === 0 && (
                <p className="text-[11px] text-tenue">
                  Conecta unos datos a este bloque para ver sus columnas.
                </p>
              )}
              {/* Cada flecha ocupa dos renglones. Lado a lado no caben: el panel
                  mide ~310 px y «ingreso_hogar_mensual» se corta a la mitad, que
                  es justo lo que no puede pasar donde un nombre equivocado
                  cambia la conclusión. */}
              {flechas.map((f, i) => (
                <div key={i} className="rounded border border-borde bg-tierra p-1.5">
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-[10px] uppercase tracking-wide text-tenue">
                      Flecha {i + 1}
                    </span>
                    <button
                      type="button"
                      aria-label={`Quitar la flecha ${f.causa || '?'} a ${f.efecto || '?'}`}
                      onClick={() => guardar(flechas.filter((_, j) => j !== i))}
                      className="rounded px-1 text-[11px] text-tenue hover:text-arcilla"
                    >
                      ✕
                    </button>
                  </div>
                  <select
                    value={f.causa}
                    onChange={(e) => {
                      const xs = [...flechas]; xs[i] = { ...xs[i], causa: e.target.value };
                      guardar(xs);
                    }}
                    className="w-full rounded border border-borde bg-superficie px-2 py-1 text-[12px] text-crema"
                  >
                    <option value="">— causa —</option>
                    {columnas.map((c) => (
                      <option key={c.nombre} value={c.nombre}>
                        {c.nombre}{c.es_estimado ? '  (estimado)' : ''}
                      </option>
                    ))}
                  </select>
                  <div className="flex items-center gap-1.5 pt-1">
                    <span className="shrink-0 text-[13px] leading-none text-salvia" aria-hidden>↳</span>
                    <select
                      value={f.efecto}
                      onChange={(e) => {
                        const xs = [...flechas]; xs[i] = { ...xs[i], efecto: e.target.value };
                        guardar(xs);
                      }}
                      className="min-w-0 flex-1 rounded border border-borde bg-superficie px-2 py-1 text-[12px] text-crema"
                    >
                      <option value="">— efecto —</option>
                      {columnas.map((c) => (
                        <option key={c.nombre} value={c.nombre}>
                          {c.nombre}{c.es_estimado ? '  (estimado)' : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              ))}
              <button
                type="button"
                onClick={() => poner([...((valor as string[]) ?? []), '->'])}
                disabled={columnas.length === 0}
                className="w-full rounded border border-dashed border-borde px-2 py-1 text-[11px] text-tenue hover:border-salvia hover:text-salvia disabled:opacity-40"
              >
                + agregar flecha
              </button>
              {incompletas > 0 && (
                <p className="text-[11px] leading-relaxed text-ambar">
                  {incompletas === 1 ? 'Hay una flecha a medias y se ignora.'
                    : `Hay ${incompletas} flechas a medias y se ignoran.`}
                </p>
              )}
              <p className="text-[11px] leading-relaxed text-tenue">
                Dibuja lo que crees que causa qué. Abak decide sola qué controlar.
              </p>
            </div>
          );
        } else if (control === 'archivo') {
          control_jsx = <SubirArchivo nodoId={nodoId} />;
        } else if (clave === 'columnas' && descriptor.op === 'datos.csv') {
          // El esquema del archivo lo llena la subida; enseñarlo como un campo
          // editable invitaría a romperlo a mano.
          const columnas = (valor as { nombre: string }[] | undefined) ?? [];
          control_jsx = columnas.length ? (
            <p className="text-[11px] leading-snug text-tenue">
              {columnas.length} columnas leídas del archivo:{' '}
              {columnas.slice(0, 8).map((c) => c.nombre).join(', ')}
              {columnas.length > 8 ? '…' : ''}
            </p>
          ) : (
            <p className="text-[11px] text-tenue">Sube un archivo para ver sus columnas.</p>
          );
        } else if (clave === 'n_filas' && descriptor.op === 'datos.csv') {
          control_jsx = (
            <p className="text-[11px] text-tenue">
              {Number(valor ?? 0).toLocaleString('es-MX')} filas
            </p>
          );
        } else if (control === 'claves') {
          // Claves de una fuente oficial (series del SIE, indicadores del BIE).
          // Es texto libre porque los catálogos tienen miles de entradas, con
          // atajos para las que se piden todo el tiempo. El nodo muestra
          // después el título oficial que devolvió la fuente: si la clave está
          // mal, se ve en el resultado y no pasa inadvertida.
          const sugerencias = (crudo.abak?.sugerencias ?? {}) as Record<string, string>;
          const actuales = (valor as string[]) ?? [];
          control_jsx = (
            <>
              <input
                className={`${clase} font-mono`}
                value={actuales.join(', ')}
                placeholder="SF43718, SP1"
                onChange={(e) => poner(e.target.value.split(',').map((x) => x.trim()).filter(Boolean))}
              />
              {Object.keys(sugerencias).length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {Object.entries(sugerencias).map(([clave, texto]) => {
                    const puesta = actuales.includes(clave);
                    return (
                      <button
                        key={clave}
                        type="button"
                        title={texto}
                        onClick={() =>
                          poner(puesta ? actuales.filter((c) => c !== clave) : [...actuales, clave])
                        }
                        className={`rounded border px-1.5 py-0.5 font-mono text-[10px] transition-colors ${
                          puesta
                            ? 'border-salvia bg-salvia/15 text-salvia'
                            : 'border-borde text-tenue hover:text-crema'
                        }`}
                      >
                        {clave}
                      </button>
                    );
                  })}
                </div>
              )}
              <p className="mt-1 text-[11px] leading-snug text-tenue/80">
                Los atajos son sugerencias, no un catálogo verificado. Confirma siempre el título
                que aparece en el resultado.
              </p>
            </>
          );
        } else if (campo.enum) {
          const etiquetas = crudo.abak?.etiquetas ?? {};
          control_jsx = (
            <select className={clase} value={(valor as string) ?? ''}
                    onChange={(e) => poner(e.target.value)}>
              {opcional && <option value="">— ninguno —</option>}
              {campo.enum.map((v) => (
                <option key={v} value={v}>{etiquetas[v] ?? v.replace(/_/g, ' ')}</option>
              ))}
            </select>
          );
        } else if (campo.type === 'boolean') {
          // La casilla lleva el NOMBRE del parámetro. Antes usaba la
          // descripción y, cuando no había, decía «Sí»: una casilla que dice
          // «Sí» no informa de nada.
          control_jsx = (
            <label className="flex cursor-pointer items-start gap-2">
              <input type="checkbox" checked={Boolean(valor)} className="mt-0.5 accent-salvia"
                     onChange={(e) => poner(e.target.checked)} />
              <span className="text-[12px] leading-snug text-crema">
                {etiquetaDe(clave, campo)}
              </span>
            </label>
          );
        } else if (campo.type === 'integer' || campo.type === 'number') {
          const min = campo.minimum ?? campo.exclusiveMinimum;
          const max = campo.maximum ?? campo.exclusiveMaximum;
          control_jsx = (
            <input
              type="number" className={clase}
              value={valor === null || valor === undefined ? '' : String(valor)}
              min={min} max={max}
              step={campo.type === 'integer' ? 1 : 'any'}
              onChange={(e) => poner(e.target.value === '' ? null : Number(e.target.value))}
            />
          );
        } else if (campo.type === 'array') {
          control_jsx = (
            <input
              className={clase}
              value={((valor as string[]) ?? []).join(', ')}
              placeholder="separa con comas"
              onChange={(e) => poner(e.target.value.split(',').map((s) => s.trim()).filter(Boolean))}
            />
          );
        } else if (campo.type === 'object') {
          control_jsx = (
            <textarea
              className={`${clase} font-mono`} rows={3}
              value={JSON.stringify(valor ?? {}, null, 0)}
              onChange={(e) => { try { poner(JSON.parse(e.target.value)); } catch { /* aún escribiendo */ } }}
            />
          );
        } else {
          control_jsx = (
            <input className={clase} value={(valor as string) ?? ''}
                   onChange={(e) => poner(e.target.value || (opcional ? null : ''))} />
          );
        }

        return (
          <div key={clave}>
            {campo.type !== 'boolean' && control !== 'archivo' && etiqueta}
            {control_jsx}
            {campo.description && (
              <p className="mt-1 text-[11px] leading-snug text-tenue/80">{campo.description}</p>
            )}
            {problema && (
              <p className="mt-1 text-[11px] leading-snug text-arcilla">
                {problema.mensaje}{problema.sugerencia ? ` ${problema.sugerencia}` : ''}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
