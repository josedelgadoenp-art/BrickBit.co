# BrickBit — Guía del proyecto (para Claude Code)

Proptech mexicana de inteligencia inmobiliaria. **Sitio 100% estático** (HTML/CSS/JS vanilla, sin build), desplegado en **Netlify** (arrastrando ZIP o vía Git). Dominio en GoDaddy. Auth y datos en **Supabase**. Mapas/3D con **Google Maps**. Idioma: español (MX).

## Principio rector: honestidad de datos
Todo dato **estimado** se marca en **ámbar** (`--amb:#F5C277`) con la etiqueta "est." o similar. Los datos reales citan su fuente (SHF, INEGI/DENUE, etc.). Nunca presentar estimaciones como hechos.

## Paleta v2 (mate — sin colores brillosos ni glows)
Tierra `#100c0a` · superficie `#1d1713` · crema `#f5ede3` · bosque `#24664a` · salvia `#6fa287` · salvia profunda `#55997e` · oliva `#b7c489` · oliva profundo `#9aac6b` · terracota `#c07a66` · arcilla rosada `#cf928b` · **ámbar `#F5C277` (intocable: marca los datos estimados)**. Escala del mapa: `#bf5b52 → #cf9247 → #e0bb83 → #b7c489 → #24664a`. Nada de `box-shadow`/`text-shadow` de color (glow); sombras solo neutras `rgba(0,0,0,…)`. `financial.html` y `aviso-de-privacidad.html` tienen su propia paleta clara (alianza GNP) y no se tocan.

## Estructura
```
index.html            Landing (nav con dropdowns: Plataforma, Experiencias 3D, Arquitectos, Conócenos, Financial)
mapa.html             Mapa interactivo (Leaflet) de las 32 zonas
analizador.html       Analizador de inversión (pro-forma, PDF, guardado en Supabase)
panel.html            "Mi BrickBit" (cuenta del usuario)

# Experiencias 3D (Google Maps 3D / Map3DElement, canal v=alpha)
zona3d.html           Simulador 3D: volumen COS/CUS extruido + pro-forma financiera EN VIVO
                      + "Bienestar y servicios": índice de vida (salud/educación/abasto/
                      parques/transporte/ocio) vía Google Places (New), con radar y marcadores 3D.
pulso.html            Pulso de México: 32 ciudades como torres de datos + viaje en el tiempo (SHF 2005-2026 + forecast)
cine.html             Tour cinematográfico por las 32 ciudades
versus.html           Duelo de 2 ciudades en pantalla dividida

# BrickBit Arquitectos (requieren backend de IA, ver abajo)
crear-plano.html      Generador de planos con IA
gemelo-digital.html   Gemelo digital 3D de un plano
comparar-proyectos.html  Comparador de proyectos

# Financial
financial.html        Buscador de seguro GNP + radar de protección + asesoría financiera gratuita.
                      Envía leads a /api/lead (lead.mjs → Upstash + copia a Google Sheet).
                      Panel privado de prospectos en /financial#registros.
analisisfinanciero.html  Diagnóstico de retiro (ruta bonita /financial/analisisfinanciero).
                      Envía a /api/diagnostico (diagnostico.mjs → Upstash).
                      Panel privado en /financial/analisisfinanciero#registros.
gmm.html              Red hospitalaria GNP (ruta bonita /financial/gmm): mapa Leaflet de las
                      466 unidades en convenio, filtros por plan/nivel/categoría/estado,
                      búsqueda por CP con radio y geolocalización, más el listado de médicos
                      sin pago directo. Paleta clara de Financial, no la v2 oscura.
                      Puerta única de nombre + WhatsApp (#acceso) para las dos vistas; el
                      prospecto va a /api/lead con origen "gmm-red-hospitalaria" y se
                      recuerda en localStorage (bb_gmm_acceso). NO usa Supabase.

# Datos (data/*.json) — estáticos, leídos por fetch
estados.json          Las 32 zonas: precio_m2, plusvalia, yield, ciclo, oportunidad, lat/lng...
shf_series.json       Serie histórica índice SHF por zona 2005-2026 (para pulso.html)
forecast.json         Multiplicadores de pronóstico 1/3/5/10 años por zona
municipios_shf.json, mercado.json, etc.
gnp_hospitales.json   Red hospitalaria GNP para /financial/gmm (corte 2026-07-31). Campo `pr` =
                      precisión del pin ('colonia' o 'cp'): el pin ubica la ZONA, no el número.
gnp_medicos_sin_pago_directo.txt  NOMBRE|especialidad|entidad. Las claves se resuelven en gmm.html.
cp_centroides.txt     Índice CP → coordenada: 31,778 CP de SEPOMEX. Registros fijos de 17 chars
                      (CP + lat×1000 + |lng|×1000 + precisión: 0 propio CP, 1 centro del municipio),
                      ordenados por CP. Ancho fijo para no parsear separadores. Lo genera
                      tools/cp_index.py. La página lo baja sólo al primer uso del buscador por CP.

# Auth compartido
auth.js               Módulo de sesión Supabase (mountAuth, bbUser, bbClient...). Cache-bust con ?v=NNN al cambiar.
supabase.js           Cliente Supabase UMD self-hosted

zona/                 33 páginas SEO (una por ciudad) + index hub + zona.css
netlify/functions/    lead.mjs (CRM de financial). denue.js queda pero INEGI bloquea IPs cloud (no usar).
backend/              Cloudflare Worker para la IA de Arquitectos (NO va a Netlify; se despliega aparte)
```

