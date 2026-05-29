# narrative-architect

Aplicacion de escritorio para creacion narrativa, worldbuilding, escritura y direccion de partidas de rol asistida por IA.

## Desarrollo con Docker

Construir:

docker compose build

Entrar al contenedor:

docker compose run --rm dev

## Estructura

apps/desktop - aplicacion de escritorio
packages/domain - modelo y reglas puras
packages/application - casos de uso y servicios
packages/persistence - guardado, carga y migraciones
packages/infrastructure - IA, importadores, exportadores y adaptadores
packages/ui - UI compartida
docs/contracts - contratos autoritativos
docs/architecture - notas de arquitectura
tests - pruebas
ai_outputs - salidas generadas por agentes
