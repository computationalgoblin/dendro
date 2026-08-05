# Prueba guiada — Dendro 0.9.0b1 (beta cerrada)

> **Qué es esto.** Un recorrido paso a paso de **toda la app** para validar la build antes de
> publicarla, y para que un tester nuevo sepa qué mirar. Es el *dry-run de máquina limpia* que cierra
> la puerta verde del contrato de cierre de beta (sustituye al smoke manual que la automatización no
> puede cubrir: render real, interacción, y arranque del exe empaquetado).
>
> **Cómo usarla.** Ve marcando `[ ]` → `[x]`. Cada paso dice **qué hacer**, el **✅ resultado esperado**
> y la **🚩 señal de fallo** (qué significa si no ocurre). Tiempo estimado: **20–30 min**.
>
> **Idea rectora de Dendro:** *la IA nunca escribe canon*. Propone **candidatos** (semillas) que **tú
> aceptas**. Si en algún punto ves que la IA cambió tu mundo sin que aceptaras nada, eso es un fallo grave.

---

## 0 · Preparación

- [ ] **Extrae el zip entero** en una carpeta (p. ej. `Documentos\Dendro`). **No** ejecutes `Dendro.exe`
      desde dentro del zip, y **no** muevas el exe solo: viaja junto a `_internal/`, `ejemplos/`,
      `LICENSE.txt` y `README-USUARIO.md`.
- [ ] Evita rutas de OneDrive/carpetas sincronizadas (pueden bloquear ficheros mientras la app guarda).
- [ ] **Lanza `Dendro.exe`.** La primera vez Windows puede mostrar **SmartScreen** («Windows protegió tu
      PC»): *Más información → Ejecutar de todas formas*. Si el antivirus lo pone en cuarentena,
      restáuralo y añade una exclusión de la carpeta (ver `README-USUARIO.md`). El exe **no está firmado**
      en la beta — es esperado.
  - ✅ **Esperado:** en pocos segundos aparece una ventana titulada **«Dendro»** ya **maximizada** (o que
        cabe entera en tu pantalla), con la pantalla de **Inicio (Home)**.
  - 🚩 **Si falla:** la ventana no aparece / se queda «No responde» >30s / abre más grande que la pantalla
        y no ves los botones de abajo → apúntalo, es bloqueante.

---

## 1 · Home y primera impresión

- [ ] Lee el **subtítulo/lema** de Home.
  - ✅ Debe hablar de **base de conocimiento narrativa / worldbuilding**. **No** debe mencionar
        «sesiones de rol», «campaña» ni «GM/máster» (eso quedó fuera de la beta).
  - 🚩 Si ves copy de rol vivo → regresión de posicionamiento (WS-A).
- [ ] Busca el **banner «Configura la IA»** (no bloqueante) y el enlace a Ajustes → IA.
  - ✅ Está presente si aún no configuraste proveedor; **no** bloquea el uso de la app.
- [ ] Busca la **tarjeta «Abrir proyecto de ejemplo»** y el **footer** con ⓘ *Acerca de* y *Reportar problema*.
  - ✅ Ambos visibles.
  - 🚩 Sin tarjeta de ejemplo → el onboarding no descubre el mundo de muestra (WS-D).

---

## 2 · Configurar la IA (opcional pero recomendado para probar las 4 mecánicas)

> Puedes hacer **todo el recorrido estructural sin IA**. Configúrala solo si quieres probar
> Regar/Sugerencias/Play/Memoria con un proveedor real (endpoint compatible con OpenAI).