## Reglas técnicas aprendidas (importantes)
- **Polígonos 3D de Google**: el anillo DEBE cerrar (repetir el primer punto al final) o no renderiza.
- **Calidad de tiles 3D**: cámara **estática** = máxima nitidez. La órbita continua impide que los tiles refinen → órbita siempre opcional (botón), nunca por defecto.
- **Inline todo**: los scripts van embebidos en cada HTML (no archivos JS externos por página) para evitar renders en blanco al abrir standalone.
- **Navegación in-page** sobre parámetros `?c=slug` (que fallan en deploys estáticos).
- Comentarios con `</script>` dentro de un `<script>` inline rompen la etiqueta: escapar como `<\/script>`.
- **Google Maps key** restringida por referrer a brickbit.co. Está embebida en las páginas 3D (es pública por diseño).

## Captación de datos (los dos formularios de Financial)
- **El valor primero, el contacto después.** Los dos embudos entregan su resultado ANTES de pedir
  nombre y teléfono. Se hizo así porque la versión anterior de `/financial` pedía el teléfono en el
  paso 2 —antes de dar nada— y una campaña de Meta con ~11.7k de alcance no produjo un solo
  registro. El resultado gratis es la moneda con la que se paga el dato.
- **La casilla de consentimiento NO se quita.** La LFPDPPP (art. 8) exige consentimiento *expreso*
  para datos patrimoniales o financieros, y ambos formularios capturan ingreso. Un "al dar clic
  aceptas" es consentimiento *tácito* y no basta para este tipo de dato. La casilla es el signo
  inequívoco que pide la ley.
- **Nada se envía antes del muro.** Verificado en navegador: cero peticiones al servidor hasta que
  la persona entrega sus datos a propósito.
- **Los paneles usan `DIAG_ADMIN_TOKEN`**, la misma llave para los dos. Va SIEMPRE en el header
  `x-admin-token`, nunca en la URL (ahí quedaría en los logs de Netlify y en el historial).
- **Derecho de cancelación**: `DELETE /api/lead?telefono=NNN` y `DELETE /api/diagnostico?telefono=NNN`.
  Redis no borra por campo, así que se reescribe la lista sin esa persona (`DEL` + `RPUSH` en un
  solo pipeline, conservando el orden).
- **Métricas de Meta**: "clics en el anuncio" cuenta reacciones, comentarios y expansiones de texto.
  Para medir el embudo hay que mirar **"visitas a la página de destino"**, que es bastante menor.
- **Listas largas: tope y scroll propio en móvil.** `gmm.html` quitaba el scroll interno de la lista
  en `max-width:900px`, y las 401 tarjetas estiraban la página a 41,928 px (49.7 pantallas de
  móvil). Con `max-height:62vh; overflow-y:auto` vuelve a 6.2. Si se toca un `overflow` dentro de
  una media query, hay que medir el alto del `body` después.
- **`/data/gnp_medicos_sin_pago_directo.txt` es públicamente descargable.** Netlify sirve estático:
  una reja en la página no protege el archivo. Sólo lleva `X-Robots-Tag: noindex`. Si alguna vez
  hace falta protegerlo de verdad, tiene que pasar por una función que valide antes de servirlo.

## URLs limpias (netlify.toml)
`/financial` → financial.html, `/financial/analisisfinanciero`, `/financial/gmm` (rewrite 200).
Los archivos viven en la raíz: **no** crear una carpeta `/financial/` o competiría con la primera regla.

## Librerías de terceros
Van auto-hospedadas en `assets/`, nunca desde un CDN: `chart.umd.js` (Chart.js 4.5.0),
`leaflet.js` + `leaflet.css` (1.9.4), `leaflet.markercluster.js` + `MarkerCluster.css` (1.5.3)
y `assets/images/` (los PNG que pide leaflet.css). Se obtienen con `npm pack <paquete>@<versión>`
y se copia el contenido de `package/dist/`. Motivo: una gráfica o un mapa no deben depender de
que un CDN ajeno esté de pie. Las tipografías de Google sí van por CDN (fallan de forma elegante).
`mapa.html` todavía carga Leaflet desde cdnjs — pendiente de migrar a `assets/`.

