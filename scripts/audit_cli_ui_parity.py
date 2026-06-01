#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI_DIR = ROOT / "packages" / "ui"
SERVICE_DIR = ROOT / "packages" / "application"
UI_CTRL_DIR = ROOT / "hosts" / "DesktopHostPySide" / "controllers"
UI_VIEW_DIR = ROOT / "hosts" / "DesktopHostPySide" / "views"
OUT = ROOT / "docs" / "ui_cli_parity_B27_3.md"


def public_methods(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    methods = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and not child.name.startswith("_"):
                    methods.append((node.name, child.name))
    return methods


def function_names(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]


def extract_cli_commands(path: Path):
    text = path.read_text(encoding="utf-8")
    commands = []
    for match in re.finditer(r'add_parser\("([^"]+)"', text):
        commands.append(match.group(1))
    return sorted(set(commands))


service_methods = {}
for file in sorted(SERVICE_DIR.glob("*_service.py")):
    methods = public_methods(file)
    if methods:
        service_methods[file.stem] = methods

controller_methods = {}
for file in sorted(UI_CTRL_DIR.glob("*.py")):
    methods = public_methods(file)
    if methods:
        controller_methods[file.stem] = methods

view_methods = {}
for file in sorted(UI_VIEW_DIR.glob("*.py")):
    methods = public_methods(file)
    if methods:
        view_methods[file.stem] = methods

cli_files = sorted(CLI_DIR.glob("cli*.py"))
cli_commands = {}
for file in cli_files:
    cmds = extract_cli_commands(file)
    if cmds:
        cli_commands[file.stem] = cmds

rows = []
ui_tokens = "\n".join(
    [
        f"{k}:{','.join(name for _, name in v)}"
        for k, v in {**controller_methods, **view_methods}.items()
    ]
).lower()
service_tokens = "\n".join(
    [f"{k}:{','.join(name for _, name in v)}" for k, v in service_methods.items()]
).lower()

for cli_file, commands in sorted(cli_commands.items()):
    for command in commands:
        cli_key = f"{cli_file}:{command}"
        normalized = command.replace("-", "_")
        matching_services = sorted(
            {
                svc
                for svc, methods in service_methods.items()
                if normalized in svc or any(normalized in method for _, method in methods)
            }
        )
        if not matching_services:
            matching_services = sorted(
                {
                    svc
                    for svc, methods in service_methods.items()
                    if any(command.split("-")[0] in method for _, method in methods)
                }
            )
        ui_screens = sorted(
            {
                view
                for view, methods in view_methods.items()
                if normalized in view or any(normalized in method for _, method in methods)
            }
        )
        ui_actions = sorted(
            {
                f"{ctrl}.{method}"
                for ctrl, methods in controller_methods.items()
                for _, method in methods
                if normalized in method or command.split("-")[0] in method
            }
        )
        if ui_screens and ui_actions:
            status = "complete"
        elif ui_screens or ui_actions:
            status = "partial"
        elif matching_services:
            status = "missing"
        else:
            status = "deferred"
        rows.append((cli_key, ", ".join(matching_services) or "—", ", ".join(ui_screens) or "—", ", ".join(ui_actions) or "—", status))

complete = sum(1 for *_, status in rows if status == "complete")
partial = sum(1 for *_, status in rows if status == "partial")
missing = sum(1 for *_, status in rows if status == "missing")
deferred = sum(1 for *_, status in rows if status == "deferred")

lines = [
    "# UI/CLI Parity Audit B27.3",
    "",
    "Resumen generado automáticamente a partir de packages/ui/cli*.py, packages/application/*_service.py y hosts/DesktopHostPySide/{controllers,views}.",
    "",
    f"- Total comandos CLI detectados: {len(rows)}",
    f"- complete: {complete}",
    f"- partial: {partial}",
    f"- missing: {missing}",
    f"- deferred: {deferred}",
    "",
    "| CLI | Servicio | UI pantalla | UI acción | Estado |",
    "|-----|----------|-------------|-----------|--------|",
]
for cli_key, service, screen, action, status in rows:
    lines.append(f"| {cli_key} | {service} | {screen} | {action} | {status} |")

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(OUT)
