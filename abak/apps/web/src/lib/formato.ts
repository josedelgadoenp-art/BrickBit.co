/** Formato de números y fechas en español (MX). */

export function num(v: unknown, decimales = 4): string {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v !== 'number') return String(v);
  if (!Number.isFinite(v)) return '—';
  const abs = Math.abs(v);
  if (abs !== 0 && (abs < 1e-4 || abs >= 1e9)) return v.toExponential(2);
  return v.toLocaleString('es-MX', {
    minimumFractionDigits: Number.isInteger(v) && abs < 1e6 ? 0 : decimales,
    maximumFractionDigits: decimales,
  });
}

export function pValor(p: number | null): string {
  if (p === null || p === undefined) return '—';
  if (p < 0.001) return '<0.001';
  return p.toFixed(3);
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
