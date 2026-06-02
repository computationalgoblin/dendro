# Contrato Bloque 31 — Experiencia inmersiva de creación narrativa

## 31.1 Objetivo

Transformar la Desktop App en una experiencia inmersiva de creación narrativa, evitando la apariencia de panel técnico, CRUD administrativo o interfaz tipo hoja de cálculo.

La aplicación deberá sentirse como un espacio de creación, exploración y dirección narrativa, manteniendo internamente todos los servicios, modelos, validaciones y reglas de persistencia ya existentes.

El objetivo no es añadir nuevos modelos de dominio, sino reorganizar la experiencia de usuario sobre la base actual.

## 31.2 Principios de producto

1. Una sola ventana principal.
2. No se abrirán ventanas externas para editar entidades, relaciones, campañas, escenas, notas, candidatos o importaciones.
3. Toda edición se realizará dentro de la ventana principal mediante paneles laterales, drawers, overlays internos o navegación contextual.
4. La pantalla inicial no será un dashboard técnico.
5. La pantalla inicial mostrará únicamente tres entradas principales: Creación, Galería, Sesión.
6. Configuración, apertura de proyecto, guardado, cierre, ajustes IA y diagnóstico estarán en una zona discreta de la pantalla inicial, utilizando preferentemente iconografía limpia y consistente.
7. Al entrar en Creación, Galería o Sesión, toda la pantalla se dedicará a ese espacio.
8. Dentro de cada espacio solo existirá un mecanismo claro y visualmente discreto de retorno a la pantalla inicial.
9. En modo normal no se mostrarán IDs, JSON, metadata cruda, listas tipo Python, nombres internos de clases ni campos técnicos.
10. Los datos técnicos solo serán visibles en modo avanzado/debug.
11. La UI no accederá directamente a persistencia; deberá usar controllers/services.
12. La IA nunca mutará canon directamente; generará sugerencias, candidatos o previews.
13. Las reglas de canon, visibilidad, secretos, pistas, perfiles de exportación y campaña deberán respetarse en toda acción visual o IA.
14. La experiencia visual debe priorizar claridad, inmersión, composición, calma, movimiento moderado y reducción de ruido.

## 31.3 Estética visual

1. Estética inspirada en estudios creativos, cuadernos de diseño y espacios de trabajo contemplativos.
2. Predominio de superficies limpias, jerarquía visual clara, tipografía cuidada y uso generoso del espacio en blanco.
3. Paleta de colores claros, naturales y refinados, inspirada en materiales orgánicos, luz suave y paisajes serenos.
4. Colores funcionales para distinguir entidades, relaciones y estados narrativos sin ruido visual.
5. Animaciones suaves y discretas orientadas a reforzar la comprensión espacial.
6. Componentes visuales consistentes en toda la aplicación.
7. Sensación general de estudio creativo, escritorio de autor o cuaderno digital de worldbuilding.
8. Uso preferente de símbolos e iconografía en botones y acciones principales.
9. La estética de Dendro transmitirá serenidad, solidez, profesionalidad y profundidad narrativa.

## 31.4 Pantalla inicial

La pantalla inicial funcionará como portal inmersivo, no como dashboard.

Deberá incluir:
1. Tres tarjetas centrales: Creación, Galería, Sesión. Cada una con título, descripción breve, icono/tratamiento visual, estado contextual.
2. Zona discreta de proyecto y configuración: nuevo, abrir, guardar, cerrar, ajustes app, ajustes IA, selector modo avanzado, diagnóstico.
3. Estado del proyecto actual de forma no invasiva.
4. Estado de IA de forma no invasiva.
5. Ausencia de tablas, contadores técnicos, IDs o logs en modo normal.
6. Composición visual limpia, equilibrada y contemplativa.

Queda fuera: dashboard técnico, listas administrativas, logs visibles, menús densos, accesos directos a módulos internos.

## 31.5 Navegación inmersiva

Al entrar en cualquiera de los tres espacios principales:
1. La pantalla completa se dedicará al espacio seleccionado.
2. Existirá un mecanismo visual sencillo para volver a la pantalla inicial.
3. No se mantendrá sidebar técnica permanente si rompe la inmersión.
4. Las herramientas propias del espacio se mostrarán como controles contextuales.
5. Las vistas internas evitarán sensación de pestañas técnicas acumuladas.
6. Transiciones entre espacios reforzarán continuidad visual mediante animaciones suaves.

