# Conjuntos de ejemplo — de dónde sale cada dato

Principio de la casa: **todo dato estimado o simulado se marca como tal.** Estos
conjuntos existen para aprender a usar Ábaco y para probar el motor, no para
citarse en un documento. Ninguno debe presentarse como evidencia.

| Archivo | Qué es | Origen |
|---|---|---|
| `mexico_estados.csv` | Corte transversal de las 32 entidades | **Mixto** (ver abajo) |
| `mexico_macro_trimestral.csv` | 84 trimestres, 2005T1–2025T4 | **Simulado**, calibrado a órdenes de magnitud reales |
| `panel_estados_anual.csv` | Panel 32 entidades × 15 años | **Simulado** |
| `mexico_insumo_producto.csv` | Matriz de 12 sectores | **Simulado**, con estructura tipo INEGI |
| `hogares_vivienda.csv` | 2,400 hogares | **Simulado**, con forma tipo ENIGH |

## `mexico_estados.csv`, columna por columna

**Reales** (vienen de `data/estados.json` de BrickBit, que a su vez cita a SHF):

- `entidad`, `lat`, `lng`
- `plusvalia_pct` — SHF, cierre anual
- `valor_mediano_vivienda` — SHF, estatal

**Estimados por BrickBit** (así vienen ya marcados en el sitio, en ámbar):

- `precio_m2`, `yield_pct`, `dias_en_mercado`, `ciclo`

**Simulados aquí, sólo para los ejemplos** — están correlacionados con el precio
real para que las regresiones de demostración den coeficientes con sentido, pero
**no miden nada**:

- `ingreso_hogar_mensual`, `escolaridad_anios`, `densidad_hab_km2`,
  `poblacion_miles`, `empleo_formal_pct`, `credito_hipotecario_pc`

## Reproducirlos

```bash
python abaco/tools/generar_ejemplos.py
```

La semilla está fija (`20260905`), así que el resultado es idéntico corrida tras
corrida. Si cambia `data/estados.json`, la parte real de `mexico_estados.csv`
cambia con él.
