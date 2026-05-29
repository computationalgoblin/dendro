# ADR 008 — Distinción ProjectMetadata vs configuración de proyecto

**Estado:** Aceptado
**Fecha:** 2026-05-29
**Bloque:** 2
**Ticket asociado:** B02-T01

## Contexto

En el modelo extendido de `Project` (B02-T01) se definieron 8 dataclasses
de "configuración". Una de ellas es `ProjectMetadata`, que semánticamente
no es configuración editable por el usuario sino metadatos del proyecto.
Esta distinción no estaba documentada explícitamente y puede causar
confusión en bloques futuros.

## Decisión

Se distinguen cuatro categorías de datos en el modelo `Project`:

### 1. Identidad y ciclo de vida (campos directos)

```
id, name, description, primary_language, secondary_languages,
created_at, updated_at
```

Datos fundamentales del proyecto. Siempre presentes. Algunos son editables
(name, description, primary_language) y otros son gestionados por el
sistema (id, created_at, updated_at).

### 2. Configuración editable del proyecto (7 dataclasses)

```
GeneralProjectConfig  — tema, tags, visibilidad por defecto
ToneConfig            — tono narrativo, formalidad, humor, oscuridad
GenreConfig           — género principal, secundarios, notas
RealismConfig         — nivel de realismo, magia, tecnología, escala
AIConfig              — habilitación IA, modelo, creatividad
VisibilityConfig      — visibilidad por defecto de entidades y relaciones
ExportConfig          — formato de exportación, marca de agua
```

Estas 7 dataclasses son **editables por el usuario** a través de
`update_config(path, value)`. Sus valores pueden ser modificados,
persistidos y recargados.

### 3. Metadatos de proyecto (1 dataclass)

```
ProjectMetadata       — version, author, tags, custom_fields
```

`ProjectMetadata` **no es configuración editable** en el mismo sentido
que las 7 anteriores. Es información sobre el proyecto como artefacto:
quién lo creó, qué versión tiene, qué tags lo describen. El campo
`custom_fields` permite extensión ad-hoc por plugins o herramientas
sin modificar el modelo.

### 4. Colecciones preparadas (listas vacías)

```
entities, relations, sources, history, issues
```

No son configuración ni metadatos. Son contenedores para datos narrativos
que se poblarán en bloques posteriores. Están en `Project` para que la
estructura sea extensible sin rediseño.

## Por qué ProjectMetadata es un dataclass y no un dict libre

- **Tipado:** campos conocidos (version, author, tags) tienen tipos
  concretos; `custom_fields: dict` permite extensión sin perder tipado
  en los campos fijos
- **Serialización:** `to_dict`/`from_dict` maneja el dataclass de forma
  idéntica a las otras 7 configuraciones
- **Migración:** si cambia la estructura de metadatos en v3, la migración
  puede tratar `ProjectMetadata` igual que cualquier otro dataclass

## Consecuencias

- Al documentar UI o comandos, distinguir entre "configuración del proyecto"
  (7 dataclasses editables) y "metadatos del proyecto" (ProjectMetadata).
- `get_config("project_metadata.author")` funciona, pero conceptualmente
  `author` no es una preferencia de configuración.
- En el futuro podría añadirse un método específico `get_metadata()` vs
  `get_config()` si la UI necesita tratarlos de forma distinta.
- Los `custom_fields` de ProjectMetadata no deben usarse como almacén
  indiscriminado. En su momento convendrá definir un contrato de qué
  puede ir ahí y qué no.

## Deuda controlada relacionada

- Las rutas de configuración (`get_config(path)`, `update_config(path)`)
  no validan que el path corresponda a una ruta permitida. En bloques
  futuros debería existir una lista o esquema de rutas válidas para
  evitar typos y accesos no intencionados a campos internos.
- Esta deuda está registrada en el cierre del Bloque 2.
