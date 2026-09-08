'use client';

import { useEffect, useState } from 'react';

import Lienzo from '@/components/canvas/Lienzo';
import Asistente from '@/components/panels/Asistente';
import PanelBitacora from '@/components/panels/PanelBitacora';
import PanelCodigo from '@/components/panels/PanelCodigo';
import PanelDatos from '@/components/panels/PanelDatos';
import PanelEspecificaciones from '@/components/panels/PanelEspecificaciones';
import PanelGraficos from '@/components/panels/PanelGraficos';
import PanelMetodologia from '@/components/panels/PanelMetodologia';
import PanelResultados from '@/components/panels/PanelResultados';
import { IconoAbajo } from '@/components/ui/Icono';
import { usarLienzo, type Pestana } from '@/store/lienzo';

/**
 * Las pestañas del área de trabajo.
 *
 * Eran ocho, todas del mismo tamaño y todas al mismo nivel. Ocho puertas
 * iguales no son una elección, son un examen: quien llega no sabe cuál abrir y
 * la única forma de averiguarlo es abrirlas todas. Ahora hay cuatro a la vista
 * —las que responden «¿qué salió?» y «¿con qué?»— y las cuatro de auditoría
 * viven dentro de «Cómo se hizo», que es la pregunta que contestan.
 *
 * Y cuando no hay nada armado no se muestra ninguna: no hay ocho pestañas
 * vacías, hay una pregunta.
 */
const PRINCIPALES: { id: Pestana; texto: string; ayuda: string }[] = [
  { id: 'resultados', texto: 'Resultado', ayuda: 'La respuesta: modelos, pruebas y tablas' },
  { id: 'graficos', texto: 'Gráficos', ayuda: 'Las figuras que produjo el análisis' },
  { id: 'lienzo', texto: 'Análisis', ayuda: 'Los pasos, conectados. Aquí se corrige.' },
  { id: 'datos', texto: 'Datos', ayuda: 'Las tablas en cada punto del análisis' },
];

const DETALLE: { id: Pestana; texto: string; ayuda: string }[] = [
  { id: 'metodologia', texto: 'Metodología', ayuda: 'Qué se hizo, con qué supuestos y advertencias' },
  { id: 'codigo', texto: 'Código', ayuda: 'El Python que se ejecuta. Es el mismo que exportas.' },
  { id: 'especificaciones', texto: 'Especificaciones',
    ayuda: 'Cuántos modelos probaste antes de reportar uno, y cómo se mueve cada coeficiente' },
  { id: 'bitacora', texto: 'Bitácora', ayuda: 'El detalle técnico, incluidos los errores completos' },
];

/**
 * Dónde va uno en la ruta.
 *
 * Tres pasos, siempre los mismos, siempre en el mismo orden: se pregunta, se
 * analiza, se lee el resultado. Sin esto la pantalla cambia sola después de
 * ejecutar y no queda claro por qué.
 */
function Pasos() {
  const ejecutando = usarLienzo((s) => s.ejecutando);
  const estado = usarLienzo((s) => s.ejecucion?.estado);
  const listo = estado === 'listo' || estado === 'error';

  const paso = ejecutando ? 2 : listo ? 3 : 2;
  const nombres = ['Pregunta', 'Análisis', 'Resultado'];

  return (
    <div className="ml-auto hidden items-center gap-1.5 pr-1 lg:flex">
      {nombres.map((n, i) => {
        const numero = i + 1;
        const hecho = numero < paso || (numero === 3 && listo);
        const activo = numero === paso;
        return (
          <span key={n} className="flex items-center gap-1.5">
            {i > 0 && <span aria-hidden className="text-[10px] text-borde">›</span>}
            <span className={`text-[11px] ${
              activo ? 'text-salvia' : hecho ? 'text-tenue' : 'text-tenue/50'
            }`}>
              {numero}. {n}
              {numero === 2 && ejecutando && '…'}
            </span>
          </span>
        );
      })}
    </div>
  );
}

