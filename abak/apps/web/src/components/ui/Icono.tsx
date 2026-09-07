/**
 * Los iconos de la interfaz, como SVG.
 *
 * Antes eran glifos sueltos en el texto: «✦», «✕», «↑», «▾». Se ven distintos
 * en cada sistema —Windows los saca de una fuente de respaldo y quedan de otro
 * peso y otro tamaño—, no se pueden alinear con precisión y se leen como
 * adorno pegado. Un SVG hereda `currentColor`, escala con el texto y se ve
 * igual en todas partes.
 */

type Props = { className?: string };

const base = 'shrink-0';

export function IconoIA({ className = 'h-4 w-4' }: Props) {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden className={`${base} ${className}`}>
      <path d="M8 1.5 9.3 5.4a3 3 0 0 0 1.9 1.9L15 8.6l-3.8 1.3a3 3 0 0 0-1.9 1.9L8 15.6l-1.3-3.8a3 3 0 0 0-1.9-1.9L1 8.6l3.8-1.3a3 3 0 0 0 1.9-1.9L8 1.5Z"
            fill="currentColor" />
    </svg>
  );
}

export function IconoSubir({ className = 'h-4 w-4' }: Props) {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden className={`${base} ${className}`}>
      <path d="M8 11V3m0 0L5 6m3-3 3 3M2.5 11.5v1a2 2 0 0 0 2 2h7a2 2 0 0 0 2-2v-1"
            stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconoCerrar({ className = 'h-3.5 w-3.5' }: Props) {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden className={`${base} ${className}`}>
      <path d="m4 4 8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function IconoAbajo({ className = 'h-3 w-3' }: Props) {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden className={`${base} ${className}`}>
      <path d="m4 6 4 4 4-4" stroke="currentColor" strokeWidth="1.5"
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconoDerecha({ className = 'h-3.5 w-3.5' }: Props) {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden className={`${base} ${className}`}>
      <path d="M3 8h10m0 0-3.5-3.5M13 8l-3.5 3.5" stroke="currentColor" strokeWidth="1.4"
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconoIzquierda({ className = 'h-3.5 w-3.5' }: Props) {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden className={`${base} ${className}`}>
      <path d="M13 8H3m0 0 3.5-3.5M3 8l3.5 3.5" stroke="currentColor" strokeWidth="1.4"
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** La flecha del editor de grafos causales: baja y gira, «esto lleva a esto». */
export function IconoRamal({ className = 'h-3.5 w-3.5' }: Props) {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden className={`${base} ${className}`}>
      <path d="M4 3v5a2 2 0 0 0 2 2h6m0 0-2.5-2.5M12 10l-2.5 2.5" stroke="currentColor"
            strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconoAyuda({ className = 'h-3.5 w-3.5' }: Props) {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden className={`${base} ${className}`}>
      <circle cx="8" cy="8" r="6.2" stroke="currentColor" strokeWidth="1.2" />
      <path d="M6.3 6.1a1.75 1.75 0 1 1 2.4 1.62c-.45.2-.7.6-.7 1.05v.3" stroke="currentColor"
            strokeWidth="1.2" strokeLinecap="round" />
      <circle cx="8" cy="11.4" r=".75" fill="currentColor" />
    </svg>
  );
}
