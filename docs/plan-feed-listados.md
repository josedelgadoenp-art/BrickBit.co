# Plan: feed de listados reales (el salto de demo → herramienta de asesoría)

**Objetivo:** reemplazar los tres números hoy estimados/vacíos —**precio de compra/m²**,
**renta/yield** e **inventario disponible**— por datos reales de listados. Es la palanca
#1 para que BrickBit deje de ser demo y pase a ser asesoría confiable.

Hoy: `data/inmuebles.json` y `data/mercado.json` traen `n_listados: 0`; el analizador
autocompleta precio con `precio/m² típico × superficie` y renta con el `yield` de la zona
(estimaciones marcadas en ámbar "est."). El mapa muestra un banner de "propiedades
individuales al conectar listados reales (Fase 1)".

---

## 1) De dónde salen los datos (elige una vía)

| Vía | Qué es | Costo/fricción | Legalidad | Recomendación |
|---|---|---|---|---|
| **A. API/partner con licencia** | Un portal o agregador (p. ej. acuerdo comercial con una inmobiliaria, MLS local, o proveedor de datos como los que licencian portales) te da un feed autorizado. | Contrato + posible cuota mensual. | ✅ Limpio si hay contrato. | **La mejor** para producción. Empieza por 1–3 ciudades piloto. |
| **B. Alianza con inmobiliarias/brokers** | Corredores suben su inventario a BrickBit (o te pasan un CSV/Sheet periódico) a cambio de leads. | Bajo costo; requiere ventas/relaciones. | ✅ Los datos son suyos y los comparten. | **Excelente arranque**: alинea con Financial (leads) y da inventario real gratis. |
| **C. Scraping de portales** | Extraer listados públicos. | Técnico + se rompe seguido. | ⚠️ Suele violar los Términos de Servicio; riesgo legal y de bloqueo (ya bloqueado en este proyecto). | **Evitar** para un producto de asesoría. Solo como sondeo interno, nunca como fuente publicada. |
| **D. Datos abiertos / referencias** | SHF, INEGI, notarías, avalúos publicados. | Gratis. | ✅ | Complemento (ya se usa SHF), **no** sustituye listados de venta/renta. |

**Camino sugerido:** **B (alianza)** para arrancar con inventario real sin costo y con
sinergia de leads, migrando a **A (licencia)** cuando el volumen lo justifique.

---

## 2) Formato de datos (contrato único, venga de donde venga)

Normaliza todo a este esquema. Escribe un archivo por ciudad o uno global
`data/inmuebles.json` (para el sitio estático) y/o una tabla `listings` en Supabase
(para búsqueda/actualización en vivo).

```json
{
  "generado": "2026-07-09T00:00:00Z",
  "fuente": "Inmobiliaria X (alianza) | Portal Y (licencia)",
  "listados": [
    {
      "id": "abc123",
      "zona": "Querétaro",           // debe empatar EXACTO con las 32 zonas de estados.json
      "operacion": "venta",          // venta | renta
      "tipo": "departamento",        // casa|departamento|terreno|local|oficina|bodega
      "precio": 3200000,             // MXN. En renta = renta mensual
      "m2": 78,                      // superficie construida (o de terreno si aplica)
      "precio_m2": 41025,            // precio / m2 (calcúlalo si no viene)
      "recamaras": 2,
      "banos": 2,
      "lat": 20.5931, "lng": -100.3899,
      "url": "https://...",          // ficha original (para citar la fuente)
      "publicado": "2026-06-30",
      "actualizado": "2026-07-08"
    }
  ]
}
```

**Reglas de honestidad (mantener):**
- Un dato es "real" solo si viene de un listado con `url`/fuente citable. Si se deriva
  (mediana de la zona, interpolación), va en **ámbar "est."** como hoy.
- El precio/m² de zona debe calcularse de una **muestra suficiente** (sugerido ≥ 8
  listados de esa zona/tipo en los últimos 90 días); si no, se marca estimado.
- La **renta/yield** real = mediana de rentas ÷ mediana de precios de venta comparables;
  hasta tenerla, se sigue mostrando el yield estimado (ya marcado).

---

## 3) Dónde se enchufa en el código (mínimos cambios)

1. **`data/inmuebles.json`** — poblarlo con el esquema de arriba (hoy `n_listados: 0`).
2. **`analizador.html` → `onZona()`** — si hay ≥ N listados reales para la zona, precargar
   `precio` y `renta` con la **mediana real** y **ocultar la etiqueta "est."**; si no,
   mantener la estimación actual (ya implementado el toggle de "est.").
3. **`mapa.html`** — la búsqueda de "propiedades/locales individuales" y el "ROI por
   propiedad" ya tienen el banner "se activan al conectar listados reales (Fase 1)".
   Al existir el feed: listar propiedades reales en el panel del asesor y quitar el banner.
   El parser de búsqueda por IA ya existe (Worker `/api/claude`) y devuelve filtros
   (`tipo`, `operacion`, `presupuesto_max`, etc.) que casan 1:1 con el esquema del feed.
4. **`estados.json`** — recalcular `precio_m2` real por zona desde el feed en el pipeline
   de datos; conservar `fuentes.precio` = "listados (N muestras, fecha)" o "estimado".
5. **Supabase (opcional, para vivo)** — tabla `listings` + un job que refresque el feed
   diario/semanal y regenere `data/inmuebles.json` en el build de Netlify.

---

## 4) Fases realistas

- **Fase 0 (1–2 semanas):** cerrar 1 alianza (vía B) en **una ciudad piloto** (p. ej.
  Querétaro o CDMX). Recibir un CSV/Sheet de su inventario.
- **Fase 1:** script que normaliza ese CSV → `data/inmuebles.json` (esquema §2) y lo
  commitea/despliega. Encender precio/renta reales en el analizador para esa zona.
- **Fase 2:** activar el listado de propiedades individuales en el mapa + ROI por
  propiedad (el motor de cálculo ya existe en `calcProyectoLocal`/`runIA`).
- **Fase 3:** automatizar el refresco (job programado) y ampliar a más ciudades;
  evaluar migrar a un proveedor con licencia (vía A) cuando el volumen lo pida.

**Criterio de "ya es asesoría" por zona:** precio, renta e inventario provienen de
listados reales con fuente citable y muestra suficiente. Mientras tanto, esa zona sigue
mostrando sus números en ámbar "est." — honesto y sin sobrepromesas.