## Qué falta / pendientes
- ~~**DENUE**: tarjeta "Economía de la zona"~~ **hecha**. `analizador.html` la muestra con datos DENUE reales: por defecto el municipio-cabecera de la zona (constante `ECON` inline, sin fetch) y, al buscar una dirección, el **municipio exacto** de ese punto — resuelto en el navegador con point-in-polygon contra `data/municipios_shape.json` (2,436 polígonos del INEGI). Cada KPI trae su **percentil nacional** contra los 2,478 municipios. Todo se regenera con `python3 tools/economia_local.py` (lee `data/denue_municipal.csv` + `data/mexico_municipios.json`); tras correrlo hay que pegar `data/economia_zonas.json` en la constante `ECON` del analizador. No usa Supabase: en un sitio estático los JSON salen más baratos y rápidos.
- **Banxico en la pro-forma**: `analizador.html` ya no trae tasas quemadas. Los supuestos macro salen de `data/macro.json`, que genera `python3 tools/macro_local.py` con la API del SIE de Banxico (token gratuito en `BANXICO_TOKEN`; Banxico bloquea IPs de nube, así que se corre en local como `riesgos_local.py`). El archivo trae tasa objetivo, TIIE 28d, INPC anual y tipo de cambio; la **tasa hipotecaria se deriva** de la tasa objetivo + un spread (constante `SPREAD_HIPOTECARIO`, hoy 3.5 pp) y por eso va marcada en ámbar. Si el JSON no existe el sitio funciona igual, con los supuestos estáticos de `MACRO_FALLBACK` — que además unificó el descuadre que había entre el analizador (11.5%) y "¿Cuánto puedo comprar?" (10.5%). **Pendiente**: sacar el token y correr el script una vez.
- **Google Places / Location Scoring**: "Bienestar y servicios" ya integrado en `zona3d.html` (usa la key de Maps embebida). Para que funcione en vivo: habilitar **Places API (New)** + **facturación** en el proyecto de Google Cloud de esa key, y permitir Places en las restricciones del key (referrer brickbit.co). Ideas B2B pendientes (Índice de Vibrancia/gentrificación, Búsqueda inversa por estilo de vida, Desiertos de oportunidad) usan la misma API.
- ~~**CRM de Financial**~~ **hecho y verificado**: `SHEETS_WEBHOOK_URL` y `LEAD_SECRET` están
  configuradas y el Apps Script responde (un POST de prueba a `/api/lead` devolvió `{"ok":true}`).
  Los prospectos ya no dependen solo de esa hoja: `lead.mjs` guarda primero en Upstash y después
  copia a la hoja, así que si el Apps Script se cae el prospecto no se pierde.
- **IA de Arquitectos**: desplegar `backend/` en Cloudflare (`wrangler secret put ANTHROPIC_API_KEY` + `wrangler deploy`) y pegar la URL del worker en la config de cada herramienta.
- **Memoria del mercado**: `c21-subir.mjs` ya genera seguimiento (`_seg-<slug>`: altas/recortes/bajas/días), `_metricas` (medianas + yield real) y `_hist` (serie mensual → Índice BrickBit en pulso). Se activa corriendo el flujo normal `c21-scraper` → `c21-subir`; la historia crece con cada corrida (ideal: mensual, `tools/actualizar-inventario.bat`). Sin cambios de worker.
- ~~**Índice nacional de CP para `/financial/gmm`**~~ **hecho**: `data/cp_centroides.txt` trae los
  **31,778 CP** del Catálogo Nacional de SEPOMEX. Como ese catálogo **no publica coordenadas**, la
  precisión es mixta y cada registro la guarda: 1,530 CP tienen el punto de su propio código postal
  (los 1,182 polígonos de `data/cdmx_codigos_postales.json` + los CP de los domicilios de la red) y
  30,248 se ubican en el centro de su municipio vía `data/mexico_municipios.json`. La página avisa
  en pantalla cuando toca uno aproximado. Se regenera con
  `python3 tools/cp_index.py --sepomex CPdescarga.xls` (necesita `xlrd` y `shapely`; el .xls pesa
  70 MB y **no** se guarda en el repo, se baja de Correos de México y se corre en local).
  Para mejorar la precisión haría falta una fuente con lat/lng por CP, que SEPOMEX no da.
- **Capa de seguridad (SESNSP)**: descargar el CSV "Incidencia Delictiva Estatal" (nueva metodología) y correr `python tools/riesgos_local.py <csv>` → `data/riesgos.json` (el gobierno bloquea IPs de nube). El mapa la muestra sola cuando el archivo existe.

## Despliegue rápido
1. Subir todo (menos `backend/`) a Netlify.
2. Variables de entorno en Netlify según lo de arriba (leads, y si se retomara, DENUE_TOKEN).
3. `backend/` va en Cloudflare Workers, por separado.
