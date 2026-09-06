/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Con `iniciar.ps1 -Red` el servidor escucha en toda la red local y se entra
  // por la IP de la máquina, no por localhost. Next bloquea por defecto las
  // peticiones de desarrollo que llegan con otro origen, así que hay que
  // declarar los rangos privados; son los únicos que puede tener una IP de
  // casa (RFC 1918). No abre nada hacia internet: eso lo decide a quién le
  // responde el servidor, no esta lista.
  allowedDevOrigins: ['192.168.*.*', '10.*.*.*', '172.16.*.*', '172.17.*.*',
                      '172.18.*.*', '172.19.*.*', '172.2*.*.*', '172.30.*.*',
                      '172.31.*.*'],
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
