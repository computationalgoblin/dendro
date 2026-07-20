# Contrato BETA2-MEM - Memoria narrativa viva

> **DEPRECADO (2026-07-11).** Este contrato modelo la Memoria como un *resumen editorial fijo*
> inyectado en cada prompt. El modelo autoritativo vigente es el **metodo Karpathy** (wiki+indice
> que la IA navega): ver **[wiki_memoria.md](wiki_memoria.md)** (epica BETA2-WIKI). Lo que sigue
> se conserva por su valor de dominio: `NarrativeMemory`, @menciones estructuradas, motor de
> impacto (Falta regar) y potencia causal/anillos **siguen vigentes y se reutilizan**. Lo que
> cambia es la parte IA (navegacion indice-first en vez de volcado fijo) y el recorte de la
> superficie de IA. No usar este documento para decidir la parte IA/RAG/prompt.

Estado: DEPRECADO por BETA2-WIKI (ver wiki_memoria.md)
Fecha: 2026-07-10
Ticket origen: BETA2-MEM-01
Perfil responsable: arquitectura-producto

Este contrato define la capacidad de Memoria narrativa viva de Dendro y su relacion con RAG, Regar, Cultivar, @menciones, anillos y propuestas estructurales.

La Memoria no es una funcion aislada. Es una capa derivada, editorial y transversal que ayuda a la IA a entender el estado actual del proyecto sin desplazar al canon ni reducir el control del usuario.

## 1. Principio rector

Dendro debe ayudar al usuario a mantener un mundo narrativo vivo.

Para hacerlo, la app necesita una Memoria que resuma el estado actual del proyecto, detecte tensiones, recuerde huecos, conecte causalidades y sirva como contexto de alta calidad para cualquier tarea IA.

La Memoria debe estar mantenida por la misma metafora que ya existe en el producto:

```text
Cambios narrativos -> Falta regar -> Regar -> Memoria actualizada + Cultivo revisable
```

La Memoria debe sentirse como una capacidad silenciosa del proyecto. El usuario no debe tener que recordar un boton nuevo para "actualizar la memoria" durante el flujo normal. Cuando el usuario autoriza Regar, esa autorizacion cubre tambien la actualizacion ordinaria de Memoria.

## 2. Jerarquia de autoridad

La jerarquia de verdad del sistema queda fijada asi:

```text
Canon confirmado
  > Referencias estructuradas (@menciones, relaciones, hitos, anillos)
  > Memoria derivada
  > Propuestas, contradicciones, huecos y cultivo pendiente
```

Reglas:

1. El canon manda siempre.
2. La Memoria interpreta y resume el canon, pero no crea canon.
3. Una referencia estructurada tiene mas autoridad que una frase suelta de Memoria.
4. Una propuesta IA no es canon hasta que el usuario la acepta.
5. Una contradiccion detectada no invalida automaticamente contenido canonico.
6. Una edicion manual de Memoria no se convierte en canon por si misma.
7. La IA nunca modifica canon directamente.

## 3. Que es Memoria

La Memoria es un estado derivado, persistente y consultable que representa la lectura editorial actual del proyecto.

Debe poder existir en varios niveles:

- Memoria global de proyecto.
- Memoria de entidad.
- Memoria de relacion.
- Memoria de hito.
- Memoria de anillo o rama.
- Memoria contextual cuando una entidad cambia de rol segun epoca, escenario, conflicto o linea narrativa.

La Memoria debe representar el estado actual mas reciente. No es una vista de versionado narrativo ni una cronologia de todas las memorias anteriores.

El sistema puede conservar trazabilidad tecnica de cambios para auditoria, pero el producto visible no debe convertir Memoria en un historial paralelo salvo nuevo contrato.

## 4. Que NO es Memoria

La Memoria no es:

- Canon.
- Una entidad narrativa nueva.
- Una base de datos paralela de lore.
- Una wiki separada.
- Memoria de sesion conversacional.
- Un sustituto de relaciones, hitos o anillos.
- Un sistema de importacion documental.
- Un lugar donde la IA pueda aplicar cambios canonicos sin aceptacion.

