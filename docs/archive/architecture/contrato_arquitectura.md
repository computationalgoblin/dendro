> ⚠️ **SUPERSEDED** — Este documento describe el producto pre-BETA1 (suite amplia con
> RPG/sesión/campaña/galería/escritura). El producto actual está definido en
> `docs/architecture/BETA1_legacy_cleanup_audit.md` (SSOT vigente).
> Los principios de arquitectura limpia (sección 2) siguen siendo válidos.

# Contrato de Arquitectura de Aplicación

# Plataforma de Creación Narrativa, Worldbuilding y Dirección de Partidas Asistida por IA

## 1. Definición general del producto

La aplicación será un software de escritorio orientado a la creación, organización, análisis y explotación narrativa de mundos, historias, escenarios y campañas de rol mediante una base de conocimiento estructurada, una interfaz visual basada en grafos semánticos, una base de datos navegable, herramientas de análisis de coherencia y una capa específica para la preparación y dirección de sesiones de rol.

La aplicación no será únicamente un editor de texto, una wiki, una herramienta de notas, un generador de contenido por IA, un gestor de campañas ni una visualización de grafos. La aplicación será un entorno integral de arquitectura narrativa en el que los elementos de un mundo, una historia o una campaña se modelan como entidades estructuradas, conectadas mediante relaciones semánticas, sometidas a reglas internas de coherencia, versionadas y asistidas por inteligencia artificial.

El objetivo principal de la aplicación será permitir al usuario crear, mantener, explorar y utilizar un corpus narrativo complejo sin perder control sobre el canon, la continuidad, la causalidad, el tono, la estructura narrativa ni la información revelada a los jugadores o lectores.

La aplicación deberá servir tanto a escritores como a directores de partidas de rol, pero su arquitectura deberá contemplar explícitamente las necesidades diferenciales de ambos perfiles. En el caso de escritores, la aplicación deberá facilitar la construcción de mundos, historias, arcos, personajes, escenas y estructuras narrativas. En el caso de directores de rol, la aplicación deberá facilitar la preparación de sesiones, la improvisación controlada, la gestión de secretos, la continuidad entre sesiones, la actualización del mundo tras la acción de los jugadores y la transformación del lore en material jugable.

La aplicación deberá funcionar como una fuente de verdad narrativa controlada por el usuario. La inteligencia artificial podrá proponer, analizar, completar, criticar, extraer, clasificar o transformar contenido, pero no deberá modificar el canon activo sin confirmación explícita del usuario.

---

## 2. Principios arquitectónicos fundamentales

### 2.1 Separación entre conocimiento, visualización e inteligencia artificial

La aplicación deberá separar conceptualmente y técnicamente tres capas:

1. La base de conocimiento narrativa.
2. Las interfaces de visualización, edición y navegación.
3. Los servicios de inteligencia artificial.

El grafo visual no deberá ser la base de datos primaria. El grafo será una representación interactiva de entidades y relaciones almacenadas en la base de conocimiento. La eliminación, modificación o filtrado de una vista de grafo no deberá implicar necesariamente la modificación del conocimiento persistente, salvo que el usuario ejecute una acción explícita de edición.

La inteligencia artificial no deberá ser la propietaria del conocimiento. La IA deberá operar sobre datos estructurados, contexto autorizado, restricciones narrativas y decisiones del usuario. Sus resultados deberán entrar en el sistema como sugerencias, hipótesis, análisis, borradores, candidatos o propuestas pendientes de aceptación.

### 2.2 Canon controlado por el usuario

El sistema deberá distinguir de forma explícita entre contenido canónico, contenido no canónico, contenido provisional, contenido descartado, contenido secreto, contenido hipotético y contenido contradictorio.

Ningún contenido generado, inferido, importado o transformado por IA deberá incorporarse automáticamente al canon definitivo sin aceptación expresa del usuario.

La aplicación deberá conservar la trazabilidad entre una afirmación narrativa y su origen. El origen podrá ser una creación manual, una importación documental, una generación IA, una modificación posterior, una sesión de rol, una nota del usuario o una inferencia aceptada.

### 2.3 Semántica fuerte de relaciones

La aplicación deberá tratar las relaciones entre elementos como entidades estructuradas de primer nivel. Una relación no será únicamente una línea visual entre dos nodos. Cada relación deberá poder expresar tipo, dirección, causalidad, temporalidad, intensidad, estado, visibilidad, fuente, fiabilidad y descripción.

El sistema deberá poder razonar sobre las relaciones, filtrarlas, visualizarlas, validarlas, transformarlas y utilizarlas como contexto para sugerencias o análisis.

### 2.4 Trazabilidad y reversibilidad

Todo cambio relevante sobre el corpus narrativo deberá poder ser rastreado. La aplicación deberá conservar historial suficiente para conocer qué cambió, cuándo cambió, por qué cambió, qué entidad o relación fue afectada y si el cambio provino del usuario, de una importación, de una sesión o de una sugerencia aceptada de IA.

El usuario deberá poder revisar cambios, comparar versiones y revertir modificaciones cuando sea necesario.

### 2.5 Compatibilidad con creación libre y creación estructurada

La aplicación deberá permitir tanto la creación espontánea como la creación guiada. El usuario deberá poder comenzar con una idea aislada, una ficha, una escena, una localización, un personaje, una facción, una cronología, un mapa conceptual, una estructura narrativa o un documento importado.

La aplicación no deberá imponer una metodología única de escritura, worldbuilding o dirección de rol. Deberá ofrecer marcos, plantillas, estructuras, análisis y sugerencias, pero siempre como herramientas opcionales.

### 2.6 Separación entre mundo, historia y campaña

La aplicación deberá distinguir entre al menos tres dominios narrativos:

1. Mundo o escenario.
2. Historia, relato, novela, guion o arco narrativo.
3. Campaña o partida de rol.

Un mundo podrá contener múltiples historias y campañas. Una historia podrá utilizar un subconjunto del mundo. Una campaña podrá alterar el estado del mundo a través de sesiones y decisiones de jugadores. Las entidades podrán pertenecer a uno o varios dominios, pero el sistema deberá conservar esa pertenencia de forma explícita.

### 2.7 Gestión diferencial de conocimiento público, privado y secreto

El sistema deberá gestionar explícitamente la diferencia entre:

1. Lo que es verdad en el canon.
2. Lo que cree un personaje.
3. Lo que sabe una facción.
4. Lo que sabe el director de partida.
5. Lo que saben los jugadores.
6. Lo que saben los personajes jugadores.
7. Lo que ha sido revelado en sesión.
8. Lo que está preparado pero no revelado.
9. Lo que es rumor, mentira, propaganda, interpretación errónea o hipótesis interna del mundo.

Esta distinción será obligatoria para el módulo de rol y recomendable para el módulo de escritura.

---

## 3. Modelo de dominio

### 3.1 Entidad narrativa

La entidad narrativa será la unidad básica de conocimiento. Toda pieza relevante del corpus deberá poder modelarse como entidad narrativa.

La entidad narrativa deberá admitir, como mínimo, los siguientes tipos conceptuales:

Personaje, localización, facción, cultura, especie, criatura, objeto, artefacto, evento, periodo histórico, escena, capítulo, sesión, conflicto, institución, religión, tecnología, sistema mágico, regla metafísica, regla física, ley social, idioma, símbolo, secreto, pista, rumor, recurso, amenaza, organización, comunidad, linaje, relación política, tradición, mito, documento interno, nota, regla de juego, encuentro, frente, arco narrativo, trama, subtrama, tema, motivo, consecuencia, pregunta abierta y decisión pendiente.

