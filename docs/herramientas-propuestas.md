## Implementado en esta continuación

`laboratorio.html` incorpora tres herramientas de cálculo local: flipping,
comparación de inmuebles y estrés de renta. La comparación usa los datos
capturados por el usuario; no afirma obtener anuncios verificados. El usuario
puede guardar manualmente los escenarios en este equipo, exportar sus supuestos
en JSON e imprimir el escenario activo.

Las siguientes propuestas siguen siendo ampliaciones futuras, sujetas a sus
fuentes e integraciones:

# Próximas herramientas para BrickBit

Propuestas de producto basadas en las capacidades encontradas en el repositorio.
No están implementadas en esta intervención. El sitio ya tiene comparación,
pro-forma, portafolio sugerido, seguimiento de listados y lógica de alertas;
repetirlos con otro nombre aportaría poco.

| Prioridad | Herramienta | Valor concreto | Primera versión y datos necesarios |
|---|---|---|---|
| 1 | Expediente de comparables verificables | Explicar por qué una propiedad parece cara o barata, con evidencia revisable. | Comparables seleccionables por radio, tipo, superficie y fecha; exclusiones justificadas, conteo de muestra y PDF con fuentes. Distinguir precios anunciados de cierres confirmados y deduplicar anuncios. Amplía los comparables ya existentes. |
| 2 | Prueba de resistencia de inversión | Encontrar qué tendría que salir mal para perder dinero. | Matriz de renta, vacancia, precio de salida, retraso y tasa; punto de equilibrio y escenarios de flujo. Partir de la pro-forma existente; mostrar supuestos editables y evitar probabilidades ficticias. |
| 3 | Monitor de calidad y frescura de datos | Saber cuándo una cifra es confiable y cuándo falta información. | Fecha de corte por fuente/ciudad, cobertura, tamaño de muestra, cambios anómalos y estado de actualización; separar dato observado, derivado y estimado. Reutilizar metadatos del inventario y de los JSON. |
| 4 | Expediente de predio | Reunir lo que hace falta revisar antes de desarrollar. | Parcela, documentos aportados, enlaces a fuentes oficiales y tareas de validación de uso de suelo, servicios, riesgos y restricciones. Registrar vigencia y estado «no verificado» cuando corresponda; no generar dictámenes legales automáticos. |
| 5 | Bitácora de decisión en equipo | Permitir que inversionista, arquitecto y analista trabajen sobre el mismo escenario. | Escenarios versionados, comentarios privados, archivos y comparación de supuestos entre versiones. Permisos por proyecto y trazabilidad; aprovechar los análisis guardados. |
| 6 | Evaluación del modelo fuera de calibración | Medir si el pronóstico mejora de verdad cuando llegan datos nuevos. | Pronósticos congelados con fecha, error por ciudad/horizonte, cobertura de intervalos y comparación con baselines en un periodo separado. Publicar un tablero metodológico alimentado por un proceso reproducible. |

## Orden sugerido

Primero consolidaría **calidad de datos + comparables verificables**. La
diferenciación sería que cada conclusión se pueda explicar y revisar. Después
añadiría pruebas de resistencia y colaboración, porque convierten la exploración
en un proceso de decisión compartido.

La bitácora podría sostener un plan profesional con proyectos, permisos e
informes; es una hipótesis comercial para validar con usuarios, no una previsión
de ingresos. Mediría análisis terminados, comparables revisados, escenarios
guardados y retorno de usuarios, con un esquema de consentimiento adecuado.

No priorizaría más recorridos 3D antes de validar uso de los existentes. Compra
fraccionada y cierre de operaciones requieren primero definir operación,
estructura jurídica y proveedores; no son solamente mejoras de interfaz.