## 31.6 Espacio Creación

La entrada principal será un grafo narrativo visual.

### Grafo central (lienzo base)
- Ocupará el centro de la pantalla como vista principal.
- Paneles y herramientas laterales ocultos por defecto, despliegue contextual al acercar cursor.
- Nodos derivados de entidades existentes.
- Aristas derivadas de relaciones existentes.
- Colores de nodo/arista según tipo (paleta §31.3).
- Nombre y descripción breve en cada nodo.
- Indicadores visuales de estado: canon, borrador, oculto, sugerencia IA.
- Zoom, pan y enfoque de nodo.
- Navegación directa arrastrando sobre el lienzo.
- Layout automático básico.
- El grafo es siempre vista derivada del core, nunca base de datos paralela.

### Funcionalidades avanzadas del grafo (post-T03)
- Filtros complejos por tipo, capa, dominio, campaña, sesión.
- Búsqueda avanzada por nombre/contenido.
- Modo Worldbuilding: capas como elementos navegables de primer nivel.
- IA general: análisis contextual, sugerencias de nodos/relaciones, coherencia narrativa (§31.8).
- Sugerencias IA con tratamiento visual diferenciado (§31.8).
- Overlays de coherencia y análisis (§31.8).

### Nodos (§31.6.2)
Cada nodo representa un objeto narrativo. Muestra en modo normal: nombre, tipo visual, color, descripción breve, estado, nunca ID interno.

### Panel lateral de nodo (§31.6.3)
Se abre dentro de la ventana principal con animación suave. Muestra: nombre, tipo, descripción, cuerpo, notas, estado canon, visibilidad, relaciones, apariciones, campañas, secretos/pistas, capas/dominios, acciones edición, acciones IA. Permite editar todo, guardar, cancelar. Datos técnicos solo en modo avanzado.

### Relaciones visuales (§31.6.4)
Flechas/conexiones con dirección, tipo en lenguaje humano, color, etiqueta. Punto seleccionable para abrir detalle.

### Panel lateral de relación (§31.6.5)
Origen, destino, tipo, descripción, estado, intensidad, notas, evidencia, acciones IA. Permite editar, archivar, crear escena, sugerir conflicto.

### Creación visual de relaciones (§31.6.6)
Drag nodo sobre nodo → selector tipo (popup contextual, no QDialog) → crear mediante servicios → grafo se actualiza → panel lateral se abre.

## 31.7 Contexto narrativo para IA (NarrativeContextBuilder)

Servicio de aplicación que construye contexto estructurado para: entidad, relación, escena, campaña, sesión, selección de grafo, facción/front, secreto/pista, WritingUnit.

Contexto incluye según procede: proyecto activo, campaña activa, tono, género, realismo, sistema de juego, capas, dominios, selección, vecindad narrativa, escenas/sesiones vinculadas, secretos/pistas permitidos por visibilidad, historial, fuentes, candidatos pendientes, issues, restricciones canon, perfil audiencia.

Respecta: visibilidad, secretos no revelados, pistas no entregadas, perfil GM/jugador/público, canon vs candidato, importación no aceptada, configuración campaña.

La IA puede recibir candidatos relacionados marcados explícitamente como no-canon si la acción lo requiere, pero nunca los mezclará con canon ni los usará como hechos confirmados.

## 31.8 Acciones IA contextuales

Acciones sobre nodo: generar texto, mejorar, sugerir relaciones, conflicto, secretos, pistas, detectar contradicciones, resumir, crear candidato.
Acciones sobre relación: profundizar, evolución, escena, contradicción, secreto/pista, candidato.
Acciones sobre grafo: nodos faltantes, relaciones faltantes, zonas aisladas, inconsistencias, tramas emergentes.

Todas usan NarrativeContextBuilder. Todas producen Candidate/preview/sugerencia revisable. Nunca canon directo.