La app no debe reintroducir importacion documental para alimentar esta capacidad. La Memoria se deriva de datos existentes del proyecto y de acciones autorizadas por el usuario.

## 5. Contenido minimo de Memoria

Cada bloque de Memoria debe poder contener, segun aplique:

- Resumen editorial.
- Estado actual.
- Preguntas abiertas.
- Contradicciones detectadas.
- Huecos o zonas sin desarrollar.
- Causalidad relevante.
- Supuestos de la IA.
- Consecuencias probables.
- Dependencias narrativas.
- Fuentes/citas hacia elementos canonicos o referencias estructuradas.
- Estado de frescura.
- Origen y autoria: usuario, IA, riego, regeneracion manual.

La Memoria debe ser util para IA y legible para el usuario. No debe convertirse en un dump tecnico.

## 6. Estados de frescura

La Memoria y los elementos relacionados deben soportar estados de frescura compatibles con la metafora actual:

- Sin Memoria: el elemento/proyecto aun no tiene memoria derivada.
- Regada: la Memoria se considera vigente respecto al estado conocido.
- Falta regar: hay cambios que pueden haberla dejado obsoleta o incompleta.
- Secada: la Memoria existe, pero se considera desfasada o de baja fiabilidad.

Estos estados no cambian el canon. Solo indican mantenimiento narrativo pendiente.

## 7. Regar como pipeline principal

La actualizacion ordinaria de Memoria forma parte de Regar.

Pipeline conceptual:

```text
1. El usuario modifica o guarda contenido canonico.
2. El motor de impacto detecta dependencias potencialmente afectadas.
3. Los elementos afectados se marcan como Falta regar.
4. El usuario autoriza Regar.
5. La IA analiza canon, referencias, memoria previa y contexto causal.
6. La IA produce Memoria actualizada, contradicciones, huecos y propuestas.
7. El sistema guarda Memoria derivada o presenta diff/propuesta segun el caso.
8. Cultivo muestra lo revisable.
9. El canon solo cambia si el usuario acepta un cambio canonico o estructural.
```

Reglas:

- Cancelar Regar no aplica cambios IA.
- Fallar IA no debe romper la app.
- La app debe seguir funcionando sin IA.
- La actualizacion de Memoria no debe aparecer como un boton principal mas en Creacion.
- Cultivar sigue significando revisar/reincorporar, no aceptar escritura automatica.

## 8. Regenerar Memoria desde Configuracion

Ademas del mantenimiento ordinario en Regar, la app debe ofrecer funciones de proyecto desde Configuracion:

- Consultar Memoria.
- Editar Memoria.
- Borrar Memoria.
- Regenerar Memoria con IA.

Esta vista debe ser un visor editorial, no un panel tecnico ni parte obligatoria de Creacion.

Regenerar Memoria requiere autorizacion explicita. Si hay Memoria existente, la IA debe proponer un cambio revisable indicando exactamente que partes van a cambiar y por cuales.

Una edicion manual de Memoria no obtiene prioridad inmutable frente a futuras actualizaciones IA. Sin embargo, cualquier actualizacion posterior debe ser trazable y revisable cuando sustituya contenido significativo.

## 9. Relacion con RAG y prompts

Toda tarea IA de Dendro debe poder usar Memoria cuando exista.

La Memoria debe entrar en el contexto IA como seccion separada y marcada como derivada/no canonica.

Orden de prioridad para ensamblado de contexto:

```text
Canon confirmado
Referencias estructuradas relevantes
Memoria derivada vigente
Memoria obsoleta con aviso
Candidatos/cultivo/propuestas pendientes
Contexto auxiliar
```

Reglas:

