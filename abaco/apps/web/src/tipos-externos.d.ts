/**
 * Plotly no publica tipos para su bundle `dist-min`, y traer `@types/plotly.js`
 * completo (más de 200 KB de declaraciones) para usar dos funciones no se paga.
 * Se declara sólo lo que Ábaco llama.
 */
declare module 'plotly.js-dist-min' {
  interface OpcionesPlotly {
    displaylogo?: boolean;
    responsive?: boolean;
    locale?: string;
    modeBarButtonsToRemove?: string[];
    toImageButtonOptions?: { format?: string; scale?: number; filename?: string };
  }
  const Plotly: {
    react(
      nodo: HTMLElement,
      datos: unknown[],
      disposicion: Record<string, unknown>,
      opciones?: OpcionesPlotly,
    ): Promise<HTMLElement>;
    purge(nodo: HTMLElement): void;
  };
  export default Plotly;
}
