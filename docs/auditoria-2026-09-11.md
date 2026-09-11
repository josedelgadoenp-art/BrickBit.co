# BrickBit.co — auditoría y renovación

Fecha: 11 de septiembre de 2026. Base revisada: `5f7d19a` en `main`.

Se implementó una nueva portada orientada al análisis, una experiencia común para
las herramientas inmobiliarias y una renovación de las 32 fichas de ciudades.
La intervención también corrige incoherencias de datos, fallas de persistencia,
tratamiento de contenido externo y problemas del backend. Los cambios se entregan
en una rama revisable; no se fusionaron ni se desplegaron sobre producción.

## Alcance y evidencia

- Inventario y comprobación estática de 53 páginas: portada, herramientas,
  Financial, privacidad, presentación y fichas de ciudades.
- Verificación de sintaxis de 30 scripts o archivos JavaScript y de sus
  referencias locales. No se detectaron errores al finalizar.
- 14 pruebas JavaScript: autenticación/favoritos con un cliente simulado,
  interacciones del explorador con DOM simulado, inyección de contenido externo,
  TIR, control de origen, tamaño de solicitudes, rate limit y persistencia.
- 3 pruebas Python: causalidad temporal de los intervalos, reproducción de
  métricas y contenido de la distribución pública.
- Inspección visual de la portada actualmente publicada. No se ejecutó una
  inspección visual de la versión modificada: este sitio estático no dispone de
  un servidor compatible con la previsualización supervisada de esta sesión.
  Las pruebas DOM no miden disposición, contraste ni renderizado WebGL.
- Los GET públicos de `/api/score`, `/api/forecast` y `/api/listados` devolvieron
  403 desde este entorno. Esto impidió comprobarlos aquí; no demuestra por sí
  solo que estén fallando para los visitantes.

El monorepo también contiene Abak, Atlas y MyCouple. No se rediseñaron esos
productos independientes. La publicación de MyCouple se conserva. La lógica
completa de Streamlit, sus fuentes remotas y los otros productos no tienen una
certificación funcional como resultado de esta intervención.

## Hallazgos corregidos

| Prioridad | Hallazgo | Corrección y comprobación |
|---|---|---|
| Alta | Los intervalos a 3 años usaban residuos cuyos resultados aún no existían en el origen evaluado. | `residuos_hasta(t,h)` exige `tp+h <= t`. Una prueba modifica todo el futuro y comprueba que la calibración pasada permanece idéntica. |
| Alta | Portada y fichas de ciudad mostraban multiplicadores antiguos. | Explorador alimentado por `forecast.json`; 32 fichas regeneradas y script de sincronización versionado. |
| Alta | Precio/m² derivado presentado en la portada como si fuera una observación real. | Se identifica como referencia derivada SHF/ENVI y se muestra en ámbar. Las fuentes acompañan los valores. |
| Alta | Distintos yields de respaldo entre analizador, 3D y datos centrales. | Se sincronizaron los valores del analizador, `zonas.js` y el simulador con `estados.json`. |
| Alta | El borrado de prospectos leía, borraba y reconstruía toda la lista; una escritura concurrente podía perderse. | Operación Lua atómica en Redis: elimina únicamente los valores coincidentes y conserva el orden de los demás. No se ejecutaron borrados reales. |
| Alta | Upstash puede devolver errores de comandos dentro de HTTP 200, interpretados como éxito. | Se inspecciona cada resultado; un error impide confirmar el guardado. Prueba con respuesta de almacenamiento fallida. |
| Alta | Datos de listados y respuestas de búsqueda interpolados como HTML sin escapar. | La nueva búsqueda construye nodos con `textContent` y filtra protocolos URL. Se escapan además campos y URLs de fichas en mapa y 3D. No equivale a una auditoría exhaustiva de todos los usos de `innerHTML` del monorepo. |
| Alta | El backend aplicaba controles de origen de forma desigual. | Control común para escrituras de navegador; allowlist predeterminada para brickbit.co y www; se conserva lectura pública para widgets. |
| Media | El límite de solicitudes dependía de Content-Length. | Se cuentan bytes recibidos, incluyendo cuerpos sin ese header. Límites diferenciados para planos, modelos, textura e ingesta. |
| Media | Inferencia pública sin limitación común de ráfagas. | Límite de 30 POST por IP/ruta/minuto por instancia, con mapa acotado y HTTP 429. La ingesta autenticada conserva su ruta propia. |
| Media | Credencial del disparo manual de alertas en query string. | Ahora exige `x-admin-token`; no acepta la credencial en URL. Hay que actualizar cualquier cliente manual. |
| Media | `publish = "."` dependía de bloquear rutas individuales del repositorio. | `scripts/build_site.py` crea `dist/` con una selección explícita de archivos públicos. Excluye código servidor, SQL, documentación interna y el listado médico restringido. |
| Media | Favoritos indicaban guardado aunque fallara la escritura. | La operación devuelve un error, y las vistas conservan el estado y permiten reintentar. |
| Media | La caché de favoritos podía conservar datos de una sesión anterior. | Se invalida al cambiar la sesión desde la inicialización del cliente. |
| Media | Los controles de alerta conservaban cambios locales después de fallar el guardado. | Restauración del estado anterior y validación del horizonte/umbral. |
| Media | TIR limitada a retornos menores que 300% y sin reconocer flujos con raíces ambiguas. | Búsqueda adaptativa, validación de finitud y rechazo de múltiples cambios de signo. Pruebas de retorno alto, negativo y raíz ambigua. |
| Media | Supuestos inválidos podían provocar divisiones por cero en financiamiento. | Se rechazan plazos nulos con deuda, porcentajes inválidos y valores no finitos antes de calcular. |
| Media | Leaflet del mapa dependía de un CDN aunque existía una copia local. | El mapa carga los activos locales de Leaflet. |
| Media | Modal de autenticación sin foco acotado ni etiquetas vinculadas. | Etiquetas accesibles, foco inicial, recorrido con Tab, cierre con Escape y devolución del foco. |
| Media | Movimiento automático y logo base64 repetido en documentos. | Video de portada bajo acción del usuario, poster extraído del video existente, movimiento reducido, Cinema respeta la preferencia inicial y logos locales reutilizados. |

