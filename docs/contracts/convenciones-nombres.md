# Convenciones de nombres

Este documento define las convenciones de nomenclatura del proyecto narrative-architect.
Aplica a todo el código fuente, tests, documentación, ramas y commits.

La fuente de verdad de estas reglas es el código existente y este documento.
Cualquier discrepancia debe resolverse actualizando este documento o el código,
según cuál refleje la intención arquitectónica correcta.

---

## 1. Paquetes y módulos Python

### 1.1 Paquetes de aplicación

Los paquetes dentro de `packages/` siguen el nombre de la capa a la que pertenecen:

| Paquete | Capa | Propósito |
|---------|------|-----------|
| `packages/domain/` | Domain | Modelo de dominio puro |
| `packages/application/` | Application | Casos de uso y orquestación |
| `packages/persistence/` | Persistence | Almacenamiento y migraciones |
| `packages/infrastructure/` | Infrastructure | IA, importación, exportación |
| `packages/ui/` | UI | Interfaz de escritorio |

**Reglas:**
- Nombres en **inglés**, en minúsculas, snake_case.
- Un solo nivel de anidamiento dentro del paquete de capa.
- El `__init__.py` de cada paquete debe contener solo el docstring del paquete y, opcionalmente, `__all__` con las exportaciones principales. No debe importar submodulos automáticamente salvo que haya una razón explícita.

### 1.2 Archivos de módulo

- **snake_case.py** — todo en minúsculas con guiones bajos.
- El nombre del archivo describe el concepto principal que contiene.
- Un archivo = un concepto o un conjunto estrechamente relacionado.

| Archivo | Contenido |
|---------|-----------|
| `result.py` | Tipo Result (Ok, Error) y utilidades |
| `config.py` | AppConfig, LoggingConfig, load_settings |
| `exceptions.py` | Jerarquía de excepciones base |
| `project.py` | Modelo Project |
| `store.py` | ProjectStore y helpers de I/O |
| `schema.py` | Versionado de esquema |
| `bootstrap.py` | Inicialización de servicios |

### 1.3 Paquetes de tests

Espejo de la estructura de `packages/`:

```
tests/
├── conftest.py                    # Fixtures base — disponibles para toda la suite
├── test_sanity.py                 # Tests de sanidad globales
├── domain/
│   ├── conftest.py                # Fixtures específicas de dominio
│   ├── test_result.py
│   ├── test_config.py
│   └── ...
├── application/
│   ├── conftest.py
│   └── test_bootstrap.py
├── persistence/
│   ├── conftest.py
│   └── test_store.py
├── architecture/
│   └── test_dependency_rules.py
└── ui/
    └── ...
```

**Reglas:**
- Cada carpeta de tests tiene su `__init__.py` (puede estar vacío).
- Los archivos de test se nombran `test_<modulo>.py`.
- Las fixtures compartidas van en `conftest.py` de la carpeta correspondiente.

---

## 2. Clases

| Elemento | Convención | Ejemplo |
|----------|-----------|---------|
| Modelos de dominio | PascalCase | `Project`, `AppContext` |
| Configuraciones | PascalCase | `AppConfig`, `LoggingConfig` |
| Excepciones | PascalCase, sufijo `Error` | `DomainError`, `ConfigurationError` |
| Casos de uso | PascalCase, sufijo `UseCase` | `CreateProjectUseCase` |
| Stores/Repositorios | PascalCase, sufijo descriptivo | `ProjectStore` |
| Clases de test | PascalCase, prefijo `Test` | `TestBootstrapSmoke`, `TestInitializeSuccess` |
| Enumeraciones | PascalCase | `CanonState`, `VisibilityLevel` |

