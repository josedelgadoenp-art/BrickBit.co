# BrickBit v1.5 — Guía de despliegue

## Qué incluye este paquete
- `index.html` — landing (nuevo hero con video + estilo glass)
- `mapa.html` — mapa interactivo (menú Vista ▾ + comparador de zonas)
- `analizador.html` — analizador de inversión (menú Acciones ▾, pro-forma, compartir por URL)
- `panel.html` — "Mi BrickBit" (análisis guardados, favoritos, alertas)
- `auth.js` — login Supabase (YA trae tus llaves) + favoritos
- `supabase.js` — librería Supabase (self-hosted, no usa CDN)
- `zona/` — 32 páginas SEO por zona + hub + estilos
- `sitemap.xml`, `robots.txt` — SEO
- `data/` — datos reales (SHF/ENVI) que consumen el mapa y el panel
- `netlify.toml` — config de Netlify (publica la raíz)
- `supabase_schema.sql` — SOLO para correr en Supabase (no es del sitio)

## Pasos para publicar (Netlify)
1. En **Netlify → Deploys**, arrastra esta carpeta (o el ZIP) tal cual.
   Todos los HTML deben quedar en la RAÍZ (no dentro de una subcarpeta).
2. Abre tu sitio por su **URL https** (no por doble clic / file://).
3. Verifica en la consola del navegador: `window.bbConfigured` debe dar `true`.

## Lo que debes hacer en Supabase (1 vez)
1. Abre el **SQL Editor** de tu proyecto.
2. Corre el contenido de `supabase_schema.sql`. (Si ya corriste la parte de
   `saved_analyses` y `favorite_zones`, basta con correr la sección nueva de
   `zone_alerts` que está al final del archivo.)
3. En **Authentication → URL Configuration**, confirma que tu URL de Netlify /
   dominio esté en *Site URL* y en *Redirect URLs* (con `/**` al final).

## SEO
- Envía `https://TU-DOMINIO/sitemap.xml` en **Google Search Console**.
- Las páginas de zona usan el dominio `https://brickbit.co`. Si tu dominio
  final es otro, avísame y reajusto el `BASE` en `etl/gen_zonas.py` y regenero.

## Notas
- El envío de **correos** de las alertas todavía no está conectado (la base sí:
  las alertas se guardan en la tabla `zone_alerts`). Es una fase aparte.
- Las **rentas** del analizador son estimadas; se sustituyen con listados reales
  en una fase posterior. Todo el sitio lo aclara.
- `supabase_schema.sql` es solo para Supabase; puedes borrarlo del deploy si
  prefieres no servirlo (es inofensivo, no contiene llaves).
