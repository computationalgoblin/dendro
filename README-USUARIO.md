# Dendro — guía rápida (beta cerrada para Windows)

## ¿Qué es Dendro?

Dendro es una aplicación de escritorio para **crear mundos y relatos**: personajes,
lugares, facciones, hitos y cronologías organizados como un **jardín narrativo** que
crece contigo. Una IA te ayuda a *regar* tus entidades, proponerte sugerencias y
jugar tu cronología en modo Play — pero **la IA nunca escribe tu canon**: todo lo que
propone son semillas que tú aceptas o rechazas. Tu mundo es tuyo.

## Instalación

1. Descarga el zip y **descomprime la carpeta ENTERA** en un sitio con permiso de
   escritura (por ejemplo, `C:\Dendro`). No necesitas instalar Python ni nada más.
   **No** ejecutes `Dendro.exe` desde dentro del visor de zips de Windows: extrae
   primero. Evita la carpeta `Documentos` si la tienes sincronizada con OneDrive
   (puede dar fallos la primera vez).
2. Entra en la carpeta descomprimida y haz doble clic en **`Dendro.exe`**.
   `Dendro.exe` **debe quedarse junto a la carpeta `_internal`**: para moverlo o
   anclarlo, mueve la carpeta entera o crea un **acceso directo** — no copies solo el
   `.exe` (sin `_internal` no arranca).
3. Si Windows muestra el aviso azul de **SmartScreen** (la beta no va firmada),
   pulsa **«Más información» → «Ejecutar de todas formas»**.
4. Si tu **antivirus** (Windows Defender u otro) lo borra o lo pone en cuarentena, es
   un **falso positivo** habitual de un `.exe` recién compilado y sin firma: restáuralo
   desde la cuarentena y **añade una exclusión** para la carpeta de Dendro (o vuelve a
   descargarlo del mismo enlace). Si «desaparece» al extraerlo, mira ahí primero.

## Configurar la IA (opcional, pero recomendado)

Dendro funciona sin IA, pero **Regar, las Sugerencias y el modo Play la necesitan**.
Para activarla:

1. En el Inicio, pulsa **Ajustes** → pestaña **IA** (o el botón **Configurar IA** del aviso).
2. Rellena:
   - **URL** de un servicio compatible con OpenAI (por ejemplo, la de tu proveedor
     o la de un servidor local tipo LM Studio / Ollama).
   - **Modelo** (el nombre exacto que espera tu proveedor).
   - **API key** (si tu proveedor la requiere).
3. Pulsa **«Probar conexión»** para comprobar que todo responde.

## Tu primer proyecto

1. Pulsa **«Nuevo / abrir proyecto»** y elige crear uno nuevo.
2. El **asistente** te ofrece varias *plantillas de tono* («Tragedia íntima»,
   «Fábula oscura»…) que rellenan la configuración creativa —género, tono, temas—
   para que la IA sepa de qué va tu obra. No crean entidades ni estructura: eso lo
   plantas tú. Elige una si te encaja, dale nombre y escoge dónde guardarlo.
   El Mapa arranca con unos anillos básicos que puedes cambiar.
3. Ya puedes plantar tus primeras entidades en el Mapa, abrirlas en Foco,
   regarlas y ver crecer el jardín.

¿Prefieres ver Dendro en marcha antes de empezar? En la carpeta **`ejemplos/`**
(junto a `Dendro.exe`) viene **«La Flor de los Almendros»**, un proyecto de muestra:
ábrelo con **«Nuevo / abrir proyecto» → abrir** y explóralo con libertad.

## ¿Dónde se guardan mis datos?

- **Proyectos**: donde tú elijas al crearlos (un fichero `.json` con copia de
  seguridad `.bak` automática en cada guardado, más una carpeta `.assets` con las
  imágenes al lado).
- **Ajustes de la app** (incluido el proveedor de IA): `%APPDATA%\Dendro\settings.json`.
- **Preferencias y registros**: `C:\Users\<tu usuario>\.narrative-architect`.

Para hacer copia de seguridad de tu mundo basta con copiar el `.json` del proyecto
y su carpeta `.assets`.

## ¿Qué sale de tu equipo?

Dendro trabaja en local. Solo sale información cuando **tú** usas una función que llama
a un servicio externo:

- **IA** (Regar / Sugerencias / Play / Memoria): se envía el **canon visible** relevante
  a **tu** proveedor configurado (la URL de Ajustes → IA). Las entidades que marques como
  **privadas o secretas NO se comparten con la IA**. Usa un proveedor **HTTPS** (o local)
  de confianza.
- **Buscar imagen en internet** (retratos): tu texto de búsqueda va a DuckDuckGo /
  Openverse para encontrar imágenes.

Dendro **no** tiene telemetría ni te rastrea: no se envía nada más que lo anterior.

## Esto es una BETA

Gracias por probar Dendro. Es una versión beta: puede haber errores. Si algo falla,
la app intenta seguir viva, te lo avisa y deja un rastro en
`C:\Users\<tu usuario>\.narrative-architect\dendro_crash.log` — adjúntalo cuando
reportes un problema, junto con qué estabas haciendo. Lo más rápido es el botón
**«Reportar problema»** del Inicio: prepara el correo con la versión, tu sistema y
las últimas líneas del registro (puedes revisarlo antes de enviarlo).

Tus datos están a salvo:

- Lo que escribes **se guarda solo** en cuanto dejas de teclear. Puedes forzarlo con
  **Ctrl+S** en cualquier momento; la píldora **Guardar** avisa con un punto (•) si
  queda algo por escribir.
- **Ctrl+Z** y **Ctrl+Y** deshacen y rehacen cambios de tu mundo (crear, borrar,
  editar), no solo lo último que tecleaste.
- Cada guardado conserva la copia `.bak` anterior, y en **Proyecto → Restaurar copia
  de seguridad** puedes volver a un momento anterior eligiéndolo por fecha.
- En **Proyecto → Exportar a Markdown** te llevas el mundo entero como carpeta de
  ficheros de texto, legible sin Dendro.

## Licencia

Esta beta se entrega solo para evaluación personal (ver el fichero `LICENSE.txt`):
no compartas el zip ni el enlace de descarga. **Los mundos y relatos que crees
con Dendro son tuyos.**
