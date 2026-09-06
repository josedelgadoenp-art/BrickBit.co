'use client';

import { useRef, useState } from 'react';

import { ErrorApi } from '@/lib/api';
import { bytes } from '@/lib/formato';
import { usarLienzo } from '@/store/lienzo';

interface Respuesta {
  archivo_id: string;
  nombre: string;
  n_filas: number;
  n_columnas: number;
  bytes_origen: number;
  bytes_parquet: number;
  compresion: number;
  columnas: { nombre: string; tipo_arrow: string; faltantes: number }[];
  avisos: string[];
}

/**
 * Sube un archivo y deja el nodo configurado.
 *
 * Al subir, el servidor convierte el archivo a formato columnar y devuelve su
 * esquema. Ese esquema se guarda en el nodo, y por eso los desplegables de los
 * bloques siguientes funcionan de inmediato, sin haber ejecutado nada.
 */
export default function SubirArchivo({ nodoId }: { nodoId: string }) {
  const actualizar = usarLienzo((s) => s.actualizarParams);
  const nodo = usarLienzo((s) => s.nodos.find((n) => n.id === nodoId));
  const entrada = useRef<HTMLInputElement>(null);
  const [subiendo, setSubiendo] = useState(false);
  const [progreso, setProgreso] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<Respuesta | null>(null);

  const params = (nodo?.data.params ?? {}) as Record<string, unknown>;
  const yaHay = Boolean(params.archivo_id);

  async function subir(archivo: File) {
    setSubiendo(true);
    setError(null);
    setProgreso(`Subiendo ${bytes(archivo.size)}…`);
    try {
      const cuerpo = new FormData();
      cuerpo.append('archivo', archivo);
      cuerpo.append('separador', String(params.separador ?? ','));
      cuerpo.append('decimal', String(params.decimal ?? '.'));
      cuerpo.append('codificacion', String(params.codificacion ?? 'utf-8'));

      setProgreso('Convirtiendo a formato columnar…');
      const respuesta = await fetch('/api/v1/datos/subir', { method: 'POST', body: cuerpo });
      if (!respuesta.ok) {
        const detalle = await respuesta.json().catch(() => null);
        throw new ErrorApi(respuesta.status, detalle);
      }
      const datos: Respuesta = await respuesta.json();
      setInfo(datos);
      actualizar(nodoId, {
        archivo_id: datos.archivo_id,
        nombre: datos.nombre,
        columnas: datos.columnas,
        n_filas: datos.n_filas,
      });
    } catch (e) {
      setError(e instanceof ErrorApi ? e.mensaje : 'No se pudo subir el archivo.');
    } finally {
      setSubiendo(false);
      setProgreso(null);
    }
  }

  return (
    <div>
      <input
        ref={entrada}
        type="file"
        accept=".csv,.tsv,.txt,.xlsx,.xls,.parquet,.zip"
        className="hidden"
        onChange={(e) => {
          const archivo = e.target.files?.[0];
          if (archivo) subir(archivo);
          e.target.value = '';
        }}
      />
      <button
        onClick={() => entrada.current?.click()}
        disabled={subiendo}
        className="w-full rounded border border-dashed border-borde bg-tierra px-3 py-3 text-[12px] text-tenue transition-colors hover:border-salvia hover:text-crema disabled:opacity-60"
      >
        {subiendo ? (progreso ?? 'Trabajando…')
          : yaHay ? `Reemplazar «${String(params.nombre)}»`
          : 'Elegir un archivo (CSV, Excel o Parquet)'}
      </button>

      {yaHay && !info && (
        <p className="mt-1.5 text-[11px] text-tenue">
          {String(params.nombre)} · {Number(params.n_filas ?? 0).toLocaleString('es-MX')} filas ·{' '}
          {(params.columnas as unknown[] | undefined)?.length ?? 0} columnas
        </p>
      )}

      {info && (
        <div className="mt-2 rounded border border-borde bg-tierra p-2.5 text-[11px] leading-relaxed">
          <p className="text-crema">
            {info.n_filas.toLocaleString('es-MX')} filas × {info.n_columnas} columnas
          </p>
          <p className="mt-0.5 text-tenue">
            {bytes(info.bytes_origen)} → {bytes(info.bytes_parquet)} en columnar
            {info.compresion > 1.1 && ` (${info.compresion}× más chico)`}
          </p>
          {info.columnas.some((c) => c.faltantes > 0) && (
            <p className="mt-1 text-tenue">
              Con faltantes:{' '}
              {info.columnas.filter((c) => c.faltantes > 0).slice(0, 4)
                .map((c) => `${c.nombre} (${c.faltantes.toLocaleString('es-MX')})`).join(', ')}
            </p>
          )}
          {info.avisos.map((aviso, i) => (
            <p key={i} className="mt-1.5 border-l-2 border-ambar/50 pl-2 text-ambar">{aviso}</p>
          ))}
        </div>
      )}

      {error && <p className="mt-1.5 text-[11px] leading-snug text-arcilla">{error}</p>}
    </div>
  );
}