export default function Pestanas() {
  const pestana = usarLienzo((s) => s.pestana);
  const irA = usarLienzo((s) => s.irA);
  const pedirCodigo = usarLienzo((s) => s.pedirCodigo);
  const pedirMetodologia = usarLienzo((s) => s.pedirMetodologia);
  const nodos = usarLienzo((s) => s.nodos.length);
  const ejecucion = usarLienzo((s) => s.ejecucion);
  const manual = usarLienzo((s) => s.manual);
  const [abierto, setAbierto] = useState(false);

  useEffect(() => {
    if (pestana === 'codigo' && nodos) pedirCodigo();
    if (pestana === 'metodologia' && nodos) pedirMetodologia();
  }, [pestana, nodos, pedirCodigo, pedirMetodologia]);

  const cuentaFiguras = Object.values(ejecucion?.nodos ?? {}).reduce(
    (n, r) => n + Object.values(r.artefactos ?? {}).filter((a) => a.tipo === 'figura').length, 0);

  // Sin nada armado, la pregunta es la pantalla completa. Salvo que la persona
  // haya pedido el taller: entonces manda ella.
  if (nodos === 0 && !manual) {
    return <div className="min-h-0 flex-1 overflow-hidden"><Asistente modo="portada" /></div>;
  }

  const enDetalle = DETALLE.some((d) => d.id === pestana);

  return (
    <>
      <nav className="flex shrink-0 items-center gap-0.5 border-b border-borde bg-superficie px-2">
        {PRINCIPALES.map((p) => {
          const activa = p.id === pestana;
          return (
            <button
              key={p.id}
              onClick={() => irA(p.id)}
              title={p.ayuda}
              className={`border-b-2 px-3 py-2 text-[12px] transition-colors ${
                activa ? 'border-salvia text-crema' : 'border-transparent text-tenue hover:text-crema'
              }`}
            >
              {p.texto}
              {p.id === 'graficos' && cuentaFiguras > 0 && (
                <span className="ml-1.5 rounded bg-borde px-1 text-[10px] text-tenue">
                  {cuentaFiguras}
                </span>
              )}
            </button>
          );
        })}

        <div className="relative">
          <button
            onClick={() => setAbierto((v) => !v)}
            aria-label="Cómo se hizo"
            aria-expanded={abierto}
            title="El código, la metodología y todo lo que se puede auditar"
            className={`inline-flex items-center gap-1 border-b-2 px-3 py-2 text-[12px] transition-colors ${
              enDetalle ? 'border-salvia text-crema' : 'border-transparent text-tenue hover:text-crema'
            }`}
          >
            {enDetalle ? DETALLE.find((d) => d.id === pestana)!.texto : 'Cómo se hizo'}
            <IconoAbajo className="h-3 w-3" />
          </button>
          {abierto && (
            <>
              {/* Sin esto el menú se queda abierto al hacer clic en cualquier
                  otro sitio, y tapa la pestaña que se quería usar. */}
              <button
                aria-label="Cerrar el menú"
                onClick={() => setAbierto(false)}
                className="fixed inset-0 z-20 cursor-default"
              />
              <div className="absolute left-0 z-30 mt-0.5 w-72 rounded-xl2 border border-borde
                              bg-superficie shadow-panel">
                {DETALLE.map((d) => (
                  <button
                    key={d.id}
                    onClick={() => { irA(d.id); setAbierto(false); }}
                    className="block w-full border-b border-borde/60 px-3 py-2 text-left
                               last:border-0 hover:bg-superficie2"
                  >
                    <div className={`text-[13px] ${d.id === pestana ? 'text-salvia' : 'text-crema'}`}>
                      {d.texto}
                    </div>
                    <div className="mt-0.5 text-[11px] leading-snug text-tenue">{d.ayuda}</div>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        <Pasos />
      </nav>

      <Asistente modo="barra" />

      <div className="min-h-0 flex-1 overflow-hidden">
        {pestana === 'lienzo' && <Lienzo />}
        {pestana === 'datos' && <PanelDatos />}
        {pestana === 'resultados' && <PanelResultados />}
        {pestana === 'graficos' && <PanelGraficos />}
        {pestana === 'codigo' && <PanelCodigo />}
        {pestana === 'metodologia' && <PanelMetodologia />}
        {pestana === 'especificaciones' && <PanelEspecificaciones />}
        {pestana === 'bitacora' && <PanelBitacora />}
      </div>
    </>
  );
}
