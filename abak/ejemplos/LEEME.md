# Análisis de ejemplo

Los ejemplos viven en `apps/web/src/lib/ejemplos.ts`, que es lo que carga el
menú «Ejemplos» de la interfaz. Se listan aquí para que se puedan encontrar
desde el repositorio.

- **¿Qué explica el precio de la vivienda?** (`hedonico`)
- **¿La ubicación importa? (econometría espacial)** (`espacial`)
- **Pronóstico del PIB y respuesta a un choque** (`macro`)
- **¿Qué arrastra la construcción? (insumo-producto)** (`insumo`)
- **Inversión y crecimiento (panel de entidades)** (`panel`)
- **Predecir el gasto en vivienda (XGBoost)** (`ml`)

Para abrir uno sin la interfaz, cópialo del archivo de arriba y mándalo a
`POST /api/v1/ejecuciones` con la forma `{"grafo": {...}}`.
