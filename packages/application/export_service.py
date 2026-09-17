"""ExportService — controlled export by audience (gm/player/public). No leak of private info. B26-T01."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from packages.domain.result import Error, Ok, Result

@dataclass
class ExportService:
    project_service: Any; entity_service: Any = None; session_service: Any = None
    secrets_service: Any = None

    def _proj(self): return self.project_service.active_project

    def _filter_entities(self, audience):
        # BETA2-FOCO: los nodos fantasma son borradores internos — jamás exportan,
        # tampoco para el GM (exportar = compartir; el fantasma no es canon pleno).
        entities = [e for e in self._proj().entities if e.canon_state.value != "fantasma"]
        if audience == "public": return [e for e in entities if e.visibility_state.value == "publico_mundo"]
        if audience == "player": return [e for e in entities if e.visibility_state.value not in ("privado_autor", "secreto_mundo")]
        return entities  # gm: all (sin fantasmas)

    def export_public_summary(self, audience="public"):
        entities = self._filter_entities(audience)
        parts = []
        for e in entities:
            parts.append(f"{e.entity_type.value}: {e.name} — {e.brief_description or '(no desc)'}"[:120])
        if audience == "gm":
            parts.append(f"\n[GM ONLY] Secrets: {len(self._proj().secrets)}, Clues: {len(self._proj().clues)}")
            parts.append(f"[GM ONLY] Factions: {len(self._proj().factions)}, Campaigns: {len(self._proj().campaigns)}")
        return Ok("\n".join(parts))

    def export_session_player_summary(self, session_id):
        if self.session_service:
            r = self.session_service.get_session(session_id)
            if isinstance(r, Ok): return Ok(r.value.player_safe_summary or f"Session: {r.value.name}")
        return Error("Session not found")

    def export_campaign_report(self, campaign_id, audience="gm"):
        proj = self._proj()
        camp = None
        for c in proj.campaigns:
            if c.id == campaign_id: camp = c; break
        if camp is None: return Error("Campaign not found")
        parts = [f"Campaign: {camp.name}", f"System: {camp.game_system}", f"Tone: {camp.tone}", f"State: {camp.state.value}"]
        if audience == "gm": parts.append(f"GM Notes: {'; '.join(camp.private_notes) if camp.private_notes else '(none)'}")
        return Ok("\n".join(parts))

    def export_entity_profile(self, entity_id, audience="gm"):
        entity = None
        for e in self._proj().entities:
            if e.id == entity_id: entity = e; break
        if entity is None: return Error("Entity not found")
        if entity.canon_state.value == "fantasma":
            return Error("Entidad fantasma: borrador interno no exportable")
        if audience == "public" and entity.visibility_state.value != "publico_mundo": return Error("Entity not visible to public")
        parts = [f"{entity.entity_type.value}: {entity.name}", f"Description: {entity.brief_description}"]
        if audience == "gm": parts.append(f"Notes: {entity.private_notes or '(none)'}")
        return Ok("\n".join(parts))

    def export_relation_profile(self, rel_id, audience="gm"):
        for r in self._proj().relations:
            if r.id == rel_id: return Ok(f"Relation: {r.source_id} → {r.target_id} ({r.relation_type.value})")
        return Error("Relation not found")

    def export_all(self, audience="gm"):
        entities = self._filter_entities(audience)
        data = {"total_entities": len(entities), "entities": [{"id": e.id, "name": e.name, "type": e.entity_type.value} for e in entities], "total_relations": len(self._proj().relations)}
        return Ok(data)

    # ── BETA-AUDIT-04: exportación a una carpeta de Markdown ────────────────────
    #
    # Los métodos de arriba devuelven texto plano truncado a 120 caracteres y un dict
    # con un CONTADOR de relaciones: sirven para un resumen, no para llevarse el
    # mundo. Y ninguno tenía superficie en la app, así que hasta ahora la única forma
    # de sacar un proyecto era copiar el JSON a mano.
    #
    # El formato es una carpeta con un fichero por entidad y un índice, con
    # front-matter YAML y enlaces `[[wiki]]`: legible en Obsidian/Logseq, diffeable en
    # git y recuperable sin Dendro. El orden es estable (por nombre) para que dos
    # exportaciones del mismo estado den el mismo diff.

    def _nombre_fichero(self, entity, usados: set[str]) -> str:
        base = "".join(
            c if (c.isalnum() or c in " -_") else "-" for c in (entity.name or "sin-nombre")
        ).strip() or "sin-nombre"
        nombre, n = base, 2
        while nombre.lower() in usados:  # dos entidades pueden llamarse igual
            nombre, n = f"{base} ({n})", n + 1
        usados.add(nombre.lower())
        return nombre

    # ── BETA2-FIX-14 (G2-24): la obra entera, no solo el reparto ─────
    #
    # El bundle escribía UNA ficha por entidad y un índice. Un showrunner exportó su
    # biblia de dos temporadas y le salieron 19 fichas de personaje y utilería: fuera
    # los 18 episodios, las dos temporadas, la cronología, la cadena causal y las
    # páginas de wiki que acababa de pagar. «Lo único que hace que esto sea una serie
    # y no un diccionario, fuera.» Las cadenas `causal_milestones`, `eras`,
    # `project_chronology` y `narrative_memories` no aparecían ni una vez.
    #
    # Los tres bloques nuevos se escriben SOLO si tienen contenido: un proyecto sin
    # hitos ni eras ni wiki sigue exportando exactamente lo de antes.

    #: Un hito con visibilidad distinta de esta no se comparte con el público.
    _VISIBILIDAD_PUBLICA_HITO = "visible_usuario"
    #: Visibilidades que nunca salen del escritorio del autor.
    _VISIBILIDAD_RESERVADA = ("privado_autor", "secreto_mundo")

    def _filter_milestones(self, audience) -> list:
        """Hitos exportables para la audiencia, en orden estable (año, título, id).

        Espeja la regla de `_filter_entities`: el GM se lo lleva todo, el jugador
        no ve lo reservado al autor y el público solo ve lo explícitamente visible.
        """
        hitos = list(getattr(self._proj(), "causal_milestones", None) or [])
        if audience == "public":
            hitos = [
                h
                for h in hitos
                if str(getattr(h, "visibility_state", "")) == self._VISIBILIDAD_PUBLICA_HITO
            ]
        elif audience == "player":
            hitos = [
                h
                for h in hitos
                if str(getattr(h, "visibility_state", "")) not in self._VISIBILIDAD_RESERVADA
            ]
        return sorted(
            hitos,
            key=lambda h: (
                getattr(h, "year", None) is None,
                getattr(h, "year", None) or 0,
                (getattr(h, "title", "") or "").lower(),
                h.id,
            ),
        )

    def _filter_memories(self, audience, ids_entidades: set, ids_hitos: set) -> list:
        """Páginas de wiki exportables, en orden estable.

        La página no tiene visibilidad propia: la HEREDA de su objetivo. Si no se
        puede verificar el objetivo (memoria de proyecto, de relación o de anillo)
        solo viaja para el GM: una síntesis editorial puede resumir canon secreto.
        """
        paginas = list(getattr(self._proj(), "narrative_memories", None) or [])

        def _visible(mem) -> bool:
            if audience == "gm":
                return True
            kind = str(getattr(getattr(mem, "target_kind", None), "value", "") or "")
            if kind in ("entity", "branch"):
                return mem.target_id in ids_entidades
            if kind == "milestone":
                return mem.target_id in ids_hitos
            return False

        return sorted(
            (m for m in paginas if _visible(m)),
            key=lambda m: (
                str(getattr(getattr(m, "target_kind", None), "value", "") or ""),
                m.target_id,
                m.context,
                m.id,
            ),
        )

    def _escribir_cronologia(self, destino, proyecto) -> tuple[int, str | None]:
        """`cronologia.md`: eras + calendario + presente. Devuelve (nº eras, error)."""
        crono = getattr(proyecto, "project_chronology", None)
        if crono is None:
            return 0, None
        eras = list(getattr(crono, "eras", None) or [])
        presente = int(getattr(crono, "present_year", 0) or 0)
        calendario = str(getattr(crono, "calendar_name", "") or "")
        if not eras and not presente and not calendario:
            return 0, None  # nada que contar: no se ensucia la carpeta

        ordenadas = (
            crono.sorted_eras()
            if hasattr(crono, "sorted_eras")
            else sorted(eras, key=lambda e: (e.start_year, e.order))
        )
        lineas = [
            "---",
            "tipo: cronologia",
            f"eras: {len(ordenadas)}",
            f"presente: {presente}",
            "---",
            "",
            "# Cronología",
            "",
        ]
        if calendario:
            lineas += [f"Calendario: **{calendario}**", ""]
        sistema = str(getattr(crono, "calendar_system", "") or "")
        if sistema:
            lineas += [f"Sistema: {sistema}", ""]
        etiqueta = (
            crono.year_label(presente) if hasattr(crono, "year_label") else f"año {presente}"
        )
        lineas += [f"Presente del mundo: {etiqueta}", ""]
        if getattr(crono, "description", ""):
            lineas += [crono.description, ""]
        if ordenadas:
            lineas += ["## Eras", ""]
            for era in ordenadas:
                fin = era.end_year
                rango = (
                    f"del año {era.start_year} al {fin}"
                    if fin is not None
                    else f"desde el año {era.start_year} — en curso"
                )
                lineas += [f"### {era.name or '(era sin nombre)'}", "", rango, ""]
                if getattr(era, "description", ""):
                    lineas += [era.description, ""]
        try:
            (destino / "cronologia.md").write_text("\n".join(lineas), encoding="utf-8")
        except OSError as exc:
            return 0, f"No se pudo escribir la cronología: {exc}"
        return len(ordenadas), None

    def _escribir_hitos(self, destino, proyecto, hitos, nombres: dict) -> tuple[int, str | None]:
        """`hitos.md`: año, tipo, participantes y cadena causal. (nº hitos, error)."""
        if not hitos:
            return 0, None
        crono = getattr(proyecto, "project_chronology", None)
        titulos = {h.id: (getattr(h, "title", "") or "(hito sin título)") for h in hitos}
        lineas = [
            "---",
            "tipo: hitos",
            f"total: {len(hitos)}",
            "---",
            "",
            "# Hitos causales",
            "",
        ]
        for hito in hitos:
            anio = getattr(hito, "year", None)
            if crono is not None and hasattr(crono, "year_label"):
                etiqueta = crono.year_label(anio)
            else:
                etiqueta = f"año {anio}" if anio is not None else "sin fecha"
            lineas += [f"## {titulos[hito.id]}", "", f"- Año: {etiqueta}"]
            lineas.append(f"- Tipo: {getattr(hito.milestone_type, 'value', hito.milestone_type)}")
            lineas.append(f"- Estado: {getattr(hito.status, 'value', hito.status)}")
            # Solo se nombran los participantes que TAMBIÉN se exportan: si no,
            # el hito filtraría por la puerta de atrás una entidad no visible.
            participantes = [
                nombres[eid]
                for eid in (getattr(hito, "affected_entity_ids", None) or [])
                if eid in nombres
            ]
            if participantes:
                lineas.append(
                    "- Participantes: " + ", ".join(f"[[{n}]]" for n in sorted(participantes))
                )
            padres = [
                titulos[hid]
                for hid in (getattr(hito, "causal_parent_hito_ids", None) or [])
                if hid in titulos
            ]
            if padres:
                lineas.append("- Causado por: " + "; ".join(sorted(padres)))
            hijos = [
                titulos[hid]
                for hid in (getattr(hito, "causal_child_hito_ids", None) or [])
                if hid in titulos
            ]
            if hijos:
                lineas.append("- Provoca: " + "; ".join(sorted(hijos)))
            lineas.append("")
            if getattr(hito, "description", ""):
                lineas += [hito.description, ""]
        try:
            (destino / "hitos.md").write_text("\n".join(lineas), encoding="utf-8")
        except OSError as exc:
            return 0, f"No se pudo escribir los hitos: {exc}"
        return len(hitos), None

    def _escribir_wiki(self, destino, proyecto, paginas, nombres: dict) -> tuple[int, str | None]:
        """`wiki/`: una página por `NarrativeMemory`. (nº páginas, error).

        Las páginas son DERIVADAS y NO canon: el front-matter lo dice para que
        nadie las confunda con lo escrito por el autor. Los wikilinks del cuerpo
        viajan tal cual (pueden estar rotos: eso es otro ticket).
        """
        if not paginas:
            return 0, None
        carpeta = destino / "wiki"
        try:
            carpeta.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return 0, f"No se pudo crear la carpeta de la wiki: {exc}"

        usados: set[str] = set()
        escritas = 0
        for pagina in paginas:
            kind = str(getattr(getattr(pagina, "target_kind", None), "value", "") or "")
            titulo = nombres.get(pagina.target_id) or self._titulo_de_pagina(proyecto, pagina, kind)
            base = "".join(c if (c.isalnum() or c in " -_") else "-" for c in titulo).strip()
            base = base or "pagina"
            if pagina.context:
                base = f"{base} · {pagina.context}"
            nombre, n = base, 2
            while nombre.lower() in usados:
                nombre, n = f"{base} ({n})", n + 1
            usados.add(nombre.lower())

            lineas = [
                "---",
                f'pagina: "{titulo}"',
                f"id: {pagina.id}",
                f"objetivo: {kind}",
                f"objetivo_id: {pagina.target_id}",
                "canon: false",
                "derivada: true  # síntesis editorial mantenida por la IA, no la escribió el autor",
                f"frescura: {getattr(pagina.freshness, 'value', pagina.freshness)}",
            ]
            if pagina.context:
                lineas.append(f'contexto: "{pagina.context}"')
            if pagina.tags:
                lineas.append("tags: [" + ", ".join(f'"{t}"' for t in pagina.tags) + "]")
            lineas += ["---", "", f"# {titulo}", ""]
            if pagina.resumen_editorial:
                lineas += [pagina.resumen_editorial, ""]
            if pagina.estado_actual:
                lineas += ["## Estado actual", "", pagina.estado_actual, ""]
            if pagina.cuerpo:
                lineas += [pagina.cuerpo, ""]
            if pagina.notas_causales:
                lineas += ["## Notas causales", ""]
                lineas += [f"- {nota}" for nota in pagina.notas_causales]
                lineas.append("")
            enlaces = [
                nombres[cita.ref_id]
                for cita in (pagina.wikilinks or [])
                if getattr(cita, "ref_id", "") in nombres
            ]
            if enlaces:
                lineas += ["## Enlaces", ""]
                lineas += [f"- [[{n}]]" for n in sorted(set(enlaces))]
                lineas.append("")
            try:
                (carpeta / f"{nombre}.md").write_text("\n".join(lineas), encoding="utf-8")
            except OSError as exc:
                return escritas, f"No se pudo escribir la página «{titulo}»: {exc}"
            escritas += 1
        return escritas, None

    def _titulo_de_pagina(self, proyecto, pagina, kind: str) -> str:
        """Nombre legible del objetivo de una página de wiki (o un id de respaldo)."""
        if kind == "project" or not pagina.target_id:
            return f"{getattr(proyecto, 'name', 'Proyecto')} (proyecto)"
        if kind == "milestone":
            for hito in getattr(proyecto, "causal_milestones", None) or []:
                if hito.id == pagina.target_id:
                    return getattr(hito, "title", "") or pagina.target_id
        if kind == "ring":
            for anillo in getattr(proyecto, "world_layers", None) or []:
                if anillo.id == pagina.target_id:
                    return getattr(anillo, "name", "") or pagina.target_id
        return f"{kind or 'pagina'}-{pagina.target_id}"

    def _relaciones_de(self, entity, visibles: dict):
        salientes, entrantes = [], []
        for rel in self._proj().relations:
            tipo = getattr(rel.relation_type, "value", rel.relation_type)
            if rel.source_id == entity.id and rel.target_id in visibles:
                salientes.append((tipo, visibles[rel.target_id], rel.description or ""))
            elif rel.target_id == entity.id and rel.source_id in visibles:
                entrantes.append((tipo, visibles[rel.source_id], rel.description or ""))
        return sorted(salientes), sorted(entrantes)

    def export_markdown_bundle(self, dest_dir, audience="gm") -> Result[dict, str]:
        """Escribe el proyecto como carpeta de Markdown. Devuelve un resumen."""
        from pathlib import Path

        proyecto = self._proj()
        if proyecto is None:
            return Error("No hay proyecto activo que exportar")

        destino = Path(dest_dir)
        try:
            destino.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return Error(f"No se pudo crear la carpeta de destino: {exc}")

        entidades = sorted(self._filter_entities(audience), key=lambda e: (e.name or "").lower())
        usados: set[str] = set()
        nombres = {e.id: self._nombre_fichero(e, usados) for e in entidades}
        anillos = {
            c.id: c.name for c in (getattr(proyecto, "world_layers", None) or [])
        }
        # BETA2-FIX-14 (G2-24): se calculan ANTES del bucle para que cada
        # ficha pueda enlazar los hitos en los que participa (navegable en Obsidian
        # como se navega en Dendro).
        hitos = self._filter_milestones(audience)
        hitos_por_entidad: dict[str, list[str]] = {}
        for hito in hitos:
            titulo = getattr(hito, "title", "") or "(hito sin título)"
            anio = getattr(hito, "year", None)
            etiqueta = f"año {anio} — {titulo}" if anio is not None else f"sin fecha — {titulo}"
            for eid in getattr(hito, "affected_entity_ids", None) or []:
                if eid in nombres:
                    hitos_por_entidad.setdefault(eid, []).append(etiqueta)

        escritos = 0
        for entidad in entidades:
            salientes, entrantes = self._relaciones_de(entidad, nombres)
            anillo = next(
                (anillos[a] for a in (getattr(entidad, "layer_ids", None) or []) if a in anillos),
                "",
            )
            lineas = [
                "---",
                f'nombre: "{entidad.name}"',
                f"id: {entidad.id}",
                f"tipo: {getattr(entidad.entity_type, 'value', entidad.entity_type)}",
                f"canon: {getattr(entidad.canon_state, 'value', entidad.canon_state)}",
                f"visibilidad: {getattr(entidad.visibility_state, 'value', entidad.visibility_state)}",
            ]
            if anillo:
                lineas.append(f'anillo: "{anillo}"')
            alias = list(getattr(entidad, "aliases", None) or [])
            if alias:
                lineas.append("alias: [" + ", ".join(f'"{a}"' for a in alias) + "]")
            lineas += ["---", "", f"# {entidad.name}", ""]
            if entidad.brief_description:
                lineas += [entidad.brief_description, ""]
            if getattr(entidad, "extended_description", ""):
                lineas += [entidad.extended_description, ""]
            if salientes or entrantes:
                lineas.append("## Relaciones")
                lineas.append("")
                for tipo, destino_nombre, desc in salientes:
                    sufijo = f" — {desc}" if desc else ""
                    lineas.append(f"- {tipo} → [[{destino_nombre}]]{sufijo}")
                for tipo, origen_nombre, desc in entrantes:
                    sufijo = f" — {desc}" if desc else ""
                    lineas.append(f"- [[{origen_nombre}]] → {tipo}{sufijo}")
                lineas.append("")
            if hitos_por_entidad.get(entidad.id):
                lineas += ["## Hitos", ""]
                lineas += [f"- {e} · [[hitos]]" for e in hitos_por_entidad[entidad.id]]
                lineas.append("")
            try:
                (destino / f"{nombres[entidad.id]}.md").write_text(
                    "\n".join(lineas), encoding="utf-8"
                )
            except OSError as exc:
                return Error(f"No se pudo escribir «{entidad.name}»: {exc}")
            escritos += 1

        # BETA2-FIX-14 (G2-24): la obra, no solo el reparto.
        n_eras, error = self._escribir_cronologia(destino, proyecto)
        if error:
            return Error(error)
        n_hitos, error = self._escribir_hitos(destino, proyecto, hitos, nombres)
        if error:
            return Error(error)
        paginas = self._filter_memories(audience, set(nombres), {h.id for h in hitos})
        n_wiki, error = self._escribir_wiki(destino, proyecto, paginas, nombres)
        if error:
            return Error(error)

        indice = [f"# {getattr(proyecto, 'name', 'Proyecto')}", ""]
        if getattr(proyecto, "description", ""):
            indice += [proyecto.description, ""]
        indice += [
            f"Exportado desde Dendro · audiencia «{audience}» · {escritos} entidades.",
            "",
        ]
        secciones = []
        if n_eras or (destino / "cronologia.md").exists():
            secciones.append("- [[cronologia]] — eras, calendario y presente del mundo")
        if n_hitos:
            secciones.append(f"- [[hitos]] — {n_hitos} hitos causales")
        if n_wiki:
            secciones.append(f"- `wiki/` — {n_wiki} páginas de wiki (derivadas, no canon)")
        if secciones:
            indice += secciones + [""]
        por_anillo: dict[str, list] = {}
        for entidad in entidades:
            clave = next(
                (anillos[a] for a in (getattr(entidad, "layer_ids", None) or []) if a in anillos),
                "Sin anillo",
            )
            por_anillo.setdefault(clave, []).append(entidad)
        for anillo_nombre in sorted(por_anillo):
            indice += [f"## {anillo_nombre}", ""]
            for entidad in por_anillo[anillo_nombre]:
                tipo = getattr(entidad.entity_type, "value", entidad.entity_type)
                indice.append(f"- [[{nombres[entidad.id]}]] — {tipo}")
            indice.append("")
        try:
            (destino / "index.md").write_text("\n".join(indice), encoding="utf-8")
        except OSError as exc:
            return Error(f"No se pudo escribir el índice: {exc}")

        return Ok(
            {
                "carpeta": str(destino),
                "entidades": escritos,
                "omitidas": len(proyecto.entities) - escritos,
                "audiencia": audience,
                # Claves NUEVAS (FIX-14). Las de arriba se conservan tal cual: hay
                # tests y superficie de UI que las leen.
                "hitos": n_hitos,
                "eras": n_eras,
                "paginas_wiki": n_wiki,
            }
        )
