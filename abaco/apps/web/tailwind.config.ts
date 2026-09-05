import type { Config } from 'tailwindcss';

/**
 * Paleta v2 de la casa: mate, sin colores brillosos ni glows.
 * El ámbar es intocable — marca los datos estimados y nada más.
 */
const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        tierra: '#100c0a',
        superficie: '#1d1713',
        superficie2: '#241d18',
        borde: '#3a302a',
        crema: '#f5ede3',
        tenue: '#a89e93',
        bosque: '#24664a',
        salvia: '#6fa287',
        salviaProfunda: '#55997e',
        oliva: '#b7c489',
        olivaProfundo: '#9aac6b',
        terracota: '#c07a66',
        arcilla: '#cf928b',
        ambar: '#F5C277',
        acero: '#8fa8bd',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      boxShadow: {
        // Sombras SOLO neutras. Nada de glows de color.
        panel: '0 1px 2px rgba(0,0,0,.35), 0 8px 24px rgba(0,0,0,.28)',
        nodo: '0 1px 2px rgba(0,0,0,.4), 0 4px 12px rgba(0,0,0,.25)',
      },
    },
  },
  plugins: [],
};
export default config;
