import type { Config } from 'tailwindcss';

/**
 * Paleta de Abak.
 *
 * Neutros mas profundos y con mas separacion entre niveles que la v2 del sitio:
 * una herramienta que se mira durante horas necesita jerarquia, no un solo tono
 * de cafe. El acento se abrio para que un boton primario se lea de reojo.
 *
 * Dos reglas que no se tocan:
 * - El AMBAR marca los datos estimados y nada mas. Ni decoracion, ni acentos.
 * - Sombras solo neutras. Nada de glows de color.
 *
 * Todos los colores de texto se verificaron contra los tres fondos: el minimo
 * es 6.05:1 y el boton primario da 9.58:1.
 */
const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        tierra: '#0C0B0A',
        superficie: '#161513',
        superficie2: '#1F1D1B',
        superficie3: '#282523',
        borde: '#302D2A',
        bordeSuave: '#252220',
        crema: '#F4F2EF',
        tenue: '#A8A29B',
        bosque: '#2C7355',
        salvia: '#7CC49B',
        salviaProfunda: '#63AC83',
        oliva: '#BFCB93',
        olivaProfundo: '#9AAC6B',
        terracota: '#D08A73',
        arcilla: '#E0A79D',
        ambar: '#F5C277',
        acero: '#9BB4C9',
      },
      fontFamily: {
        // Geist: tipografia de interfaz, geometrica y de altura de x generosa.
        // La pila de respaldo es toda de sistema: si no hay red, no cambia nada
        // mas que la letra.
        sans: ['Geist', 'Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['Geist Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      letterSpacing: {
        apretado: '-0.011em',
      },
      borderRadius: {
        xl2: '14px',
      },
      boxShadow: {
        // Sombras SOLO neutras. Nada de glows de color.
        panel: '0 1px 2px rgba(0,0,0,.4), 0 12px 32px rgba(0,0,0,.32)',
        nodo: '0 1px 2px rgba(0,0,0,.45), 0 6px 16px rgba(0,0,0,.28)',
        alto: '0 2px 4px rgba(0,0,0,.45), 0 24px 60px rgba(0,0,0,.42)',
      },
    },
  },
  plugins: [],
};

export default config;
