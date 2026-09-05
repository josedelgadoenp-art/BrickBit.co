/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // La API vive en otro puerto en desarrollo. Con el reescrito, el navegador
  // habla siempre con el mismo origen y no hay CORS que perseguir.
  async rewrites() {
    return [
      {
        source: '/api/:ruta*',
        destination: `${process.env.ABAK_API ?? 'http://127.0.0.1:8000'}/api/:ruta*`,
      },
    ];
  },
};
export default nextConfig;