- [ ] **Ajustes → IA.** Introduce proveedor, `base_url` (**https://**), modelo y API key. Guarda.
  - ✅ Al reabrir Ajustes, **la clave sigue puesta** (no se pierde al guardar).
  - ✅ Si pones un `base_url` **http://** remoto (no `localhost`), aparece **aviso de TLS**.
  - ✅ Debe existir una **«declaración de egreso»**: qué sale de tu equipo (proveedor de IA + búsqueda de
        imágenes), sin telemetría.
  - 🚩 La clave se borra al guardar / no hay aviso de http remoto → regresión (WS-B/SHIP).
- [ ] *(Sin proveedor)* cualquier acción de IA debe **fallar con un mensaje claro**, nunca fingir éxito ni
      inventar contenido.

---

## 3 · Abrir el proyecto de ejemplo

- [ ] En Home, pulsa **«Abrir proyecto de ejemplo»**.
  - ✅ Se abre **«La Flor de los Almendros»** y entras en **Creación**. Se copió a una carpeta
        **escribible** (tu carpeta de usuario), no se edita el original de solo-lectura del zip.
  - ✅ El **Mapa de anillos** aparece poblado (no un lienzo vacío).
  - 🚩 Se abre vacío / error de apertura silencioso → WS-C/WS-D.

---

## 4 · Mapa de anillos (la vista principal de Creación)

- [ ] Observa los **anillos concéntricos**: el centro son las entidades de mayor **potencia causal**;
      hacia fuera, menos. Pasa el ratón sobre nodos y relaciones.
  - ✅ Hover resalta el nodo y sus relacionadas; el rendimiento es fluido al mover/zoom.
- [ ] Busca una entidad **secreta** (visibilidad reservada).
  - ✅ Muestra un **candado** (no solo un color) — se distingue a simple vista.
  - 🚩 Ninguna marca de secreto → WS-M (marcador de secreto).
- [ ] Fíjate en el **estado de jardín** de las entidades: **💧/gota** (sedienta, marrón «!») vs **pausa/×**
      (secada, gris). El eje no depende solo del color (canal para daltonismo).
  - ✅ Sedienta y secada se distinguen por **glifo**, no solo por tono.

---

## 5 · Modo Foco (entidad centrada)

- [ ] Doble clic (o abrir) una entidad → entra en **Foco**. Revisa las pestañas **Ficha / Relaciones / Cultivo**.
  - ✅ El **retrato** persiste; los chips y la franja de datos se ven sin solaparse.
- [ ] Pestaña **Relaciones**: pasa el ratón sobre una fila de relación.
  - ✅ Aparece una **«×» para eliminar** esa relación (con confirmación). *(Antes solo se podía borrar
        desde el Mapa.)*
  - 🚩 No hay forma de borrar la relación desde Foco → WS-E.
- [ ] Borra una **entidad** desde el rail/menú de Foco (elige una de prueba).
  - ✅ Pide confirmación y la elimina; el Mapa se actualiza.
- [ ] **Retrato:** prueba a asignar imagen (búsqueda Openverse) y recórtala.
  - ✅ La búsqueda no congela la ventana; puedes cancelar; el recorte se guarda.

---

## 6 · Cronología

- [ ] Ve a la **Cronología**. Busca los botones **`+ Hito`** y **`+ Era`** (visibles, no solo clic-derecho).
  - ✅ Están a la vista; crear un hito lo sitúa en el **presente** por defecto.
  - 🚩 Solo accesibles por menú contextual → WS-E.
- [ ] Arrastra el **lapso de vida** de una entidad y observa las **cajas de rama** (contenedores que
      encierran a sus miembros).
  - ✅ El arrastre ajusta el rango; las cajas de rama se dibujan alrededor de su contenido.
- [ ] Si hay hitos, busca la **CTA de Play** («recorrer»).
  - ✅ Presente cuando hay hitos.

---

## 7 · Regar (mecánica de IA nº1) — *requiere proveedor*

> Regar = la IA **lee la wiki/canon y escribe la página de Memoria** de la entidad + propaga «falta regar»
> a las relacionadas. Es determinista en su efecto: **no crea canon nuevo**.

- [ ] En una entidad **sedienta**, pulsa **Regar**.
  - ✅ Aparece un **indicador de ocupado** (floater de estado) con botón **Cancelar** mientras corre.
  - ✅ Al terminar, la entidad deja de estar sedienta; su **página de Memoria** se actualiza; alguna
        relacionada pasa a **«falta regar»**.
  - 🚩 La ventana se queda «No responde» durante el Regar → regresión grave (el trabajo de IA debe ir en
        hilo aparte, WS-F/B2).
- [ ] Prueba **Regar todas** (lote) y pulsa **Cancelar riego** a mitad.
  - ✅ El lote se detiene; lo ya regado se conserva.
- [ ] Fuerza un error (p. ej. desconecta la red) y regla otra.
  - ✅ Mensaje de error **humanizado** (no un volcado crudo del proveedor). Si la respuesta se **corta**
        por longitud, avisa «la respuesta se cortó / acota o sube presupuesto».

---

## 8 · Sugerencias → semillas → aceptar (mecánica creativa) — *requiere proveedor*

> Única vía creativa con **prompt libre**. La IA propone **semillas** que **germinan**; tú **aceptas**
> (florecen a canon) o **rechazas** (se marchitan).

- [ ] Abre **Sugerencias** (desde Foco o Mapa), escribe una **petición libre** y lánzala.
  - ✅ Aparece feedback del plan; empiezan a **germinar semillas** con notificación pulsante.
  - 🚩 La petición se ignora o se disfraza de «reparar métrica» → WS-E.
- [ ] Abre el **panel de revisión** de una semilla.
  - ✅ Puedes **previsualizar** el candidato antes de decidir; **Aceptar** lo integra al canon;
        **Rechazar** lo descarta.
  - ✅ **Clave de confianza:** hasta que aceptas, **el canon no cambió**.
  - 🚩 Si algo entró al mundo sin que aceptaras → fallo del invariante central.
- [ ] Cierra y reabre el proyecto con semillas **pendientes**.
  - ✅ Las semillas pendientes **rehidratan** como notificaciones (no se pierden en silencio).

---

## 9 · Play (recorrido inmersivo) — *requiere proveedor*

- [ ] Desde la Cronología con hitos, entra en **Play**. Recorre escenas, prueba un **desvío** y llega al
      **epílogo**. Prueba **aplazar** y la **edición inline**.
  - ✅ La navegación fluye (prefetch); los desvíos y el epílogo funcionan.
  - ✅ Ante error del proveedor, mensaje **humanizado** + pre-check de proveedor (no error crudo).

---

## 10 · Memoria (wiki que mantiene la IA)

- [ ] Abre el **visor de Memoria** (Configuración → Memoria, o la pestaña Cultivo en Foco).
  - ✅ Se ve **el cuerpo de la wiki** (no solo el resumen de una línea): cuerpo, **wikilinks**, tags.
  - 🚩 Solo el lead/`resumen` → WS-K (mostrar el cuerpo que la IA generó).
- [ ] Si hay botón **«Regenerar con IA»**, púlsalo.
  - ✅ Corre **sin congelar** la ventana (indicador ocupado, botón deshabilitado mientras trabaja).
  - 🚩 «No responde» hasta el timeout → regresión grave (WS-F/B2).

---

## 11 · Estructura (propuestas de anillo proactivas)

- [ ] Con proyecto cargado, busca la **píldora «⚙ Estructura / ⚙ N ajustes»** (siempre visible) y ábrela.
  - ✅ Abre el **panel de revisión estructural**. Si la IA ha atribuido potencia causal a entidades,
        propone **mover de anillo** (`ring_move`) las mal ubicadas, con justificación.
  - ✅ Entidad **sin potencia atribuida** → **no se juzga** (silencio honesto, sin ruido).
- [ ] *(Con proveedor)* pulsa **«Proponer estructura»**.
  - ✅ Propone **crear** anillos que faltan o **fusionar** redundantes, con nombres diegéticos.
- [ ] **Acepta** una propuesta de mover entidad.
  - ✅ Se **materializa como candidato**, persiste, y **el Mapa + la Cronología se reconstruyen al
        instante** sin expulsarte a Foco.
  - 🚩 Aceptar no reubica visualmente el nodo → WS-STRUCT (refresh completo).

---

## 12 · Deshacer / Rehacer (red de seguridad)

- [ ] Tras un **borrado** (entidad o relación) o tras **aceptar un candidato**, pulsa **Ctrl+Z**.
  - ✅ La acción se **revierte** (la entidad/relación vuelve, o el candidato aceptado se deshace).
  - [ ] Pulsa **Ctrl+Y** (o Ctrl+Shift+Z) → **rehace**.
  - ✅ La acción se **rehace**.
  - 🚩 Ctrl+Z no hace nada / corrompe el proyecto → WS-C (deshacer por instantánea).
- [ ] Comprueba que **Ctrl+Z dentro de un campo de texto** deshace *el texto*, no el mundo entero
      (solo actúa a nivel de proyecto cuando el campo no consumió la tecla).

---

## 13 · Persistencia y copias de seguridad

- [ ] Haz varios cambios, **guarda** (o deja que el autosave de ~800 ms actúe), **cierra** y **reabre** el
      proyecto.
  - ✅ **Todo se conserva** sin pérdida (entidades, relaciones, hitos, retratos, memoria, semillas
        pendientes).
  - 🚩 Cualquier pérdida al recargar → fallo de persistencia.
- [ ] Guarda **varias veces**. Junto al `.json` del proyecto deben acumularse **copias `.bak`**.
  - ✅ Se conserva **la más reciente** entre las N copias (rotación correcta).
- [ ] En el panel de **Proyecto**, prueba **«Restaurar copia de seguridad»** (o provoca un fallo de apertura).
  - ✅ Puedes listar y **restaurar** un backup; un fallo de apertura ofrece **acción** (no te deja en
        Home vacío en silencio).

---

## 14 · Privacidad: los secretos NO salen a la IA — *requiere proveedor*

> Invariante de confianza (WS-B/B1). El canon marcado **PRIVADO_AUTOR** nunca egresa; SECRETO_MUNDO /
> SECRETO_CANONICO / NO_EXPORTABLE viajan como **marcador** («[entidad secreta omitida]»), no con su texto.

- [ ] Marca una entidad como **secreta/privada** y **Regar** o **Sugerir** sobre una vecina suya.
  - ✅ El resultado **no revela** el contenido secreto de la vecina. *(Si tienes acceso al log de app,
        el prompt enviado no contiene su texto — ver §16.)*
  - 🚩 El texto secreto aparece en la respuesta o en el prompt → fuga (bloqueante).

---

## 15 · Robustez al cerrar

- [ ] Lanza un **Regar/Sugerencia/Play** y **cierra la ventana** mientras el trabajo de IA está **en vuelo**.
  - ✅ La app cierra limpio, **sin crash** ni ventana de error del sistema.
  - 🚩 «Dendro.exe dejó de funcionar» al cerrar con job en vuelo → WS-F (workers).

---

## 16 · Reportar problema y registros

- [ ] En Home (footer), abre **«Reportar problema»** y **«Abrir carpeta de registros»**.
  - ✅ Se abre `~/.narrative-architect/` con **`dendro.log`** (rotativo) sellado con versión + SO.
        «Reportar problema» prepara un correo con crash+log+versión+SO.
  - ✅ Los **fallos del proveedor de IA** dejan traza en `dendro.log` (la señal nº1 de la beta).
  - [ ] Provoca un error serio (p. ej. abrir un `.json` corrupto) → aparece el **banner de recuperación
        persistente** con **«Abrir registro»** (no un toast que se desvanece).

---

## Veredicto

- [ ] **Sin 🚩 bloqueantes** en §0–§16 → la build está lista para distribuir como **beta cerrada**.
- [ ] Si aparece algún 🚩, anota el número de sección + qué viste y devuélvelo antes de etiquetar/tag.

**Camino mínimo sin IA** (si no configuras proveedor): §0–§6, §11 (solo lectura de propuestas
deterministas), §12–§13, §15–§16. Las mecánicas de IA (§7–§10, §14) necesitan proveedor.
