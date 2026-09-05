'use client';

import { Handle, Position, type NodeProps } from '@xyflow/react';
import { memo, useMemo } from 'react';

import { usarLienzo, type NodoLienzo } from '@/store/lienzo';

const ESTADO_ETIQUETA: Record<string, { texto: string; clase: string }> = {
  corriendo: { texto: 'Corriendo…', clase: 'bg-acero/20 text-acero' },
  listo: { texto: 'Listo', clase: 'bg-salvia/20 text-salvia' },
  cacheado: { texto: 'Sin cambios', clase: 'bg-tenue/15 text-tenue' },
  error: { texto: 'Falló', clase: 'bg-terracota/25 text-arcilla' },
  omitido: { texto: 'No corrió', clase: 'bg-tenue/10 text-tenue' },
  en_cola: { texto: 'En cola', clase: 'bg-tenue/10 text-tenue' },
};

/**
 * Un bloque del lienzo.
 *
 * Muestra tres cosas de un vistazo, que son las que el usuario necesita sin
 * abrir nada: qué herramienta es (color y nombre de la familia), si está bien
 * configurada (borde rojo si no), y en qué estado quedó tras ejecutar.
 */
function NodoAbak({ id, data, selected }: NodeProps<NodoLienzo>) {
  const catalogo = usarLienzo((s) => s.catalogo);
  // Zustand v5 compara por identidad: un selector que devuelve `.filter(...)`
  // crea un arreglo nuevo en cada render y dispara un bucle infinito. Se
  // selecciona el arreglo estable y el filtrado se hace aqui.
  const todos = usarLienzo((s) => s.diagnosticos);
  const diagnosticos = useMemo(() => todos.filter((d) => d.nodo_id === id), [todos, id]);
  const resultado = usarLienzo((s) => s.resultadoDe(id));
  const podado = usarLienzo((s) => s.podados.includes(id));

  const descriptor = catalogo?.nodos.find((n) => n.op === data.op);
  const familia = catalogo?.familias.find((f) => f.id === descriptor?.familia);
  const tipos = catalogo?.tipos ?? {};
  const color = familia?.color ?? '#6b6259';

  const errores = diagnosticos.filter((d) => d.severidad === 'error');
  const estado = resultado?.estado;
  const insignia = estado ? ESTADO_ETIQUETA[estado] : null;

  const borde = errores.length ? 'border-terracota'
    : selected ? 'border-salvia'
    : estado === 'error' ? 'border-terracota/70'
    : 'border-borde';

  return (
    <div
      className={`tarjeta-nodo w-[248px] rounded-lg border ${borde} bg-superficie shadow-nodo ${
        podado ? 'opacity-45' : ''
      }`}
      title={podado ? 'Este bloque no alimenta ningún resultado, así que no se ejecuta.' : undefined}
    >
      <div className="h-1 rounded-t-lg" style={{ background: color }} />

      <div className="px-3 pb-2 pt-2">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-[10px] uppercase tracking-wide" style={{ color }}>
            {familia?.titulo ?? '—'}
          </span>
          {insignia && (
            <span className={`rounded px-1.5 py-0.5 text-[10px] ${insignia.clase}`}>
              {insignia.texto}
              {resultado?.ms ? ` · ${resultado.ms} ms` : ''}
            </span>
          )}
        </div>

        <div className="mt-0.5 truncate text-[13px] font-medium text-crema" title={data.etiqueta}>
          {data.etiqueta || descriptor?.titulo || data.op}
        </div>
        {data.etiqueta !== descriptor?.titulo && (
          <div className="truncate text-[11px] text-tenue">{descriptor?.titulo}</div>
        )}

        {errores.length > 0 && (
          <div className="mt-1.5 rounded bg-terracota/12 px-2 py-1 text-[11px] leading-snug text-arcilla">
            {errores[0].mensaje}
          </div>
        )}
        {estado === 'error' && resultado?.error && (
          <div className="mt-1.5 rounded bg-terracota/12 px-2 py-1 text-[11px] leading-snug text-arcilla">
            {resultado.error.titulo}
          </div>
        )}
      </div>

      {/* Puertos de entrada: a la izquierda, con su tipo explicado al pasar el cursor. */}
      {descriptor?.entradas.map((p, i) => (
        <Handle
          key={`e-${p.nombre}`}
          type="target"
          position={Position.Left}
          id={p.nombre}
          style={{
            top: 42 + i * 20,
            background: tipos[p.tipo]?.color ?? '#6b6259',
            opacity: p.requerido ? 1 : 0.55,
          }}
          title={`${p.titulo ?? p.nombre} — ${p.ayuda_tipo}${p.requerido ? '' : ' (opcional)'}`}
        />
      ))}

      {/* Puertos de salida: a la derecha. */}
      {descriptor?.salidas.map((p, i) => (
        <Handle
          key={`s-${p.nombre}`}
          type="source"
          position={Position.Right}
          id={p.nombre}
          style={{ top: 42 + i * 20, background: tipos[p.tipo]?.color ?? '#6b6259' }}
          title={`${p.titulo ?? p.nombre} — ${p.ayuda_tipo}`}
        />
      ))}
    </div>
  );
}

export default memo(NodoAbak);