El sistema deberá permitir tipos personalizados definidos por el usuario. Los tipos personalizados deberán integrarse en las mismas capacidades generales que los tipos nativos: ficha, relaciones, grafo, búsqueda, filtros, IA, importación, exportación y análisis.

Cada entidad narrativa deberá tener, como mínimo, los siguientes campos estructurales:

1. Identificador único interno.
2. Nombre principal.
3. Nombres alternativos o alias.
4. Tipo de entidad.
5. Descripción breve.
6. Descripción extendida.
7. Estado de canon.
8. Estado de visibilidad.
9. Etiquetas.
10. Dominio de pertenencia.
11. Fuente u origen.
12. Fecha de creación.
13. Fecha de modificación.
14. Historial de versiones.
15. Relaciones entrantes.
16. Relaciones salientes.
17. Notas privadas del usuario.
18. Notas públicas o exportables.
19. Nivel de desarrollo.
20. Nivel de certeza.
21. Nivel de importancia narrativa.
22. Elementos asociados.
23. Restricciones narrativas aplicables.
24. Metadatos personalizados.

La entidad deberá admitir contenido textual libre, pero no deberá depender exclusivamente de texto plano. El sistema deberá favorecer la extracción de propiedades estructuradas cuando estas resulten útiles para análisis, búsqueda, consistencia y generación.

### 3.2 Estados de canon

La aplicación deberá soportar, como mínimo, los siguientes estados de canon:

1. Canónico.
2. Borrador.
3. Hipótesis.
4. Sugerido por IA.
5. Importado pendiente de validación.
6. Contradictorio.
7. Obsoleto.
8. Descartado.
9. Archivado.
10. Secreto canónico.
11. Secreto no confirmado.
12. Rumor interno del mundo.
13. Falso dentro del mundo.
14. Interpretación subjetiva.

El estado de canon deberá afectar a la forma en que la entidad se utiliza como contexto para IA, análisis, exportación, búsqueda y presentación. El usuario deberá poder configurar si determinados estados se incluyen o se excluyen en operaciones concretas.

### 3.3 Estados de visibilidad

La aplicación deberá distinguir entre visibilidad interna y externa.

La visibilidad interna determinará qué puede ver el usuario dentro de la aplicación en un contexto determinado. La visibilidad externa determinará qué puede exportarse, mostrarse o compartirse con jugadores, lectores o colaboradores.

La aplicación deberá soportar, como mínimo, los siguientes estados de visibilidad:

1. Privado del autor o director.
2. Visible para el usuario.
3. Visible para jugadores.
4. Visible para personajes concretos.
5. Visible para facciones concretas.
6. Revelado en sesión.
7. Revelado parcialmente.
8. Preparado pero no revelado.
9. Exportable.
10. No exportable.
11. Público dentro del mundo.
12. Secreto dentro del mundo.
13. Rumor.
14. Mentira conocida.
15. Información desconocida por todos los actores internos.

### 3.4 Nivel de certeza

La aplicación deberá permitir asignar un grado de certeza a entidades, relaciones y afirmaciones. El nivel de certeza deberá indicar si un elemento es definitivo, probable, posible, dudoso, contradictorio, especulativo o pendiente de validación.

La IA deberá respetar el nivel de certeza. Los elementos de baja certeza no deberán ser tratados como hechos definitivos salvo que el usuario lo autorice.

### 3.5 Afirmaciones narrativas

Además de entidades y relaciones, el sistema deberá poder representar afirmaciones narrativas. Una afirmación narrativa será una declaración estructurada sobre el mundo, una historia o una campaña.

Las afirmaciones podrán derivarse de descripciones textuales, importaciones, notas, sesiones o generación IA. Deberán poder tener estado de canon, fuente, certeza, visibilidad y vínculos con entidades.

El sistema de consistencia deberá poder operar sobre afirmaciones, no solo sobre entidades. Esto será necesario para detectar contradicciones internas que no estén expresadas como relaciones simples.

---

## 4. Sistema de relaciones semánticas

### 4.1 Relación narrativa

Una relación narrativa será una conexión semántica entre dos o más entidades, afirmaciones, eventos, escenas, sesiones o estructuras.

Cada relación deberá tener, como mínimo:

1. Identificador único.
2. Entidad origen.
3. Entidad destino.
4. Tipo de relación.
5. Dirección.
6. Descripción.
7. Intensidad.
8. Temporalidad.
9. Causalidad.
10. Estado de canon.
11. Estado de visibilidad.
12. Fuente.
13. Nivel de certeza.
14. Fecha o periodo de validez.
15. Condiciones de validez.
16. Consecuencias asociadas.
17. Notas.
18. Historial de cambios.

Las relaciones deberán poder ser binarias, direccionales, bidireccionales, jerárquicas, causales, temporales o contextuales. El sistema deberá admitir relaciones entre más de dos elementos cuando la semántica lo requiera.

### 4.2 Tipos de relación

El sistema deberá incluir una taxonomía inicial de relaciones, ampliable por el usuario.

La taxonomía deberá contemplar, como mínimo:

1. Pertenece a.
2. Contiene.
3. Está ubicado en.
4. Nació en.
5. Murió en.
6. Participó en.
7. Causó.
8. Fue causado por.
9. Gobierna.
10. Es gobernado por.
11. Sirve a.
12. Es enemigo de.
13. Es aliado de.
14. Ama.
15. Odia.
16. Teme.
17. Protege.
18. Persigue.
19. Conoce.
20. Desconoce.
21. Sospecha.
22. Oculta.
23. Revela.
24. Contradice.
25. Depende de.
26. Deriva de.
27. Simboliza.
28. Inspira.
29. Destruyó.
30. Creó.
31. Posee.
32. Busca.
33. Heredó.
34. Enseñó.
35. Traicionó.
36. Investiga.
37. Financia.
38. Controla.
39. Es controlado por.
40. Prohíbe.
41. Permite.
42. Está en conflicto con.
43. Tiene deuda con.
44. Debe lealtad a.
45. Está relacionado por sangre con.
46. Está relacionado políticamente con.
47. Está relacionado religiosamente con.
48. Está relacionado económicamente con.
49. Está relacionado militarmente con.
50. Está relacionado históricamente con.

El usuario deberá poder crear tipos de relación propios, definir sus campos específicos, establecer su dirección por defecto, configurar su representación visual y decidir si participan en análisis de consistencia.

### 4.3 Relaciones causales

Las relaciones causales deberán permitir encadenar decisiones, eventos, reglas del mundo y consecuencias.

El sistema deberá poder representar que una entidad, evento, regla o decisión produce efectos directos, efectos indirectos, efectos retardados, efectos condicionales o efectos hipotéticos.

El motor de IA y el motor de consistencia deberán poder utilizar relaciones causales para explorar consecuencias, detectar huecos explicativos y proponer desarrollos coherentes.

### 4.4 Relaciones temporales

Las relaciones temporales deberán permitir ordenar eventos, escenas, periodos, biografías, eras, sesiones, descubrimientos, revelaciones y cambios de estado.

El sistema deberá soportar:

1. Fechas absolutas del mundo.
2. Fechas relativas.
3. Periodos.
4. Orden parcial.
5. Antes de.
6. Después de.
7. Durante.
8. Simultáneo a.
9. Causa anterior a consecuencia.
10. Revelado en.
11. Preparado antes de.
12. Modificado después de.

El sistema no deberá exigir que todos los mundos tengan calendarios completos. Deberá admitir cronologías incompletas, vagas, míticas, contradictorias o deliberadamente inciertas.

