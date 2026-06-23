# Arnés visual (BETA1-UX)

Utilidades de verificación para la épica de pulido de UI. **No son tests**
(sin prefijo `test_`); se ejecutan a mano para comparar "antes/después".

## Generar un proyecto demo

```bash
.venv/Scripts/python -m tests.desktop._visual.demo_project ruta/demo.json
```

## Capturar las superficies

```bash
# Capturas FIELES (fuentes/iconos reales). Usa la plataforma real; la ventana
# se monta fuera de pantalla, no molesta.
.venv/Scripts/python -m tests.desktop._visual.capture --out docs/ui_captures --label baseline

# Modo headless/CI (texto en cajas □ — solo sirve para layout/forma/color):
QT_QPA_PLATFORM=offscreen .venv/Scripts/python -m tests.desktop._visual.capture --out docs/ui_captures --label ci
```

Genera `home.png`, `creation_full.png`, `canvas.png` y `panel_nodo.png` en
`<out>/<label>/`.

> **Importante:** la plataforma `offscreen` en Windows **no carga las fuentes del
> sistema** → todo el texto sale en cajas. Para juzgar tipografía/iconos hay que
> capturar con la plataforma real (comportamiento por defecto de `capture`).

## Convención de etiquetas

- `baseline` — estado "antes" de la épica (no tocar).
- `uxNN` — estado tras la tarea UXNN (p. ej. `--label ux03`).
