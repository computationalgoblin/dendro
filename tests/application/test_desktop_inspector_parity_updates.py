from __future__ import annotations

from packages.application.campaign_service import CampaignService
from packages.application.project_service import ProjectService
from packages.application.session_service import SessionService
from packages.application.faction_service import FactionService
from packages.persistence.store import ProjectStore
from packages.domain.result import Ok


def test_campaign_update_accepts_inspector_parity_fields():
    ps = ProjectService(store=ProjectStore())
    assert isinstance(ps.create("CampaignInspector"), Ok)
    service = CampaignService(project_service=ps)
    created = service.create_campaign({"name": "Old"})
    assert isinstance(created, Ok)
    campaign = created.value

    result = service.update_campaign(campaign.id, {
        "name": "New",
        "description": "desc",
        "world_entity_id": "world-1",
        "game_system": "system",
        "tone": "grim",
        "genre": "fantasy",
        "state": "pausada",
        "players": [{"id": "plr_1", "name": "Ana", "metadata": {"seat": 1}}],
        "player_character_entity_ids": ["pc-1"],
        "session_entity_ids": ["ses-ent-1"],
        "session_ids": ["session-1"],
        "active_plot_entity_ids": ["plot-1"],
        "active_faction_entity_ids": ["faction-ent-1"],
        "active_location_entity_ids": ["loc-1"],
        "secret_entity_ids": ["secret-1"],
        "clue_entity_ids": ["clue-1"],
        "clock_ids": ["clock-1"],
        "private_notes": ["private"],
        "public_summaries": ["summary"],
        "visibility_rules": {"players": "public"},
        "metadata": {"k": "v"},
    })

    assert isinstance(result, Ok)
    updated = result.value
    assert updated.name == "New"
    assert updated.players[0].name == "Ana"
    assert updated.session_ids == ["session-1"]
    assert updated.visibility_rules == {"players": "public"}
    assert updated.metadata == {"k": "v"}


def test_session_update_accepts_inspector_parity_fields():
    ps = ProjectService(store=ProjectStore())
    assert isinstance(ps.create("SessionInspector"), Ok)
    session_service = SessionService(project_service=ps)
    # SessionService validates only if campaign_service is injected.
    created = session_service.create_session({"name": "Old", "campaign_id": "camp-1"})
    assert isinstance(created, Ok)
    session = created.value

    result = session_service.update_session(session.id, {
        "name": "New",
        "campaign_id": "camp-2",
        "entity_id": "entity-session",
        "session_number": 3,
        "real_date": "2026-01-01",
        "internal_date": "Era 1",
        "context_summary": "ctx",
        "gm_objectives": ["gm"],
        "player_known_objectives": ["player"],
        "planned_scenes": [{"name": "Scene", "order": 1}],
        "optional_scenes": [{"name": "Optional", "order": 2}],
        "planned_location_ids": ["loc"],
        "planned_npc_ids": ["npc"],
        "relevant_faction_ids": ["fac"],
        "active_conflict_ids": ["conf"],
        "available_clue_ids": ["clue"],
        "revealable_secret_ids": ["secret"],
        "clock_ids": ["clock"],
        "rumors": ["rumor"],
        "encounters": ["enc"],
        "rewards": ["reward"],
        "complications": ["comp"],
        "expected_consequences": ["cons"],
        "open_questions": ["q"],
        "improvised_material": ["imp"],
        "private_notes": ["private"],
        "player_safe_summary": "safe",
        "continuity_checklist": ["cont"],
        "ia_suggestion_candidate_ids": ["cand"],
        "state": "activa",
        "post_session_summary": "post",
        "source_id": "source",
        "metadata": {"k": "v"},
    })

    assert isinstance(result, Ok)
    updated = result.value
    assert updated.name == "New"
    assert updated.campaign_id == "camp-2"
    assert updated.planned_scenes[0].name == "Scene"
    assert updated.optional_scenes[0].name == "Optional"
    assert updated.metadata == {"k": "v"}


def test_front_update_accepts_stage_inspector_payloads():
    ps = ProjectService(store=ProjectStore())
    assert isinstance(ps.create("FrontInspector"), Ok)
    service = FactionService(project_service=ps)
    created = service.create_front({"name": "Front"})
    assert isinstance(created, Ok)
    front = created.value

    result = service.update_front(front.id, {
        "name": "Front updated",
        "front_type": "amenaza",
        "description": "desc",
        "state": "activo",
        "current_stage_index": 0,
        "advance_conditions": ["advance"],
        "retreat_conditions": ["retreat"],
        "session_ids": ["ses-1"],
        "affected_entity_ids": ["ent-1"],
        "visibility_state": "publico",
        "stages": [{
            "name": "Stage 1",
            "threshold": 2,
            "description": "stage desc",
            "consequences": ["consequence"],
            "conditions": ["condition"],
            "is_terminal": True,
        }],
        "metadata": {"k": "v"},
    })

    assert isinstance(result, Ok)
    updated = result.value
    assert updated.name == "Front updated"
    assert updated.front_type.value == "amenaza"
    assert updated.stages[0].name == "Stage 1"
    assert updated.stages[0].is_terminal is True
    assert updated.metadata == {"k": "v"}