### 4.5 Relaciones de conocimiento

El sistema deberá representar qué entidades conocen, ignoran, creen, malinterpretan, ocultan o revelan determinada información.

Estas relaciones serán fundamentales para campañas de rol, misterios, intrigas, secretos, investigaciones y tramas políticas.

Las relaciones de conocimiento deberán poder distinguir entre:

1. Saber un hecho verdadero.
2. Creer un hecho falso.
3. Sospechar un hecho verdadero.
4. Sospechar un hecho falso.
5. Haber oído un rumor.
6. Conocer una versión parcial.
7. Conocer una interpretación sesgada.
8. Ocultar deliberadamente información.
9. Haber recibido una pista.
10. Haber presenciado un evento.
11. Haber olvidado o perdido información.
12. Tener acceso potencial a una fuente.

---

## 5. Arquitectura de capas del mundo

### 5.1 Capas conceptuales

La aplicación deberá permitir organizar el worldbuilding en capas conceptuales. Estas capas no serán obligatorias ni impondrán un flujo único, pero deberán estar disponibles como estructura de análisis, navegación y generación.

El sistema deberá soportar, como mínimo, las siguientes capas:

1. Premisa estética y tonal.
2. Metafísica y cosmología.
3. Reglas fundamentales del mundo.
4. Física, naturaleza y restricciones materiales.
5. Geografía, clima y recursos.
6. Biología, especies, criaturas y ecologías.
7. Comunidades, culturas y sociedades.
8. Economía, política e instituciones.
9. Lenguaje, símbolos, arte y tradición.
10. Religión, mito, ideología y creencias.
11. Tecnología, magia y sistemas de poder.
12. Historia, eras, eventos y memoria colectiva.
13. Situación actual.
14. Conflictos activos.
15. Narrativa, trama, escenas y arcos.
16. Campaña, sesiones, jugadores y consecuencias.

El usuario deberá poder crear, modificar, ocultar o reorganizar capas. La aplicación deberá permitir que una entidad pertenezca a una o varias capas.

### 5.2 Propagación de consecuencias entre capas

La aplicación deberá permitir analizar cómo una decisión en una capa afecta a otras capas.

El sistema deberá soportar análisis descendente, ascendente y lateral:

1. Descendente: de principios abstractos a consecuencias concretas.
2. Ascendente: de elementos concretos a inferencias estructurales.
3. Lateral: de una institución, cultura, localización o conflicto a otros elementos del mismo nivel.

La IA deberá poder sugerir consecuencias, dependencias, contradicciones, oportunidades narrativas y elementos faltantes derivados de cambios en cualquier capa.

### 5.3 Grados de realismo

La aplicación deberá permitir configurar grados de realismo por proyecto, por capa y por operación de IA.

El grado de realismo deberá afectar a las sugerencias, análisis y detecciones de inconsistencia.

El sistema deberá contemplar, como mínimo:

1. Realismo bajo.
2. Realismo medio.
3. Realismo alto.
4. Realismo histórico.
5. Ciencia ficción blanda.
6. Ciencia ficción dura.
7. Fantasía mítica.
8. Fantasía verosímil.
9. Fantasía simbólica.
10. Surrealismo.
11. Weird fiction.
12. Realismo mágico.
13. Cuento de hadas.
14. Horror cósmico.
15. Horror psicológico.
16. Ucronía.
17. Distopía.
18. Pulp.
19. Épica.
20. Grimdark.

Estas categorías no deberán limitarse a etiquetas estéticas. Deberán influir en la tolerancia del sistema ante coincidencias, causalidad, escala, plausibilidad material, reglas internas, densidad de explicación y tipo de conflicto.

---

## 6. Marcos narrativos y estructuras importables

### 6.1 Definición de marco narrativo

Un marco narrativo será una estructura formal, temática o funcional que la aplicación podrá utilizar para analizar, guiar, organizar o generar contenido.

Los marcos narrativos no deberán funcionar como formularios obligatorios. Deberán actuar como lentes de análisis, restricciones opcionales, modelos de progresión, fuentes de tensión, detectores de huecos y generadores de propuestas.

### 6.2 Tipos de marcos

La aplicación deberá soportar, como mínimo, los siguientes tipos de marcos:

1. Estructuras de historia.
2. Estructuras de arco de personaje.
3. Estructuras de campaña.
4. Estructuras de misterio.
5. Estructuras de investigación.
6. Estructuras de horror.
7. Estructuras de tragedia.
8. Estructuras de aventura.
9. Estructuras de exploración.
10. Estructuras políticas.
11. Estructuras de facciones.
12. Estructuras episódicas.
13. Estructuras de temporada.
14. Estructuras de sandbox.
15. Estructuras de dungeon.
16. Estructuras de hexcrawl.
17. Estructuras de viaje.
18. Estructuras de revolución.
19. Estructuras de guerra.
20. Estructuras de caída o corrupción.
21. Estructuras de revelación.
22. Estructuras de conspiración.

### 6.3 Funciones de los marcos narrativos

La aplicación deberá permitir:

1. Asociar uno o varios marcos narrativos a un proyecto.
2. Asociar marcos distintos a partes distintas del proyecto.
3. Evaluar una historia, mundo o campaña contra un marco.
4. Detectar elementos ausentes respecto a un marco.
5. Detectar sobrecarga estructural.
6. Detectar desviaciones deliberadas.
7. Generar propuestas compatibles con el marco.
8. Adaptar contenido existente a un marco.
9. Comparar varios marcos aplicados al mismo corpus.
10. Crear marcos personalizados.
11. Importar marcos definidos por el usuario.
12. Desactivar un marco sin eliminar el contenido generado bajo su influencia.

### 6.4 Independencia entre marco y canon

La aplicación deberá distinguir entre el marco utilizado para generar o analizar contenido y el contenido finalmente aceptado como canon.

Un elemento generado bajo la influencia de un marco no deberá quedar permanentemente dependiente de dicho marco, salvo que el usuario configure esa dependencia.

---

## 7. Inteligencia artificial integrada

### 7.1 Principios de IA

La IA deberá operar como un sistema de asistencia, no como autoridad narrativa.

La IA deberá:

1. Respetar el canon activo.
2. Distinguir canon, borrador, hipótesis, rumor, secreto y contradicción.
3. Indicar qué contexto ha utilizado.
4. Explicar el motivo narrativo o estructural de sus sugerencias cuando sea necesario.
5. Señalar posibles impactos sobre entidades y relaciones existentes.
6. Identificar contradicciones potenciales antes de aplicar propuestas.
7. Permitir aceptación, edición, rechazo o archivo de sus resultados.
8. Evitar sobrescribir contenido sin consentimiento del usuario.
9. Mantener trazabilidad entre sugerencia y resultado aceptado.
10. Adaptarse a tono, género, realismo, estructura y restricciones del proyecto.

### 7.2 Modos funcionales de IA

La aplicación deberá incluir, como mínimo, los siguientes modos funcionales de IA:

1. Generación.
2. Expansión.
3. Crítica.
4. Consistencia.
5. Causalidad.
6. Tono.
7. Estructura.
8. Continuidad.
9. Extracción documental.
10. Resumen.
11. Reescritura.
12. Conversión de formato.
13. Preparación de sesión.
14. Improvisación controlada.
15. Actualización post-sesión.
16. Análisis de jugabilidad.
17. Gestión de secretos.
18. Análisis de facciones.
19. Depuración de duplicados.
20. Clasificación y etiquetado.

