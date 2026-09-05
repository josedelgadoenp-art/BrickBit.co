import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Ábaco — análisis económico sin código',
  description:
    'Conecta bloques en un lienzo; Ábaco compila el análisis a un programa de Python legible y lo ejecuta. El código que exportas es el mismo que corrió.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es-MX">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