1. La IA debe saber que la Memoria no es canon.
2. El canon confirmado debe tener prioridad en presupuesto de contexto.
3. Si la Memoria esta Falta regar o Secada, la app debe avisar al usuario cuando la tarea IA pueda verse afectada.
4. El usuario puede continuar con IA aunque la Memoria este obsoleta.
5. El aviso recomendado es: la memoria puede estar obsoleta; se recomienda Regar antes de continuar.
6. Las respuestas IA no deben presentar Memoria como verdad canonica.
7. Las fuentes/citas de Memoria deben estar disponibles para depuracion y confianza.

Este contrato no exige introducir embeddings o vector DB. Si se anaden en el futuro, deben respetar la misma jerarquia de autoridad.

## 10. @menciones como referencias estructuradas

Las @menciones deben convertirse en referencias estructuradas transversales.

Cuando el usuario escribe una @mencion en un campo soportado, la app debe resolverla a un elemento del proyecto y guardar una referencia estable.

Objetivos:

- Interconectividad tipo wiki sin crear una wiki paralela.
- Backlinks: saber quien menciona a quien.
- Mejor recuperacion RAG.
- Mejor calculo de impacto cuando cambia un elemento.
- Mejor explicacion de contradicciones y huecos.
- Renombrados seguros: cambiar el nombre visible no rompe la referencia.

Reglas:

1. La referencia estructurada debe apuntar a id/tipo estable, no solo a texto.
2. Una mencion ambigua debe pedir desambiguacion o quedar marcada como no resuelta.
3. Una mencion no resuelta no crea canon automaticamente.
4. Las menciones deben poder apuntar a entidades, relaciones, hitos, anillos, ramas y otros elementos que el core soporte.
5. Las menciones deben alimentar RAG, Memoria, impacto y navegacion.
6. La conversion debe ocurrir mediante servicios de aplicacion, no escritura directa de UI a persistencia.

## 11. Motor de impacto

El motor de impacto detecta que cambios pueden volver obsoleta la Memoria o el cultivo de elementos relacionados.

Entradas posibles:

- Relaciones canonicas.
- @menciones estructuradas.
- Hitos y subhitos.
- Anillos y ramas.
- Fuentes/citas de Memoria.
- Propuestas aceptadas.
- Cambios de estado canonico.

Salida principal:

```text
Elementos marcados como Falta regar + causa explicable
```

El motor no debe invalidar contenido automaticamente. Un cambio superior genera revision automatica, no borrado ni reescritura automatica.

La UX principal no debe ser una lista intimidante tipo "afecta a 12 elementos". El usuario debe ver el estado Falta regar en los elementos y secciones donde trabaja.

## 12. Contradicciones, huecos y cultivo

Las contradicciones detectadas por la IA o por el motor de impacto deben aparecer en Cultivo.

Issues esta obsoleto para este flujo.

Reglas:

1. Una contradiccion no modifica canon.
2. Una contradiccion debe estar anclada a los elementos afectados.
3. El usuario debe poder revisar, aceptar una propuesta, corregir manualmente, aplazar o ignorar segun la UI que se implemente.
4. Los huecos y preguntas abiertas tambien viven en Cultivo cuando afectan a una entidad o contexto concreto.
5. La Memoria puede registrar que existe una contradiccion, pero no resolverla como canon sin accion del usuario.

## 13. Potencia causal

Potencia causal significa capacidad potencial de propagar consecuencias a traves del mundo.

No equivale a:

- Importancia narrativa.
- Protagonismo.
- Posicion temporal.
- Nivel metafisico por si solo.

Debe considerar varias dimensiones:

- Alcance de los efectos.
- Profundidad de propagacion.
- Persistencia temporal.
- Intensidad de las consecuencias.
- Capacidad de modificar las condiciones causales de otras entidades.

La importancia narrativa se mantiene como dimension separada. Algo puede ser causalmente menor pero narrativamente central, o causalmente enorme pero periferico para la historia concreta.

## 14. Potencia basal, contextual y realizada

La potencia causal no es un atributo fijo simple.

