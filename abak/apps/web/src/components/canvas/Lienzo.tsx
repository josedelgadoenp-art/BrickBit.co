'use client';

import {
  Background, BackgroundVariant, Controls, MiniMap, ReactFlow, ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useCallback, useMemo, useRef } from 'react';

import NodoAbak from '@/components/canvas/NodoAbak';
import { usarLienzo } from '@/store/lienzo';

function LienzoInterno() {
  const nodos = usarLienzo((s) => s.nodos);
  const aristas = usarLienzo((s) => s.aristas);
  const catalogo = usarLienzo((s) => s.catalogo);
  const cambiarNodos = usarLienzo((s) => s.cambiarNodos);
  const cambiarAristas = usarLienzo((s) => s.cambiarAristas);
  const conectar = usarLienzo((s) => s.conectar);
  const seleccionar = usarLienzo((s) => s.seleccionar);
  const agregarNodo = usarLienzo((s) => s.agregarNodo);

  const contenedor = useRef<HTMLDivElement>(null);
  const tiposNodo = useMemo(() => ({ abak: NodoAbak }), []);

  /** Soltar una herramienta arrastrada desde la paleta. */
  const soltar = useCallback(
    (evento: React.DragEvent) => {
      evento.preventDefault();
      const op = evento.dataTransfer.getData('application/abak-op');
      if (!op || !contenedor.current) return;
      const caja = contenedor.current.getBoundingClientRect();
      agregarNodo(op, { x: evento.clientX - caja.left - 120, y: evento.clientY - caja.top - 30 });
    },
    [agregarNodo],
  );

  const colorNodo = useCallback(
    (n: { data?: { op?: string } }) => {
      const d = catalogo?.nodos.find((x) => x.op === n.data?.op);
      return catalogo?.familias.find((f) => f.id === d?.familia)?.color ?? '#6b6259';
    },
    [catalogo],
  );

  return (
    <div ref={contenedor} className="h-full w-full" onDrop={soltar}
         onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; }}>
      <ReactFlow
        nodes={nodos}
        edges={aristas}
        nodeTypes={tiposNodo}
        onNodesChange={cambiarNodos}
        onEdgesChange={cambiarAristas}
        onConnect={conectar}
        onNodeClick={(_, n) => seleccionar(n.id)}
        onPaneClick={() => seleccionar(null)}
        fitView
        minZoom={0.2}
        maxZoom={1.8}
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{ type: 'smoothstep' }}
      >
        <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#2a221c" />
        {/* Sin bloques no hay nada que encuadrar ni que navegar: dos cajas vacías
            compitiendo con la pantalla de inicio. Aparecen cuando sirven. */}
        {nodos.length > 0 && (
          <>
            <Controls className="!border-borde !bg-superficie" showInteractive={false} />
            <MiniMap pannable zoomable nodeColor={colorNodo} maskColor="rgba(12,11,10,.74)" />
          </>
        )}
      </ReactFlow>

      {/* Un lienzo vacío sin una palabra encima es una pared. Sólo se llega
          aquí pidiendo armarlo a mano, así que dice el gesto que falta. */}
      {nodos.length === 0 && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-8">
          <p className="max-w-sm text-center text-[13px] leading-relaxed text-tenue">
            Haz clic en una herramienta de la izquierda —o arrástrala hasta aquí— y se conecta
            sola con la anterior. Empieza por «Cargar archivo» o «Datos de ejemplo».
          </p>
        </div>
      )}

    </div>
  );
}

export default function Lienzo() {
  return (
    <ReactFlowProvider>
      <div className="relative h-full w-full">
        <LienzoInterno />
      </div>
    </ReactFlowProvider>
  );
}