Cada modo deberá tener reglas de contexto, permisos y salida propios.

### 7.3 IA generativa

El modo generativo deberá poder proponer entidades, relaciones, eventos, escenas, conflictos, facciones, localizaciones, secretos, pistas, objetos, tradiciones, instituciones, tecnologías, sistemas mágicos, culturas, consecuencias, nombres y descripciones.

Toda generación deberá producir resultados estructurados cuando sea posible. Los resultados generados deberán poder entrar al sistema como candidatos, no como canon automático.

El sistema deberá permitir configurar:

1. Número de propuestas.
2. Grado de originalidad.
3. Grado de coherencia con el canon.
4. Grado de riesgo creativo.
5. Tono.
6. Género.
7. Marco narrativo aplicable.
8. Capas del mundo afectadas.
9. Restricciones de longitud.
10. Restricciones de contenido.
11. Inclusión o exclusión de elementos existentes.
12. Nivel de detalle.
13. Salida como entidad, relación, escena, nota, resumen, tabla o propuesta mixta.

### 7.4 IA crítica

El modo crítico deberá analizar contenido existente y detectar problemas narrativos, estructurales, tonales, causales o funcionales.

Deberá poder identificar:

1. Contradicciones.
2. Redundancias.
3. Elementos infrautilizados.
4. Elementos sobredesarrollados.
5. Falta de motivación.
6. Falta de conflicto.
7. Conflictos sin consecuencia.
8. Causalidad débil.
9. Exposición excesiva.
10. Elementos no jugables.
11. Personajes pasivos.
12. Facciones sin objetivo.
13. Localizaciones sin función.
14. Secretos sin pistas.
15. Pistas sin revelación asociada.
16. Escenas sin decisión significativa.
17. Tramas sin presión.
18. Finales no preparados.
19. Giros no sembrados.
20. Roturas de tono.
21. Roturas de género.
22. Escalas incoherentes.
23. Errores de continuidad.

### 7.5 IA causal

El modo causal deberá analizar causas, consecuencias y dependencias.

Deberá poder:

1. Propagar consecuencias de una decisión narrativa.
2. Identificar causas necesarias para un evento.
3. Detectar consecuencias ausentes.
4. Detectar eventos sin causa suficiente.
5. Identificar impactos sociales, políticos, económicos, religiosos, ecológicos, históricos, personales y dramáticos.
6. Proponer efectos directos, indirectos y retardados.
7. Diferenciar consecuencias seguras, probables, posibles e improbables.
8. Señalar entidades afectadas.
9. Crear relaciones causales candidatas.
10. Sugerir conflictos derivados.

### 7.6 IA de tono

El modo de tono deberá adaptar análisis, sugerencias y textos a parámetros tonales del proyecto.

Deberá poder trabajar con tono global, tono por región, tono por historia, tono por facción, tono por escena y tono por sesión.

El sistema deberá permitir bloquear tono cuando el usuario no quiera que una sugerencia altere la identidad estética del proyecto.

### 7.7 IA estructural

El modo estructural deberá operar sobre marcos narrativos. Deberá evaluar el corpus frente a una estructura seleccionada, detectar huecos, proponer correspondencias, sugerir transformaciones y advertir desviaciones.

El análisis estructural deberá distinguir entre ausencia problemática y desviación deliberada. El usuario deberá poder marcar una desviación como intencionada para que no sea reportada repetidamente como error.

### 7.8 IA de continuidad

El modo de continuidad deberá responder preguntas sobre el canon, el estado de sesiones, la cronología, los secretos, las relaciones, las revelaciones y el conocimiento de personajes o jugadores.

Las respuestas de continuidad deberán priorizar datos canónicos y citar internamente sus fuentes dentro de la aplicación. Cuando la información sea incierta, contradictoria o inexistente, la IA deberá declararlo.

### 7.9 IA de preparación de sesión

El modo de preparación de sesión deberá convertir información del mundo y de la campaña en material utilizable durante una partida.

Deberá poder generar y organizar:

1. Objetivos de sesión.
2. Escenas previstas.
3. Escenas opcionales.
4. PNJ relevantes.
5. Localizaciones activas.
6. Pistas disponibles.
7. Secretos pendientes.
8. Conflictos activos.
9. Consecuencias esperadas.
10. Eventos de facción.
11. Encuentros.
12. Rumores.
13. Complicaciones.
14. Recompensas.
15. Amenazas.
16. Decisiones significativas.
17. Preguntas abiertas.
18. Recordatorio de continuidad.
19. Resumen para el director.
20. Resumen seguro para jugadores.

### 7.10 IA de improvisación en vivo

El modo de improvisación en vivo deberá priorizar rapidez, brevedad, coherencia y control de spoilers.

Deberá poder generar contenido inmediato sin romper el canon activo. Deberá distinguir entre contenido desechable, contenido provisional y contenido que debe incorporarse al canon después de la sesión.

Deberá permitir crear rápidamente PNJ, nombres, descripciones, respuestas de facciones, consecuencias, pistas alternativas, complicaciones, localizaciones menores, rumores, obstáculos, recompensas, diálogos breves y reacciones del mundo.

### 7.11 IA post-sesión

El modo post-sesión deberá convertir notas de juego en actualización estructurada del corpus.

Deberá poder:

1. Resumir lo ocurrido.
2. Identificar entidades modificadas.
3. Crear nuevas entidades detectadas.
4. Crear nuevas relaciones.
5. Actualizar estados de vida, ubicación, lealtad, conocimiento o actitud.
6. Marcar secretos revelados.
7. Marcar pistas entregadas.
8. Detectar consecuencias pendientes.
9. Detectar contradicciones con preparación previa.
10. Proponer retcon, adaptación o aceptación de cambios.
11. Generar resumen para jugadores.
12. Generar resumen privado para el director.
13. Preparar semillas para la siguiente sesión.
14. Actualizar relojes, frentes o amenazas.
15. Registrar decisiones relevantes de jugadores.

---

## 8. Motor de consistencia narrativa

### 8.1 Función general

El motor de consistencia deberá analizar el corpus narrativo para detectar contradicciones, ambigüedades problemáticas, lagunas, duplicados, dependencias rotas y desviaciones respecto a reglas internas.

El motor deberá operar sobre entidades, relaciones, afirmaciones, cronología, visibilidad, fuentes, sesiones, marcos narrativos y capas de mundo.

La detección de inconsistencias no deberá modificar automáticamente el corpus. Deberá generar incidencias, advertencias, informes o propuestas de corrección.

### 8.2 Tipos de consistencia

El motor deberá contemplar, como mínimo:

1. Consistencia cronológica.
2. Consistencia geográfica.
3. Consistencia causal.
4. Consistencia motivacional.
5. Consistencia de conocimiento.
6. Consistencia de canon.
7. Consistencia de visibilidad.
8. Consistencia tonal.
9. Consistencia de género.
10. Consistencia de escala.
11. Consistencia de sistema mágico o tecnológico.
12. Consistencia histórica.
13. Consistencia de facciones.
14. Consistencia de sesiones.
15. Consistencia de pistas y secretos.
16. Consistencia de estructura narrativa.
17. Consistencia de reglas internas.
18. Consistencia de nomenclatura.
19. Consistencia de duplicados.
20. Consistencia de dependencias.

### 8.3 Incidencias de consistencia

Toda inconsistencia detectada deberá registrarse como incidencia estructurada.

Cada incidencia deberá incluir:

1. Identificador.
2. Tipo de incidencia.
3. Severidad.
4. Entidades afectadas.
5. Relaciones afectadas.
6. Afirmaciones afectadas.
7. Descripción del problema.
8. Evidencia interna.
9. Posibles soluciones.
10. Estado.
11. Fecha de detección.
12. Fecha de resolución.
13. Resolución aplicada.
14. Motivo de descarte si se descarta.
15. Si es una desviación deliberada.

Los estados mínimos de incidencia deberán ser:

1. Abierta.
2. Revisada.
3. Aceptada como problema.
4. Descartada.
5. Resuelta.
6. Marcada como intencional.
7. Pendiente de información.
8. Pospuesta.

### 8.4 Contradicciones permitidas

El sistema deberá permitir contradicciones deliberadas. No toda contradicción narrativa es un error. La aplicación deberá poder distinguir entre:

1. Error de continuidad.
2. Mentira de personaje.
3. Rumor falso.
4. Propaganda.
5. Mito contradictorio.
6. Interpretación cultural.
7. Información parcial.
8. Paradoja intencionada.
9. Misterio sin resolver.
10. Retcon pendiente.
11. Diferencia entre edición antigua y nueva.

El usuario deberá poder marcar contradicciones como intencionadas para evitar falsas alertas recurrentes.

---

## 9. Grafo semántico interactivo

### 9.1 Función del grafo

El grafo será una interfaz visual para explorar, editar y analizar entidades y relaciones. No será la única forma de interacción ni la fuente primaria del conocimiento.

El grafo deberá permitir visualizar nodos, relaciones, clusters, capas, jerarquías, trayectorias causales, cronologías parciales, redes de conocimiento, redes de conflicto, redes de facciones, redes de secretos y dependencias estructurales.

### 9.2 Capacidades del grafo

El grafo deberá permitir:

1. Crear entidades.
2. Crear relaciones.
3. Editar entidades.
4. Editar relaciones.
5. Filtrar por tipo.
6. Filtrar por estado de canon.
7. Filtrar por visibilidad.
8. Filtrar por capa.
9. Filtrar por dominio.
10. Filtrar por importancia.
11. Filtrar por sesión.
12. Filtrar por marco narrativo.
13. Filtrar por severidad de inconsistencia.
14. Mostrar rutas causales.
15. Mostrar dependencias.
16. Mostrar conocimiento por personaje o facción.
17. Mostrar secretos y revelaciones.
18. Mostrar conexiones directas e indirectas.
19. Expandir nodos.
20. Contraer nodos.
21. Agrupar nodos.
22. Crear vistas guardadas.
23. Comparar dos estados del grafo.
24. Mostrar sugerencias de IA como nodos candidatos.
25. Aceptar, editar o rechazar nodos candidatos.
26. Aceptar, editar o rechazar relaciones candidatas.
27. Anotar nodos.
28. Anotar relaciones.
29. Navegar desde grafo a ficha.
30. Navegar desde ficha a grafo.

### 9.3 Vistas de grafo

La aplicación deberá soportar múltiples vistas de grafo. Una vista de grafo será una configuración visual y semántica sobre el mismo corpus.

Deberán existir, como mínimo:

1. Grafo global.
2. Grafo de personaje.
3. Grafo de localización.
4. Grafo de facción.
5. Grafo de conflicto.
6. Grafo de secretos.
7. Grafo de pistas.
8. Grafo de cronología.
9. Grafo causal.
10. Grafo de campaña.
11. Grafo de sesión.
12. Grafo de conocimiento.
13. Grafo de estructura narrativa.
14. Grafo de inconsistencias.
15. Grafo de mundo por capas.

Las vistas deberán ser configurables y persistibles.

### 9.4 Control de complejidad visual

El grafo deberá evitar la sobrecarga visual. Deberá ofrecer mecanismos de reducción de complejidad:

1. Filtros.
2. Agrupaciones.
3. Clustering.
4. Profundidad máxima.
5. Vista por vecindad.
6. Foco en entidad.
7. Ocultación de relaciones débiles.
8. Ocultación de entidades archivadas.
9. Vista por capa.
10. Vista por tipo de relación.
11. Vista por relevancia narrativa.
12. Vista por sesión.
13. Vista por estado de revelación.

---

## 10. Base de datos narrativa y vistas de galería

### 10.1 Función general

La aplicación deberá incluir una interfaz de base de datos narrativa ordenada, navegable y filtrable. Esta capa deberá permitir trabajar con el corpus de forma tabular, documental, visual y estructurada.

La base de datos narrativa deberá complementar al grafo. Deberá ser la herramienta principal para revisar, clasificar, editar y mantener grandes cantidades de contenido.

### 10.2 Vistas requeridas

La aplicación deberá ofrecer, como mínimo, las siguientes vistas:

1. Galería de personajes.
2. Galería de localizaciones.
3. Galería de facciones.
4. Galería de culturas.
5. Galería de objetos.
6. Galería de eventos.
7. Galería de escenas.
8. Galería de sesiones.
9. Galería de secretos.
10. Galería de pistas.
11. Galería de conflictos.
12. Galería de reglas del mundo.
13. Galería de tecnologías.
14. Galería de sistemas mágicos.
15. Galería de idiomas.
16. Galería de instituciones.
17. Galería de religiones.
18. Galería de criaturas.
19. Cronología.
20. Lista de tramas.
21. Lista de subtramas.
22. Lista de arcos de personaje.
23. Lista de inconsistencias.
24. Lista de elementos pendientes.
25. Lista de sugerencias IA.
26. Lista de elementos importados pendientes.
27. Lista de elementos no desarrollados.
28. Lista de elementos huérfanos.
29. Lista de elementos infrautilizados.
30. Lista de elementos revelados.

### 10.3 Fichas de entidad

Cada entidad deberá tener una ficha propia.

La ficha deberá incluir, como mínimo:

1. Nombre.
2. Tipo.
3. Resumen.
4. Descripción extendida.
5. Estado de canon.
6. Estado de visibilidad.
7. Nivel de certeza.
8. Etiquetas.
9. Capas.
10. Dominio narrativo.
11. Relaciones principales.
12. Relaciones entrantes.
13. Relaciones salientes.
14. Cronología asociada.
15. Apariciones.
16. Sesiones asociadas.
17. Escenas asociadas.
18. Secretos asociados.
19. Pistas asociadas.
20. Conflictos asociados.
21. Notas privadas.
22. Notas exportables.
23. Fuentes.
24. Historial.
25. Sugerencias de IA.
26. Inconsistencias relacionadas.
27. Acciones disponibles.
28. Campos personalizados.

La ficha deberá permitir saltar a vista de grafo, cronología, sesiones, fuentes e incidencias relacionadas.

### 10.4 Búsqueda y filtrado

La aplicación deberá incluir búsqueda semántica, búsqueda textual, búsqueda por metadatos y búsqueda estructurada.

Deberá permitir buscar por:

1. Nombre.
2. Alias.
3. Tipo.
4. Etiqueta.
5. Texto.
6. Relación.
7. Estado de canon.
8. Visibilidad.
9. Capa.
10. Fuente.
11. Sesión.
12. Escena.
13. Fecha interna.
14. Fecha de creación.
15. Fecha de modificación.
16. Importancia.
17. Certeza.
18. Inconsistencia.
19. Marco narrativo.
20. Dominio narrativo.

La búsqueda deberá poder combinar criterios.

---

## 11. Importación documental

### 11.1 Función general

La aplicación deberá permitir importar documentos externos para convertirlos, total o parcialmente, en conocimiento estructurado.