Dendro debe distinguir, si el modelo lo requiere:

- Potencia basal: derivada de la naturaleza, escala o posicion estructural de una entidad.
- Potencia contextual: cambia segun epoca, escenario, conflicto, relaciones activas y estado del mundo.
- Potencia realizada: se infiere retrospectivamente a partir de consecuencias que ocurrieron realmente.

Una entidad debe tener un anillo principal dentro de una vista causal concreta. Puede tener posiciones contextuales alternativas, pero no pertenecer simultaneamente a varios anillos dentro de la misma vista porque eso reduce legibilidad.

## 15. Anillos como jerarquia causal visible

Los anillos siguen existiendo como estructura visible, comprensible, inspeccionable y editable.

La IA puede:

- Sugerir colocacion inicial.
- Detectar inconsistencias.
- Proponer mover entidades.
- Explicar relaciones causales que justifican la propuesta.
- Predecir consecuencias estructurales de aceptar el cambio.

La IA no debe:

- Controlar la jerarquia de forma opaca.
- Mover entidades entre anillos sin aceptacion.
- Hacer que los anillos desaparezcan de la experiencia del usuario.

Los cambios de anillo son propuestas estructurales, no candidatos narrativos ordinarios.

## 16. Propagacion causal

La jerarquia de anillos representa una asimetria predominante de propagacion, no una prohibicion rigida.

Regla descendente:

- Un cambio en un nivel causal superior debe marcar dependientes inferiores como potencialmente afectados o Falta regar.
- No debe borrar, invalidar ni reescribir automaticamente contenido inferior.

Regla ascendente:

- Una entidad de menor potencia causal puede afectar a una superior bajo condiciones explicitas.
- Estas relaciones deben poder representarse como excepciones causales, puntos de apalancamiento, catalizadores, vulnerabilidades, efectos acumulativos o amplificaciones.

## 17. Propuestas estructurales

Una propuesta estructural es una sugerencia revisable sobre la estructura del proyecto.

Ejemplos:

- Mover una entidad de un anillo a otro.
- Cambiar el anillo principal en un contexto.
- Marcar una excepcion causal ascendente.
- Ajustar una dependencia causal.

Cada propuesta estructural debe incluir:

- Elemento afectado.
- Estado actual.
- Estado propuesto.
- Contexto en el que aplica.
- Razones.
- Relaciones/fuentes que la justifican.
- Consecuencias esperadas.
- Acciones: aceptar, rechazar, modificar o aplazar.

Aceptar una propuesta estructural puede modificar estructura, pero solo mediante servicio de aplicacion y con trazabilidad.

## 18. UX de Memoria

La UX tiene dos superficies principales.

### 18.1 Foco y Cultivo

Foco/Cultivo muestran lo que afecta al trabajo diario:

- Estado de Memoria del elemento.
- Falta regar.
- Contradicciones.
- Huecos.
- Preguntas abiertas.
- Propuestas estructurales.
- Avisos cuando una tarea IA puede usar Memoria obsoleta.

La Memoria debe ser consultable si el usuario quiere, pero no debe exigir gestion constante.

### 18.2 Configuracion de proyecto

Configuracion ofrece el visor editorial de Memoria:

- Memoria global.
- Memoria por elemento cuando aplique.
- Fuentes/citas.
- Estado de frescura.
- Edicion manual.
- Borrado.
- Regeneracion IA autorizada.
- Diff exacto antes/despues cuando la IA proponga sustituir contenido.

No debe mostrarse un resumen automatico de Memoria al abrir proyecto salvo nuevo contrato.

## 19. Comportamiento sin IA

La app debe seguir funcionando sin IA.

Sin IA disponible:

- El usuario puede crear, editar y consultar canon.
- Las @menciones estructuradas deben seguir funcionando.
- Backlinks y referencias locales deben seguir funcionando.
- El sistema puede marcar Falta regar mediante impacto determinista.
- La Memoria existente puede leerse, editarse o borrarse.
- Regenerar/actualizar Memoria con IA queda deshabilitado o muestra aviso recuperable.

