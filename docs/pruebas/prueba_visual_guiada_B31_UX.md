# Prueba visual guiada B31 UX

Fecha: 2026-06-03
Estado: validación parcial A-E ejecutada por el usuario.
Resultado parcial: NO PASA.

## Veredicto provisional

```text
B31-T12 parcial — NO PASA
Ámbito validado: Home, configuración, navegación, ventanas externas y modo avanzado.
Bloqueantes principales:
- Header técnico persistente.
- Schema v? visible.
- Contadores visibles en espacios principales.
- Configuración no agrupada ni minimalista.
- Ajustes IA no funcionales.
- Modo avanzado/diagnóstico mal ubicados.
- Estética todavía demasiado técnica.
- Transiciones insuficientes.
- Paneles laterales persisten al volver a Home.
- No hay creación normal de entidades/corpus/candidatos/fuentes/capas fuera de modo avanzado.
```

## Decisión de QA

No continuar con la validación F-R hasta corregir A-E o aceptar deuda explícita.

Ticket correctivo abierto:

- `B31-UX-FIX-01 — Corrección UX Home/configuración/inmersión antes de continuar QA`

## A. Home

Resultado: NO PASA.

Observaciones:

- A1 y A2 pasan: existe estructura base de Home/navegación.
- A3 falla: persiste lenguaje técnico en superficie principal.
- A10/A11/A12 fallan: estética todavía demasiado técnica/pesada.

Corrección esperada:

- Home sin header superior técnico.
- Sin `Schema v?` en modo normal.
- Sin proveedor IA/fallback visible en superficie principal.
- Sin contadores en Creación/Galería/Sesión.
- Tres nodos centrales conectados: Creación, Galería, Sesión.
- Fondo blanco roto/cálido.
- Iconografía homogénea y minimalista.
- Tipografía más cercana a máquina de escribir/cuaderno de autor, manteniendo legibilidad.

## B. Configuración

Resultado: PARCIAL / NO CUMPLE UX.

Observaciones:

- B1-B6 indican que abrir/guardar/nuevo/cerrar existen.
- Están como botones sueltos, no como configuración agrupada.
- `Ajustes IA` existe pero no hace nada: P0.

Corrección esperada:

- Icono Proyecto:
  - Nuevo
  - Abrir
  - Guardar
  - Cambiar proyecto / cerrar si se mantiene
- Icono Configuración:
  - Apariencia / UX
  - Modo avanzado
  - Diagnóstico
  - Ajustes IA
- Panel interno lateral, no ventana externa.

## C. Navegación / inmersión

Resultado: PARCIAL.

Observaciones:

- C1-C7 pasan funcionalmente.
- C9 falla: transiciones insuficientes.
- Al volver a Home, el panel lateral puede persistir.

Corrección esperada al volver a Home:

- Cerrar RightDrawer.
- Cerrar overlays internos.
- Limpiar selección contextual.
- Mantener solo estado de proyecto.
- Transición Home -> espacio con zoom suave hacia nodo/espacio.
- Botón volver como símbolo minimalista, no botón textual pesado.

## D. Ventanas externas

Resultado: no concluyente funcionalmente.

Observación:

- No se puede concluir todo el flujo porque aún faltan caminos normales limpios para crear/editar entidades desde modo normal.

Corrección esperada:

- Sin ventanas externas en flujos normales.
- Edición/detalle en RightDrawer o panel interno.

## E. Modo avanzado

Resultado: funcionalmente PASA, pero revela problema de producto.

Observaciones:

- El modo avanzado oculta/muestra vistas técnicas.
- Pero el modo normal pierde accesos funcionales limpios a corpus/relaciones/candidates/fuentes/capas.

Corrección esperada:

Modo normal debe permitir:

- Crear entidad desde Creación/grafo.
- Gestionar relaciones visualmente.
- Revisar candidatos como cards/sugerencias.
- Gestionar fuentes como referencias legibles.
- Gestionar capas/worldbuilding de forma visual.

Modo avanzado queda para:

- Tablas técnicas.
- IDs.
- JSON.
- Metadata.
- Diagnóstico.

## Criterio de repetición A-E

Después de `B31-UX-FIX-01`, repetir solo A-E.

Criterio para continuar con F-R:

```text
A: PASA
B: PASA
C: PASA
D: al menos sin ventanas externas confirmadas donde sea posible
E: PASA + modo normal tiene equivalentes funcionales no técnicos
```

Si no se cumple, no continuar con F-R salvo aceptación explícita de deuda.
