# Dendro — guía rápida (beta cerrada para Windows)

## ¿Qué es Dendro?

Dendro es una aplicación de escritorio para **crear mundos y relatos**: personajes,
lugares, facciones, hitos y cronologías organizados como un **jardín narrativo** que
crece contigo. Una IA te ayuda a *regar* tus entidades, proponerte sugerencias y
jugar tu cronología en modo Play — pero **la IA nunca escribe tu canon**: todo lo que
propone son semillas que tú aceptas o rechazas. Tu mundo es tuyo.

## Instalación

1. Descarga el zip de Dendro y **descomprímelo** en cualquier carpeta
   (por ejemplo, `Documentos\Dendro`). No necesitas instalar Python ni nada más.
2. Entra en la carpeta descomprimida y haz doble clic en **`Dendro.exe`**.
3. Si Windows muestra el aviso azul de SmartScreen (la beta no va firmada),
   pulsa **«Más información» → «Ejecutar de todas formas»**.

## Configurar la IA (opcional, pero recomendado)

Dendro funciona sin IA, pero **Regar, las Sugerencias y el modo Play la necesitan**.
Para activarla:

1. Pulsa el **engranaje** (⚙) → **Configuración** → pestaña **IA**.
2. Rellena:
   - **URL** de un servicio compatible con OpenAI (por ejemplo, la de tu proveedor
     o la de un servidor local tipo LM Studio / Ollama).
   - **Modelo** (el nombre exacto que espera tu proveedor).
   - **API key** (si tu proveedor la requiere).
3. Pulsa **«Probar conexión»** para comprobar que todo responde.

## Tu primer proyecto

1. Pulsa **«Nuevo / abrir proyecto»** y elige crear uno nuevo.
2. El **asistente** te ofrece varios *presets* (tipo de mundo/relato) para empezar
   con una estructura razonable. Elige uno, dale nombre y escoge dónde guardarlo.
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

## Esto es una BETA

Gracias por probar Dendro. Es una versión beta: puede haber errores. Si algo falla,
la app intenta seguir viva, te lo avisa y deja un rastro en
`C:\Users\<tu usuario>\.narrative-architect\dendro_crash.log` — adjúntalo cuando
reportes un problema, junto con qué estabas haciendo. Tus datos están a salvo:
cada guardado conserva la copia `.bak` anterior.

## Licencia

Esta beta se entrega solo para evaluación personal (ver el fichero `LICENSE`):
no compartas el zip ni el enlace de descarga. **Los mundos y relatos que crees
con Dendro son tuyos.**
