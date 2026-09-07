'use client';

import {
  Background, BackgroundVariant, Controls, MiniMap, ReactFlow, ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useCallback, useMemo, useRef } from 'react';

import NodoAbak from '@/components/canvas/NodoAbak';
import Asistente from '@/components/panels/Asistente';
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
        <Controls className="!border-borde !bg-superficie" showInteractive={false} />
        <MiniMap pannable zoomable nodeColor={colorNodo} maskColor="rgba(16,12,10,.72)" />
      </ReactFlow>

      {nodos.length === 0 && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="max-w-md rounded-lg border border-borde bg-superficie/85 px-6 py-5 text-center">
            <p className="text-sm text-crema">El lienzo está vacío.</p>
            <p className="mt-2 text-[13px] leading-relaxed text-tenue">
              Arrastra una herramienta de la izquierda, o abre un ejemplo desde la barra de arriba.
              Empieza casi siempre por <span className="text-salvia">Datos de ejemplo</span>.
            </p>
          </div>
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
        <Asistente />
      </div>
    </ReactFlowProvider>
  );
}