La importación documental deberá admitir, como mínimo, PDF y texto plano. La arquitectura deberá permitir ampliar formatos en el futuro.

La importación no deberá incorporar directamente contenido al canon sin revisión del usuario.

### 11.2 Pipeline de importación

El proceso de importación deberá incluir, como mínimo:

1. Carga del documento.
2. Extracción de texto.
3. Segmentación del contenido.
4. Identificación de secciones.
5. Identificación de entidades candidatas.
6. Identificación de relaciones candidatas.
7. Identificación de eventos candidatos.
8. Identificación de fechas o cronología.
9. Identificación de reglas, tablas, descripciones o bloques especiales.
10. Clasificación por tipo.
11. Detección de duplicados contra el corpus existente.
12. Detección de contradicciones con el canon activo.
13. Presentación de candidatos al usuario.
14. Aceptación, edición, fusión o descarte.
15. Incorporación controlada al corpus.
16. Conservación del documento como fuente.
17. Trazabilidad entre elemento importado y fragmento de origen.

### 11.3 Bandeja de candidatos

Los resultados de importación deberán entrar en una bandeja de revisión.

Cada candidato deberá mostrar:

1. Tipo propuesto.
2. Nombre propuesto.
3. Descripción extraída.
4. Fuente.
5. Fragmento de origen.
6. Relaciones propuestas.
7. Confianza de extracción.
8. Posibles duplicados.
9. Posibles contradicciones.
10. Estado de revisión.
11. Acciones disponibles.

Las acciones mínimas serán:

1. Aceptar.
2. Editar y aceptar.
3. Fusionar con entidad existente.
4. Convertir a otro tipo.
5. Marcar como fuente de referencia.
6. Descartar.
7. Posponer.
8. Solicitar reanálisis.
9. Añadir como hipótesis.
10. Añadir como borrador.

### 11.4 Importación parcial

El usuario deberá poder importar selectivamente:

1. Solo personajes.
2. Solo localizaciones.
3. Solo facciones.
4. Solo eventos.
5. Solo cronología.
6. Solo relaciones.
7. Solo reglas.
8. Solo secretos.
9. Solo pistas.
10. Solo texto como fuente consultable.
11. Solo elementos de una sección.
12. Solo elementos con confianza superior a un umbral.

### 11.5 Fuente documental

Todo documento importado deberá poder conservarse como fuente. Las entidades, relaciones y afirmaciones derivadas del documento deberán poder referenciar el origen.

El sistema deberá permitir navegar desde una entidad hasta sus fuentes y desde una fuente hasta las entidades derivadas de ella.

---

## 12. Capa de escritura

### 12.1 Función general

La capa de escritura deberá permitir desarrollar historias, relatos, novelas, guiones, escenas, capítulos y arcos narrativos sobre la base de conocimiento.

No será obligatorio que la aplicación sea un procesador de textos completo, pero sí deberá permitir conectar contenido escrito con el modelo narrativo estructurado.

### 12.2 Elementos de escritura

La aplicación deberá soportar:

1. Historia.
2. Arco narrativo.
3. Trama.
4. Subtrama.
5. Capítulo.
6. Escena.
7. Secuencia.
8. Punto de giro.
9. Revelación.
10. Conflicto.
11. Tema.
12. Motivo.
13. Símbolo.
14. Voz narrativa.
15. Punto de vista.
16. Personaje focal.
17. Estado de revisión.
18. Nota de autor.

### 12.3 Relación entre escritura y corpus

Las escenas, capítulos y arcos deberán poder vincularse a entidades del corpus.

El sistema deberá permitir conocer qué personajes, localizaciones, secretos, objetos, conflictos, facciones y eventos aparecen o se mencionan en cada unidad de escritura.

La IA deberá poder analizar continuidad entre escenas, progresión de personajes, distribución de información, aparición de elementos y consistencia con el mundo.

### 12.4 Control estructural

La capa de escritura deberá poder integrarse con marcos narrativos. El usuario deberá poder evaluar una historia o parte de una historia frente a un marco seleccionado.

El sistema deberá permitir detectar:

1. Falta de conflicto.
2. Falta de progresión.
3. Escenas redundantes.
4. Escenas sin función.
5. Personajes sin arco.
6. Revelaciones no preparadas.
7. Giros sin consecuencia.
8. Temas no desarrollados.
9. Tramas abandonadas.
10. Exceso de exposición.
11. Incoherencias de punto de vista.
12. Rupturas de tono.

---

## 13. Capa de rol

### 13.1 Función general

La capa de rol deberá permitir preparar, dirigir, registrar y actualizar campañas de rol utilizando el mismo corpus narrativo estructurado.

La capa de rol no deberá intentar sustituir necesariamente a un tablero virtual. Su función principal será gestionar la arquitectura narrativa, el estado de campaña, la continuidad, las sesiones, los secretos, las pistas, las facciones, los PNJ, las localizaciones y las consecuencias de las decisiones de los jugadores.

### 13.2 Campaña

Una campaña deberá ser una entidad de alto nivel vinculada a un mundo, escenario o corpus.

La campaña deberá contener, como mínimo:

1. Nombre.
2. Descripción.
3. Sistema de juego.
4. Tono.
5. Género.
6. Estado.
7. Jugadores.
8. Personajes jugadores.
9. Sesiones.
10. Tramas activas.
11. Facciones activas.
12. Localizaciones activas.
13. Secretos.
14. Pistas.
15. Relojes o amenazas.
16. Notas privadas.
17. Resúmenes públicos.
18. Historial de cambios.
19. Configuración de visibilidad.
20. Reglas de mesa o acuerdos narrativos.

El sistema de juego deberá ser un metadato flexible. La aplicación deberá poder funcionar de forma agnóstica al sistema.

### 13.3 Personajes jugadores

Los personajes jugadores deberán poder modelarse como entidades narrativas con campos adicionales específicos de campaña.

Deberán poder vincularse a:

1. Jugador.
2. Trasfondo.
3. Objetivos.
4. Secretos.
5. Relaciones.
6. Facciones.
7. Localizaciones.
8. Eventos pasados.
9. Sesiones.
10. Información conocida.
11. Información ignorada.
12. Deudas.
13. Promesas.
14. Conflictos personales.
15. Arcos pendientes.
16. Recompensas.
17. Consecuencias.
18. Estado actual.

### 13.4 Preparación de sesión

La aplicación deberá incluir un espacio de preparación de sesión.

Cada sesión deberá poder contener:

1. Número o identificador.
2. Fecha real.
3. Fecha interna del mundo.
4. Resumen de contexto.
5. Objetivos del director.
6. Objetivos de jugadores conocidos.
7. Escenas previstas.
8. Escenas opcionales.
9. Localizaciones previstas.
10. PNJ previstos.
11. Facciones relevantes.
12. Conflictos activos.
13. Pistas disponibles.
14. Secretos revelables.
15. Rumores.
16. Encuentros.
17. Recompensas.
18. Complicaciones.
19. Consecuencias esperadas.
20. Preguntas abiertas.
21. Material improvisable.
22. Notas privadas.
23. Resumen seguro para jugadores.
24. Checklist de continuidad.
25. Sugerencias de IA.

La sesión deberá poder estar vinculada al corpus completo. Los elementos usados en sesión deberán quedar registrados.

### 13.5 Dirección en vivo

La aplicación deberá incluir un modo de dirección en vivo optimizado para consulta rápida y modificación ligera durante la partida.

Este modo deberá permitir:

1. Consultar PNJ.
2. Consultar localizaciones.
3. Consultar secretos.
4. Consultar pistas.
5. Consultar facciones.
6. Crear notas rápidas.
7. Crear entidades provisionales.
8. Crear relaciones provisionales.
9. Marcar pistas como entregadas.
10. Marcar secretos como revelados.
11. Registrar decisiones de jugadores.
12. Registrar eventos ocurridos.
13. Solicitar improvisación IA.
14. Generar nombres.
15. Generar descripciones breves.
16. Generar consecuencias.
17. Generar complicaciones.
18. Consultar continuidad.
19. Evitar spoilers visibles.
20. Preparar resumen post-sesión.

El modo en vivo deberá minimizar fricción. Las operaciones deberán ser rápidas y no deberán exigir completar fichas complejas durante la sesión.

### 13.6 Secretos y pistas

La aplicación deberá tratar secretos y pistas como entidades estructuradas.

Un secreto deberá poder tener:

1. Contenido verdadero.
2. Entidades afectadas.
3. Estado de revelación.
4. Quién lo sabe.
5. Quién lo sospecha.
6. Quién lo ignora.
7. Quién lo oculta.
8. Pistas asociadas.
9. Consecuencias de revelación.
10. Consecuencias de ocultación.
11. Sesiones donde puede revelarse.
12. Sesión donde fue revelado.
13. Forma de revelación.
14. Nivel de importancia.
15. Estado de canon.

Una pista deberá poder tener:

1. Contenido.
2. Secreto asociado.
3. Fuente.
4. Localización.
5. PNJ asociado.
6. Forma de entrega.
7. Estado de entrega.
8. Claridad.
9. Redundancia.
10. Riesgo de pérdida.
11. Sesión prevista.
12. Sesión entregada.
13. Personajes que la conocen.
14. Interpretación probable.
15. Interpretaciones erróneas posibles.

El sistema deberá poder detectar secretos sin pistas, pistas sin secreto, pistas entregadas sin seguimiento y secretos revelados sin consecuencia.

### 13.7 Facciones y frentes

La aplicación deberá permitir modelar facciones y amenazas dinámicas.

Cada facción deberá poder tener:

1. Objetivos.
2. Recursos.
3. Líderes.
4. Miembros.
5. Aliados.
6. Enemigos.
7. Territorios.
8. Planes.
9. Secretos.
10. Métodos.
11. Ideología.
12. Estado actual.
13. Relojes o progreso.
14. Reacciones posibles.
15. Relación con personajes jugadores.
16. Relación con otras facciones.
17. Eventos asociados.
18. Consecuencias de inacción.
19. Consecuencias de intervención.
20. Visibilidad para jugadores.

Los frentes, amenazas o relojes deberán representar procesos que avanzan con o sin intervención de los jugadores.

### 13.8 Post-sesión

La aplicación deberá incluir un flujo de actualización post-sesión.

El usuario deberá poder introducir notas libres, seleccionar eventos ocurridos, aceptar sugerencias de IA y actualizar el corpus.

El sistema deberá convertir lo ocurrido en:

1. Resumen privado.
2. Resumen público.
3. Cambios de entidades.
4. Cambios de relaciones.
5. Cambios de estado.
6. Secretos revelados.
7. Pistas entregadas.
8. Facciones afectadas.
9. Consecuencias pendientes.
10. Nuevas preguntas abiertas.
11. Nuevas oportunidades narrativas.
12. Inconsistencias generadas.
13. Preparación inicial para próxima sesión.

---

## 14. Sistema de fuentes, versiones e historial

### 14.1 Fuentes

Toda entidad, relación o afirmación deberá poder estar vinculada a una o varias fuentes.

Las fuentes podrán ser:

1. Entrada manual.
2. Documento importado.
3. Fragmento de documento.
4. Generación IA.
5. Sugerencia IA aceptada.
6. Sesión de rol.
7. Nota post-sesión.
8. Versión anterior.
9. Importación externa.
10. Decisión del usuario.
11. Marco narrativo.
12. Plantilla.

### 14.2 Versionado

La aplicación deberá conservar versiones de elementos relevantes.

El usuario deberá poder:

1. Ver historial.
2. Comparar versiones.
3. Recuperar versiones anteriores.
4. Marcar una versión como canónica.
5. Ver qué relaciones cambiaron.
6. Ver qué inconsistencias aparecieron tras un cambio.
7. Ver qué sesiones o documentos originaron un cambio.
8. Ver qué sugerencias IA fueron aceptadas o rechazadas.

### 14.3 Auditoría interna

El sistema deberá poder reconstruir el origen de una decisión narrativa.

Para cualquier hecho importante, el usuario deberá poder saber:

1. De dónde salió.
2. Cuándo se introdujo.
3. Quién o qué lo introdujo.
4. Cuándo se modificó.
5. Qué entidades dependen de él.
6. Qué contradicciones genera.
7. En qué sesiones o escenas apareció.
8. Si fue revelado o no.

---

## 15. Exportación y salida de información

### 15.1 Función general

La aplicación deberá permitir exportar contenido de forma controlada.

La exportación deberá respetar estados de visibilidad, canon, secretos, filtros y destinatarios.

### 15.2 Tipos de exportación

La aplicación deberá permitir exportar:

1. Biblia de mundo.
2. Resumen de historia.
3. Resumen de campaña.
4. Resumen de sesión.
5. Resumen público para jugadores.
6. Resumen privado para director.
7. Fichas de personajes.
8. Fichas de localización.
9. Fichas de facción.
10. Cronología.
11. Lista de secretos.
12. Lista de pistas.
13. Lista de tramas.
14. Informe de inconsistencias.
15. Grafo o vista de grafo.
16. Documento de preparación de sesión.
17. Handouts.
18. Wiki estática.
19. Documento de referencia.
20. Dataset estructurado.

### 15.3 Control de visibilidad en exportación

Antes de exportar, la aplicación deberá permitir seleccionar perfil de exportación.

Los perfiles mínimos deberán ser:

1. Autor completo.
2. Director completo.
3. Jugadores sin spoilers.
4. Personaje concreto.
5. Facción concreta.
6. Documento público del mundo.
7. Documento de trabajo.
8. Documento de revisión.
9. Documento de inconsistencias.
10. Documento de pitch.

La exportación no deberá revelar secretos, notas privadas o contenido no exportable salvo autorización explícita del usuario.

---

## 16. Proyectos, espacios y organización

### 16.1 Proyecto

Un proyecto será el contenedor principal de datos.

Cada proyecto deberá poder contener:

1. Uno o varios mundos.
2. Una o varias historias.
3. Una o varias campañas.
4. Documentos fuente.
5. Marcos narrativos.
6. Configuración de IA.
7. Configuración de tono.
8. Configuración de realismo.
9. Entidades.
10. Relaciones.
11. Afirmaciones.
12. Sesiones.
13. Exportaciones.
14. Historial.
15. Plantillas.
16. Campos personalizados.

### 16.2 Espacios principales de trabajo

La interfaz deberá organizarse en, al menos, tres espacios conceptuales:

1. Crear.
2. Organizar.
3. Escribir o dirigir.

El espacio Crear deberá priorizar creación, expansión, grafo, edición de relaciones, generación IA y exploración de consecuencias.

El espacio Organizar deberá priorizar base de datos, galerías, fichas, búsqueda, filtros, cronología, incidencias, duplicados y mantenimiento del corpus.

El espacio Escribir o Dirigir deberá adaptarse al tipo de proyecto activo. En modo escritura deberá priorizar escenas, capítulos, estructura, continuidad y texto. En modo rol deberá priorizar sesiones, pistas, secretos, PNJ, facciones, improvisación, resumen y actualización de campaña.