**Reglas:**
- No usar prefijos como `I` para interfaces (Python no es Java/C#).
- No usar sufijos como `Impl` para implementaciones.
- Los nombres deben ser autodescriptivos: `ProjectStore` > `Store`.

---

## 3. Funciones y métodos

| Elemento | Convención | Ejemplo |
|----------|-----------|---------|
| Funciones de utilidad | snake_case | `load_settings()`, `reset_settings()` |
| Métodos de instancia | snake_case | `project.touch()`, `store.save()` |
| Métodos de clase | snake_case | `Project.from_dict()` |
| Factories de Result | snake_case, prefijo opcional | `ok_result()`, `error_result()` |
| Funciones de test | snake_case, prefijo `test_` | `test_returns_ok_with_default_config()` |
| Propiedades | snake_case | `context.data_dir` |

### 3.1 Verbos recomendados

| Operación | Verbo |
|-----------|-------|
| Crear instancia | `create`, `from_*` (classmethod) |
| Guardar | `save` |
| Cargar | `load`, `open` |
| Obtener valor | `get_*` |
| Establecer valor | `set_*` (evitar si es un dataclass) |
| Validar | `validate_*`, `is_*`, `check_*` |
| Convertir a dict | `to_dict()` |
| Convertir desde dict | `from_dict()` (classmethod) |
| Inicializar | `initialize` |
| Ejecutar caso de uso | `execute` |

---

## 4. Variables

| Elemento | Convención | Ejemplo |
|----------|-----------|---------|
| Variables locales | snake_case | `project_name`, `config_data` |
| Constantes de módulo | UPPER_SNAKE_CASE | `CURRENT_SCHEMA_VERSION`, `MAX_BACKUPS` |
| Parámetros de función | snake_case | `config_overrides`, `schema_version` |
| Variables de tipo | mayúscula simple | `T`, `E`, `U` |

---

## 5. Excepciones

Ver documento completo en `docs/contracts/convenciones-errores.md`.

Resumen:
- Toda excepción hereda de `NarrativeArchitectError`.
- Códigos: `DOMAIN_XXX`, `APP_XXX`, `CONFIG_XXX`, `PERSIST_XXX`.
- Sufijo `Error` en el nombre de la clase.

---

## 6. Tests

Ver documento completo en `docs/contracts/convencion-pruebas.md`.

Resumen:
- Archivos: `test_<descripcion>.py`.
- Clases: `Test<Descripcion>` (agrupan por concepto o escenario).
- Métodos: `test_<descripcion>` en snake_case.
- Fixtures: snake_case, nombre descriptivo (`app_config`, `temp_data_dir`).
- Marcadores: `@pytest.mark.smoke`, `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.domain`, `@pytest.mark.application`.

---

## 7. Servicios de aplicación

- Nombres con sufijo `UseCase`: `CreateProjectUseCase`, `OpenProjectUseCase`.
- Un solo método público `execute(command)` por caso de uso.
- Los comandos son `@dataclass(frozen=True)` con sufijo `Command`: `CreateProjectCommand`.

---

## 8. Archivos de configuración y proyecto

| Elemento | Convención | Ejemplo |
|----------|-----------|---------|
| Proyecto narrative-architect | `.json` | `mi-proyecto.json` |
| Config de aplicación | `.toml` o entorno | `pyproject.toml`, variables `NA_*` |
| Documentación | `.md` | `README.md`, `convenciones-nombres.md` |
| Tickets Kanban | `.md` | `B01-T06.md` |

---

## 9. Ramas Git

Formato: `tipo/BXX-TYY-descripcion-corta`

| Tipo | Uso |
|------|-----|
| `feature/` | Nueva funcionalidad |
| `fix/` | Corrección de errores |
| `docs/` | Documentación |
| `test/` | Pruebas |
| `refactor/` | Refactorización |
| `chore/` | Mantenimiento |
| `build/` | Infraestructura, CI, Docker |

Ejemplo: `feature/B02-T01-modelo-proyecto-extendido`, `docs/B01-T07-convenciones-nombres-esquema`

---

## 10. Commits

Formato: `tipo(scope): mensaje descriptivo ref BXX-TYY`

| Tipo | Uso |
|------|-----|
| `feat` | Nueva funcionalidad |
| `fix` | Corrección |
| `chore` | Mantenimiento, tooling |
| `docs` | Documentación |
| `test` | Tests |
| `refactor` | Refactorización |
| `build` | CI, Docker, dependencias |
| `ci` | CI/CD |

Ejemplos:
```
feat(application): bootstrap module with AppContext and smoke test ref B01-T06
docs(contracts): naming conventions and schema evolution strategy ref B01-T07
chore(kanban): mark B01-T06 as Done with closing summary ref B01-T06
```

---

## 11. Convenciones de estilo Python

- Python 3.12+.
- Type hints obligatorios en todas las funciones y métodos públicos.
- `from __future__ import annotations` en todos los archivos.
- Dataclasses frozen para objetos inmutables (comandos, config).
- Dataclasses mutables para entidades de dominio con identidad (Project).
- `Result[T, E]` para flujo de control, no excepciones.
- `__all__` en módulos con API pública.
- Docstrings en triple comilla, formato descriptivo.

---

## 12. Historial de cambios

| Fecha | Cambio |
|------|--------|
| 2026-05-29 | Versión inicial — documento creado como parte de B01-T07 |