La IA mejora el sistema, pero no puede ser requisito para abrir, editar o guardar proyectos.

## 20. Persistencia y migracion

BETA2-MEM debe disenar la Memoria pensando primero en proyectos nuevos.

Para proyectos existentes:

- No debe generarse Memoria automaticamente durante migracion.
- No debe perderse informacion.
- El proyecto puede quedar en estado Sin Memoria hasta que el usuario Regue o regenere desde Configuracion.
- Cualquier migracion debe ser testeada con guardado/recarga.

La Memoria debe persistir con fuentes, estado de frescura, origen y trazabilidad suficiente.

## 21. Trazabilidad y seguridad

Todo cambio relevante relacionado con Memoria debe registrar:

- Origen.
- Autor o agente: usuario/IA/sistema.
- Fecha.
- Elementos afectados.
- Motivo o causa.
- Fuentes usadas.

Si una tarea IA usa Memoria, las trazas de contexto deben respetar secretos, privacidad y visibilidad vigente del proyecto.

Aunque BETA1 haya retirado visibilidad de UI, ningun contrato futuro debe asumir que es seguro filtrar informacion no autorizada.

## 22. Orden de implementacion

La epica BETA2-MEM debe implementarse en este orden:

1. Contrato autoritativo: este documento.
2. Modelo de dominio y persistencia.
3. @menciones estructuradas.
4. Motor de impacto y Falta regar.
5. Servicio IA de actualizacion de Memoria.
6. Integracion RAG/prompt.
7. Pipeline Regar v2.
8. Potencia causal, anillos y propuestas estructurales.
9. UI Foco/Cultivo.
10. Visor editorial en Configuracion.
11. QA integral.

No se debe saltar al servicio IA o UI antes de tener dominio/persistencia y referencias estructuradas suficientes.

## 23. Reglas para agentes

Cualquier agente que trabaje en BETA2-MEM debe respetar estas reglas:

1. No crear modelos paralelos si el core ya representa el concepto.
2. No hacer que UI escriba directamente en persistencia.
3. No hacer que IA modifique canon.
4. No reintroducir importacion documental.
5. No tratar Memoria como canon.
6. No revivir Issues como destino principal de contradicciones.
7. No ocultar anillos ni volverlos totalmente automaticos.
8. No anadir un boton principal de Memoria al flujo normal de Creacion.
9. No cerrar tickets sin pruebas definidas.
10. Mantener terminologia: Memoria, Regar, Cultivar, Falta regar, Regada, Secada, Foco, Mapa, Cronologia.

## 24. Criterios globales de aceptacion de la epica

La epica BETA2-MEM solo puede considerarse completa cuando:

1. La Memoria persiste y recarga sin perdida.
2. La IA usa Memoria en tareas relevantes sin confundirla con canon.
3. Regar mantiene Memoria actualizada bajo autorizacion del usuario.
4. Las @menciones son referencias estructuradas y renombrables.
5. Los cambios relevantes marcan Falta regar antes de IA.
6. Las contradicciones aparecen en Cultivo.
7. Los anillos siguen visibles y editables.
8. La IA propone cambios de anillo como propuestas estructurales revisables.
9. La app funciona sin IA.
10. Hay visor editorial de Memoria en Configuracion.
11. Hay pruebas unitarias, integracion y smoke de los flujos principales.
12. No se viola canon, visibilidad ni trazabilidad.

## 25. Declaracion final

La Memoria narrativa viva debe hacer que Dendro parezca recordar su mundo sin apropiarse de el.

Debe ayudar a la IA a razonar mejor, al usuario a detectar tensiones antes y al proyecto a mantenerse coherente con menos carga abstracta.

Pero el centro no cambia: el usuario controla el canon, la IA propone, Regar mantiene vivo el sistema y Cultivar convierte los hallazgos en decisiones revisables.