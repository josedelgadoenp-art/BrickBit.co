# BrickBit — Guía del proyecto (para Claude Code)

Proptech mexicana de inteligencia inmobiliaria. **Sitio 100% estático** (HTML/CSS/JS vanilla, sin build), desplegado en **Netlify** (arrastrando ZIP o vía Git). Dominio en GoDaddy. Auth y datos en **Supabase**. Mapas/3D con **Google Maps**. Idioma: español (MX).

## Principio rector: honestidad de datos
Todo dato **estimado** se marca en **ámbar** (`--amb:#F5C277`) con la etiqueta "est." o similar. Los datos reales citan su fuente (SHF, INEGI/DENUE, etc.). Nunca presentar estimaciones como hechos.

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
                      Envía leads a /api/lead (Netlify function lead.mjs → Google Sheet).

# Datos (data/*.json) — estáticos, leídos por fetch
estados.json          Las 32 zonas: precio_m2, plusvalia, yield, ciclo, oportunidad, lat/lng...
shf_series.json       Serie histórica índice SHF por zona 2005-2026 (para pulso.html)
forecast.json         Multiplicadores de pronóstico 1/3/5/10 años por zona
municipios_shf.json, mercado.json, etc.

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

## URLs limpias (netlify.toml)
`/financial` → financial.html (rewrite 200). Se pueden añadir más igual.

## Qué falta / pendientes
- **DENUE**: los índices económicos por zona se calculan con `denue_local.py` (script local que lee CSV del DENUE; INEGI bloquea la nube). Falta cargar `zone_denue` en Supabase y construir la tarjeta "Economía de la zona" en el analizador.
- **Google Places / Location Scoring**: "Bienestar y servicios" ya integrado en `zona3d.html` (usa la key de Maps embebida). Para que funcione en vivo: habilitar **Places API (New)** + **facturación** en el proyecto de Google Cloud de esa key, y permitir Places en las restricciones del key (referrer brickbit.co). Ideas B2B pendientes (Índice de Vibrancia/gentrificación, Búsqueda inversa por estilo de vida, Desiertos de oportunidad) usan la misma API.
- **CRM de Financial**: crear el Google Sheet + Apps Script y setear en Netlify las vars `SHEETS_WEBHOOK_URL`, `LEAD_SECRET`, `ALLOWED_ORIGIN`.
- **IA de Arquitectos**: desplegar `backend/` en Cloudflare (`wrangler secret put ANTHROPIC_API_KEY` + `wrangler deploy`) y pegar la URL del worker en la config de cada herramienta.

## Despliegue rápido
1. Subir todo (menos `backend/`) a Netlify.
2. Variables de entorno en Netlify según lo de arriba (leads, y si se retomara, DENUE_TOKEN).
3. `backend/` va en Cloudflare Workers, por separado.