## Resultado del modelo

No se ajustaron los coeficientes para mejorar artificialmente el resultado.

| Métrica | 1 año | 3 años |
|---|---:|---:|
| Error absoluto medio BrickBit, pp de apreciación acumulada | 1.82 | 5.56 |
| Persistencia | 1.99 | 6.20 |
| Promedio nacional | 1.94 | 5.78 |
| Evaluaciones | 480 | 416 |
| Cobertura empírica corregida, intervalo nominal 90% | 91.5% | 86.6% |

Antes de corregir la fuga temporal, se publicaba 89.6% para la cobertura a tres
años. El error puntual no cambia, porque la corrección afecta la calibración de
los intervalos. Los pesos documentados fueron calibrados con 2011–2018; las
métricas agregadas incluyen ese periodo. No deben describirse como una prueba
independiente de generalización. Cinco y diez años siguen siendo extrapolaciones.

## Renovación de la experiencia

- Portada con navegación lateral, acceso a búsqueda, explorador de ciudades,
  horizontes 1/3/5/10, intervalo del modelo, fuentes y enlaces directos al análisis.
- Catálogo de las herramientas existentes, sin esconderlas detrás de bloques
  comerciales repetidos. Se conservan búsqueda, portafolios sugeridos, favoritos,
  cuenta, lista de novedades, Iris y acceso a Financial.
- Nueva jerarquía tipográfica, superficies azul oscuro, acciones turquesa y
  ámbar para estimaciones. Layout responsive con navegación móvil desplegable.
- Navegación común y encabezados más breves en crear plano, revisor, gemelo y
  comparador. Actualización visual del mapa, analizador y controles 3D.
- Treinta y dos fichas con estructura renovada, escenarios actuales, fuentes y
  límites visibles. Contenido SEO y preguntas frecuentes consistentes.
- Entrada breve y estados de interacción, reducción de movimiento y pausa del
  video al salir de la pestaña. Cámara 3D opcional se conserva.
- Financial conserva su identidad separada; esta intervención corrige su
  persistencia, pero no sustituye sus pantallas por el tema inmobiliario.

La respuesta HTML de portada pasa de 173,708 a aproximadamente 53,500 bytes
sin comprimir. Esto es reducción de HTML, no una medición de Core Web Vitals:
ahora existen CSS y JS externos cacheables y se añadió un poster del video.

## Verificación que falta antes de publicar

1. Revisar el diseño en navegador a 390, 768 y 1440 px, con teclado y texto al
   200%; comprobar impresión/PDF y los paneles del mapa. La revisión visual
   del código modificado no se realizó en esta sesión.
2. Confirmar el build de Netlify y las rutas limpias, Functions y Netlify Forms
   con `dist/`. La función médica continúa incluyendo su archivo mediante
   `included_files`; el archivo nunca entra en la distribución estática.
3. Verificar Supabase con una cuenta de prueba: sesión, recuperación, favoritos,
   RLS real, análisis y alertas. El SQL versionado no acredita su estado aplicado.
4. Verificar Cloudflare: modelo Anthropic disponible para esa cuenta, secretos,
   KV, facturación, cuota y los endpoints de IA. No se consumieron llamadas
   pagadas ni se enviaron alertas o correos reales durante las pruebas.
5. Confirmar restricciones y APIs habilitadas de Google Maps/Places. Son claves
   de navegador públicas por diseño; no se sustituyeron ni se ampliaron permisos.
6. Sustituir el límite por instancia por un control distribuido de cuota antes
   de tráfico significativo. CORS y un límite en memoria no son autenticación
   ni garantizan una cuota global: los clientes fuera del navegador pueden
   omitir o falsificar Origin. Los endpoints pagos siguen requiriendo una
   estrategia de acceso/consumo a nivel de producto.
7. Validar cron, Twilio/Resend y entregas reales cuando se conecten los servicios.
   La existencia de una ruta y una configuración no prueba entrega operativa.

Netlify, Supabase y Cloudflare fueron identificados como conexiones necesarias
para continuar esa verificación operativa. No estaban conectados al cerrar la
intervención. No se fusionó la rama ni se publicaron cambios en brickbit.co.

## Cómo reproducir

```sh
npm ci --prefix tests
npm test --prefix tests
python -m pip install numpy==2.2.6
python -m unittest discover -s tests -p 'test_*.py'
python scripts/check_site.py
python scripts/build_site.py
```

Al actualizar datos: regenerar el pronóstico según el proceso del proyecto y
ejecutar `python scripts/sync_public_data.py`. Revisar y versionar las salidas.
El workflow `BrickBit quality` ejecuta las comprobaciones en pull requests.

Las pruebas de backend usan respuestas simuladas y datos de prueba; no tienen
credenciales de producción. Este informe documenta evidencia y límites, no una
garantía de ausencia de fallas.