### 16.3 Configuración por proyecto

Cada proyecto deberá poder configurar:

1. Idioma principal.
2. Idiomas secundarios.
3. Tono.
4. Género.
5. Grado de realismo.
6. Marcos narrativos activos.
7. Sistema de rol.
8. Tipos de entidad activos.
9. Tipos de relación activos.
10. Campos personalizados.
11. Reglas de IA.
12. Reglas de exportación.
13. Reglas de visibilidad.
14. Convenciones de nombres.
15. Calendario interno.
16. Unidades de medida.
17. Nivel de tolerancia a inconsistencias.
18. Preferencias de sugerencias IA.

---

## 17. Personalización y extensibilidad

### 17.1 Tipos personalizados

El usuario deberá poder definir tipos de entidad personalizados.

Cada tipo personalizado deberá poder tener:

1. Nombre.
2. Descripción.
3. Icono o representación visual.
4. Color o estilo visual.
5. Campos propios.
6. Relaciones permitidas o sugeridas.
7. Plantilla de ficha.
8. Participación en IA.
9. Participación en consistencia.
10. Participación en exportación.
11. Vistas asociadas.

### 17.2 Campos personalizados

El usuario deberá poder añadir campos personalizados a tipos existentes o personalizados.

Los campos deberán poder ser, como mínimo:

1. Texto corto.
2. Texto largo.
3. Número.
4. Fecha.
5. Fecha interna del mundo.
6. Selección.
7. Selección múltiple.
8. Relación con entidad.
9. Booleano.
10. Estado.
11. Nivel o escala.
12. Referencia documental.
13. Lista.
14. Tabla simple.
15. Etiqueta.

### 17.3 Plantillas

La aplicación deberá permitir crear y aplicar plantillas para:

1. Entidades.
2. Relaciones.
3. Fichas.
4. Sesiones.
5. Campañas.
6. Historias.
7. Marcos narrativos.
8. Exportaciones.
9. Análisis IA.
10. Importaciones.

Las plantillas no deberán imponer estructura obligatoria salvo que el usuario lo configure.

---

## 18. Seguridad narrativa y control de spoilers

### 18.1 Protección de secretos

La aplicación deberá evitar revelaciones accidentales en modo jugador, exportaciones, resúmenes públicos, vistas compartibles y consultas IA orientadas a salida pública.

Toda operación que pueda revelar contenido marcado como secreto, privado o no exportable deberá respetar el perfil de visibilidad activo.

### 18.2 Contexto seguro para IA

Cuando la IA genere contenido para jugadores o salida pública, el contexto enviado o utilizado deberá excluir información no autorizada por el perfil activo.

La aplicación deberá poder generar contenido seguro para jugadores sin contaminarlo con conocimiento privado del director.

### 18.3 Separación de notas privadas y públicas

Toda entidad deberá poder contener notas privadas y notas exportables. Las notas privadas no deberán aparecer en exportaciones públicas ni en modos seguros.

---

## 19. Requisitos de calidad funcional

### 19.1 Coherencia

La aplicación deberá favorecer coherencia interna sin imponer realismo innecesario. El sistema deberá permitir mundos fantásticos, míticos, surrealistas, contradictorios o simbólicos siempre que esas propiedades sean intencionales.

### 19.2 Control del usuario

El usuario deberá tener control final sobre canon, cambios, importaciones, sugerencias, exportaciones y configuración de IA.

### 19.3 Transparencia

La aplicación deberá mostrar por qué una sugerencia, inconsistencia, relación o clasificación ha sido propuesta cuando dicha explicación sea necesaria para la revisión del usuario.

### 19.4 No destructividad

La aplicación deberá evitar operaciones destructivas irreversibles. Las eliminaciones, fusiones y cambios masivos deberán ser trazables y, cuando sea razonable, reversibles.

### 19.5 Escalabilidad conceptual

La aplicación deberá poder manejar proyectos pequeños, medianos y grandes sin que el modelo conceptual se rompa. Deberá contemplar cientos o miles de entidades y relaciones, aunque la interfaz deberá ofrecer mecanismos de filtrado, agrupación y foco para mantener la usabilidad.

---

## 20. Límites del producto

La aplicación no deberá definirse principalmente como:

1. Un tablero virtual de rol.
2. Un procesador de textos tradicional.
3. Una wiki pasiva.
4. Un generador automático de novelas.
5. Un chatbot genérico.
6. Un gestor de archivos.
7. Una herramienta de diagramas sin semántica.
8. Una base de datos tabular sin narrativa.
9. Una enciclopedia estática.
10. Un sustituto completo de sistemas de reglas de rol.

La aplicación podrá integrarse o exportar hacia herramientas externas, pero su función principal será mantener y explotar la arquitectura narrativa del proyecto.

---

## 21. Resultado objetivo

El resultado final de la aplicación deberá ser un entorno donde el usuario pueda:

1. Crear un mundo desde ideas abstractas o elementos concretos.
2. Definir entidades narrativas con estructura.
3. Relacionar entidades con semántica fuerte.
4. Visualizar el corpus como grafo, galería, ficha, cronología y lista.
5. Utilizar IA para sugerir, expandir, criticar, resumir, extraer y transformar contenido.
6. Controlar qué es canon, hipótesis, borrador, secreto, rumor o contradicción.
7. Importar documentos y convertirlos en conocimiento revisable.
8. Detectar inconsistencias narrativas, causales, cronológicas y de visibilidad.
9. Aplicar marcos narrativos como herramientas de análisis y generación.
10. Preparar historias, escenas, arcos y campañas.
11. Preparar sesiones de rol.
12. Dirigir sesiones con soporte de consulta e improvisación.
13. Registrar lo ocurrido en sesión.
14. Actualizar el mundo tras las acciones de los jugadores.
15. Gestionar secretos, pistas, facciones, amenazas y consecuencias.
16. Exportar información adaptada a destinatarios concretos.
17. Mantener trazabilidad entre contenido, fuente, versión y decisión.
18. Evitar que la IA sustituya el criterio creativo del usuario.
19. Convertir lore en material narrativo o jugable.
20. Mantener continuidad en proyectos narrativos complejos.

---

## 22. Declaración final de contrato

La aplicación deberá concebirse como un sistema de conocimiento narrativo asistido por IA, centrado en entidades, relaciones, canon, continuidad, causalidad, estructura y uso práctico del contenido.

Toda funcionalidad visual, generativa, documental, analítica o de rol deberá subordinarse a este principio: el usuario construye y controla una red narrativa estructurada que la aplicación ayuda a expandir, verificar, explorar y utilizar.

La arquitectura deberá preservar la separación entre creación, organización, análisis, escritura y dirección de partidas, pero todas estas áreas deberán operar sobre una misma base de conocimiento coherente y trazable.

La IA deberá ser un colaborador contextual, crítico y generativo, nunca una autoridad automática sobre el canon.

El grafo deberá ser una interfaz semántica, no un diagrama decorativo.

La base de datos deberá ser narrativa, no meramente administrativa.

La capa de rol deberá convertir el corpus en juego vivo, no solo almacenarlo.

La importación documental deberá producir candidatos revisables, no contaminación automática del proyecto.

El motor de consistencia deberá detectar problemas sin invalidar decisiones creativas deliberadas.

El producto final deberá permitir crear mundos, historias y campañas complejas con control, coherencia, flexibilidad y capacidad de uso real antes, durante y después de la escritura o la partida.
