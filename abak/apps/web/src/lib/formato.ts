/** Formato de números y fechas en español (MX). */

export function num(v: unknown, decimales = 4): string {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v !== 'number') return String(v);
  if (!Number.isFinite(v)) return '—';
  const abs = Math.abs(v);
  // Un entero se escribe entero, por grande que sea: son pesos, metros
  // cuadrados o conteos, y nadie escribe el precio de una casa con cuatro
  // decimales. El corte estaba en 1e6, así que en una misma tabla los m2
  // salían «127» y el precio «7,397,420.0000».
  if (Number.isInteger(v) && abs < 1e15) {
    return v.toLocaleString('es-MX', { maximumFractionDigits: 0 });
  }
  if (abs !== 0 && (abs < 1e-4 || abs >= 1e9)) return v.toExponential(2);
  return v.toLocaleString('es-MX', {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales,
  });
}

export function pValor(p: number | null): string {
  if (p === null || p === undefined) return '—';
  if (p < 0.001) return '<0.001';
  return p.toFixed(3);
}

/**
 * ¿Esta cifra es una probabilidad de una prueba?
 *
 * Importa porque un p-valor no se escribe como cualquier número: redondeado a
 * tres decimales, 1e-20 sale como «0», y ninguna probabilidad es cero. Se
 * escribe «<0.001», que es lo que se publica en un artículo.
 */
export function esProbabilidad(clave: string): boolean {
  const c = clave.toLowerCase().replace(/[()\s]/g, '');
  return c === 'p' || c === 'pvalor' || c === 'pvalue'
      || c.startsWith('prob') || c.endsWith('_p') || c.endsWith('pvalor');
}

export function duracion(ms: number | null | undefined): string {
  if (!ms && ms !== 0) return '—';
  if (ms < 1000) return `${ms} ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.floor(ms / 60000)} min ${Math.round((ms % 60000) / 1000)} s`;
}

export function bytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 ** 2).toFixed(1)} MB`;
}
