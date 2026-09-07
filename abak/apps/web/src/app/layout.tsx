import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Abak — inteligencia económica',
  description:
    'Describe el análisis en español y la inteligencia artificial lo arma con herramientas de econometría de verdad. Todo queda a la vista: el código que exportas es el mismo que corrió.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es-MX">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