Sugerencias visuales en grafo: nodos/relaciones propuestas con tratamiento visual diferenciado (paleta §31.3). Acción visible para aceptar/canonizar. Al canonizar: se convierte en entidad/relación real mediante servicios. Candidate conserva source=AI, action_type, context_hash/resumen, target object. Aceptar sugerencia crea history/source si el dominio lo soporta.

Análisis de coherencia narrativa sobre canon visible, considerando relaciones, dependencias, contradicciones, vacíos y capas de worldbuilding activas. Resultados reflejados visualmente en el grafo mediante indicadores armoniosos. Ninguna observación modifica canon automáticamente.

## 31.9 Configuración creativa

Proyecto: nombre, género, tono, realismo, estilo narrativo, capas worldbuilding, visibilidad, preferencias IA.
Campaña: mundo, sistema juego, tono, género, realismo, temas, notas privadas, resumen público, visibilidad, límites.

IA usará esta configuración en toda generación contextual.

## 31.10 Espacio Galería

Espacio para explorar y contemplar material creado. No será tabla técnica.

Incluye: vista cards, vista mural, vista por tipo/campaña/localización/facción, secretos/pistas (autorizado), buscador, filtros, agrupaciones.

Cada card: nombre, tipo, icono/color, descripción breve, estado, relaciones destacadas, apariciones, imagen/placeholder/símbolo.

Al seleccionar: detalle limpio en misma ventana (RightDrawer), sin ID, sin JSON, técnicos en modo avanzado. Si no hay contenido: EmptyState estético.

Experiencia favorece exploración tranquila, lectura cómoda y contemplación.

## 31.11 Espacio Sesión

Espacio inmersivo para campaña de rol: preparación, dirección en vivo y post-sesión.

Fase A — Shell + campaña:
Selector campaña, estado campaña, clocks visibles, frentes activos, facciones activas, sin datos técnicos en modo normal.

Fase B — Preparación y escenas:
Escenas preparadas navegables, secretos ocultos/revelados, pistas pendientes/entregadas, detalle en RightDrawer.

Fase C — Live/Post inmersivo:
Sesión activa con controles de dirección en vivo, post-sesión: resumen, semillas, issues. Integración con IA contextual (T07/T08).

## 31.12 Modo avanzado

Ocultación completa de datos técnicos en modo normal. IDs, JSON, metadata, campos internos, source_ids, custom fields solo en modo avanzado/debug activable desde configuración.

Toggle global afecta TODOS los espacios. Estado se persiste entre sesiones. Indicador visual discreto cuando activo.

Auditoría estática: escaneo de textos visibles en modo normal para patrones de ID/JSON en paneles principales.

## 31.13 Reglas transversales

1. No romper CLI ni servicios existentes.
2. No eliminar vistas técnicas; reubicarlas en modo avanzado.
3. Sin IDs/JSON en modo normal. En modo avanzado sí pueden aparecer.
4. Paleta y tipografía según §31.3.
5. python -m pytest tests/architecture/ -q debe pasar tras cada ticket.

## 31.14 Decisiones de producto fijadas

1. La pantalla inicial no es un dashboard. Es una home inmersiva.
2. No se permiten ventanas externas para flujos normales. Criterio de rechazo.
3. El grafo no es una feature más. Es la entrada principal de Creación.
4. IA contextual exige NarrativeContextBuilder.
5. QDialog/QMessageBox solo para errores críticos y confirmaciones destructivas. Prohibidos como editor.

## 31.15 Dependencias

- Bloque 30 completado.
- PySide6 >= 6.7.0.
- Motor de grafo visual (QGraphicsScene/QGraphicsView base, evaluable en T03).

## 31.16 Orden de implementación recomendado

```
T01 — Home inmersiva y navegación fullscreen
T02 — RightDrawer / sin ventanas externas
T11 — Modo avanzado y ocultación técnica
T03 — Graph Canvas mínimo
T04 — Panel contextual de nodo
T05 — Panel contextual de relación
T06 — Drag-to-relate
T07 — NarrativeContextBuilder (puede ir en paralelo desde B30)
T08 — Acciones IA contextuales
T09 — Galería inmersiva
T10A — Session shell + campaña/clocks/fronts/facciones
T10B — Preparación y escenas
T10C — Live/Post inmersivo
T12 — QA Windows UX y cierre
```
