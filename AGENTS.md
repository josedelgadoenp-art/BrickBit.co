# BrickBit — reglas para agentes de código

Proptech mexicana. **Sitio 100% estático**: HTML/CSS/JS vanilla, sin build, sin framework.
Se despliega en Netlify publicando el repositorio entero. Idioma: **español (MX)**.

Si vas a escribir código aquí, lee esto antes. Son reglas aprendidas rompiendo cosas en
producción, no preferencias de estilo.

## Nunca

1. **No inventes que un dato es real.** Todo dato estimado se marca en ámbar `#F5C277` con la
   etiqueta "est.". Los datos reales citan su fuente (SHF, INEGI/DENUE, Banxico…). El ámbar
   está reservado para eso: no lo uses de color decorativo, y no marques como estimado algo
   que tiene fuente.
2. **No pongas sombras de color.** Nada de `box-shadow` ni `text-shadow` con color (glow).
   La paleta v2 es mate. Sombras sólo neutras, `rgba(0,0,0,…)`.
3. **No toques `financial.html` ni `aviso-de-privacidad.html`.** Tienen su propia paleta clara
   (alianza GNP) y no siguen la v2.
4. **No quites la casilla de consentimiento** de ningún formulario. La LFPDPPP (art. 8) exige
   consentimiento expreso para datos patrimoniales o financieros, y los formularios capturan
   ingreso. Un "al dar clic aceptas" no basta.
5. **No saques los scripts a archivos externos.** Van embebidos en cada HTML. Un `.js` por
   página provoca renders en blanco al abrir el archivo standalone.
6. **No cargues librerías desde un CDN.** Van auto-hospedadas en `assets/`. Las tipografías de
   Google son la única excepción (fallan de forma elegante).
7. **No crees una carpeta `/financial/`.** Competiría con el rewrite de `/financial` en
   `netlify.toml`. Los archivos viven en la raíz.
8. **No pongas tokens en la URL.** `DIAG_ADMIN_TOKEN` va siempre en el header `x-admin-token`;
   en la URL quedaría en los logs de Netlify y en el historial del navegador.

## Trampas que ya costaron tiempo

- Un comentario que contenga `</script>` dentro de un `<script>` inline **rompe la etiqueta**.
  Escríbelo `<\/script>`.
- Los polígonos 3D de Google **no renderizan si el anillo no cierra**: hay que repetir el
  primer punto al final.
- La calidad de los tiles 3D depende de que la cámara esté **quieta**. La órbita continua
  impide que refinen, así que va siempre como botón opcional, nunca por defecto.
- La navegación es **in-page**, no por `?c=slug`: esos parámetros fallan en deploys estáticos.
- Si tocas un `overflow` dentro de una media query, **mide el alto del `body` después**. Quitar
  el scroll interno de una lista estiró una página a 41,928 px en móvil.
- OpenStreetMap no sirve teselas `@2x`: si dejas el `{r}` en el patrón, cada tesela da 404.

## Cómo se captan datos

El valor primero, el contacto después. Los formularios entregan su resultado **antes** de pedir
nombre y teléfono, y no se envía nada al servidor hasta que la persona entrega sus datos a
propósito. La versión anterior pedía el teléfono en el paso 2 y una campaña con ~11.7k de
alcance no produjo un solo registro.

Si fijas un supuesto (edad de retiro, tasa, horizonte), **decláralo en pantalla**. No se
esconden números.

## Qué no se publica

`netlify.toml` cierra con redirect `force` a 404: `/netlify/*`, `/scripts/*`, `/tools/*`,
`/backend/*` y los `.md` de la raíz uno por uno — `/*.md` **no** funciona, Netlify no admite
sufijo tras el splat. Si añades un `.md` en la raíz, añade también su redirect.

## Dónde está cada cosa

| | |
|---|---|
| `index.html` `mapa.html` `analizador.html` `panel.html` | núcleo del sitio |
| `zona3d.html` `pulso.html` `cine.html` `versus.html` | experiencias 3D (Google Maps 3D) |
| `financial.html` `analisisfinanciero.html` `gmm.html` | Financial — paleta propia, ver regla 3 |
| `netlify/functions/*.mjs` | leads, diagnóstico, pase HMAC de médicos |
| `data/*.json` | datos estáticos, se leen por `fetch` |
| `zona/` | 33 páginas SEO + hub |
| `tools/` | scripts de mantenimiento, no se publican |

Los detalles completos, con el porqué de cada decisión, están en `CLAUDE.md`. Si vas a tocar
algo que no está aquí, léelo antes.
