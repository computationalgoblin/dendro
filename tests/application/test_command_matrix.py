"""Deterministic command matrix (Acción × Ámbito).

The command bar no longer classifies free text: two selectors resolve to an
AIJobType verbatim. This locks the matrix from the product spec and the wiring
of the new focused job types (ring template + structured edits).
"""
from __future__ import annotations

import pytest

from packages.application.ai_jobs import (
    ACTION_LABELS,
    COMMAND_MATRIX,
    SCOPE_LABELS,
    AIJobType,
    CommandAction,
    CommandScope,
    _creates_for_intent,
    _expected_output_for_intent,
    job_type_for_command,
    valid_scopes_for_action,
)
from packages.application.ai_request_gateway import INTENT_PARAMS, ModelParams

A = CommandAction
S = CommandScope

# The full product matrix, cell by cell.
EXPECTED_CELLS = {
    (A.CREAR, S.HOJA): AIJobType.GENERATE_ENTITIES,
    (A.CREAR, S.RAMA): AIJobType.GENERATE_TREE,
    (A.CREAR, S.RELACION): AIJobType.SUGGEST_RELATIONS,
    (A.CREAR, S.ANILLO): AIJobType.CREATE_RING_TEMPLATE,
    (A.CREAR, S.HITO): AIJobType.PROPOSE_MILESTONES,
    (A.EDITAR, S.HOJA): AIJobType.EDIT_ENTITIES,
    (A.EDITAR, S.RAMA): AIJobType.EDIT_ENTITIES,
    (A.EDITAR, S.RELACION): AIJobType.EDIT_RELATION,
    (A.EDITAR, S.ANILLO): AIJobType.EDIT_RING,
    (A.EDITAR, S.HITO): AIJobType.EDIT_MILESTONE,
    # Analytical trio: same job type for every scope.
    **{(A.ANALIZAR, s): AIJobType.ANALYZE_COHERENCE for s in S},
    **{(A.EXPLICAR, s): AIJobType.EXPLAIN_FROM_CAUSES for s in S},
    **{(A.EXPANDIR, s): AIJobType.EXPAND_WORLDBUILDING for s in S},
}


@pytest.mark.parametrize("cell,expected", list(EXPECTED_CELLS.items()))
def test_every_cell_resolves_as_specified(cell, expected):
    action, scope = cell
    assert job_type_for_command(action, scope) is expected


def test_matrix_is_complete_5x5():
    assert len(COMMAND_MATRIX) == 25
    assert COMMAND_MATRIX == EXPECTED_CELLS


def test_string_coercion_matches_enum():
    # The UI hands us the enum .value strings.
    assert job_type_for_command("crear", "hoja") is AIJobType.GENERATE_ENTITIES
    assert job_type_for_command("editar", "relacion") is AIJobType.EDIT_RELATION


def test_every_action_offers_all_five_scopes():
    for action in CommandAction:
        scopes = valid_scopes_for_action(action)
        assert scopes == list(CommandScope)


def test_unsupported_combination_raises():
    with pytest.raises(ValueError):
        job_type_for_command("crear", "no-existe")
    with pytest.raises(ValueError):
        job_type_for_command("inventada", "hoja")


def test_labels_cover_all_enum_members():
    assert set(ACTION_LABELS) == set(CommandAction)
    assert set(SCOPE_LABELS) == set(CommandScope)


@pytest.mark.parametrize(
    "intent",
    [
        AIJobType.CREATE_RING_TEMPLATE,
        AIJobType.EDIT_RELATION,
        AIJobType.EDIT_RING,
        AIJobType.EDIT_MILESTONE,
    ],
)
def test_new_job_types_have_gateway_params(intent):
    # Registered explicitly, not falling back to defaults.
    assert intent.value in INTENT_PARAMS
    assert ModelParams.from_intent(intent.value) is INTENT_PARAMS[intent.value]


@pytest.mark.parametrize(
    "intent",
    [
        AIJobType.CREATE_RING_TEMPLATE,
        AIJobType.EDIT_RELATION,
        AIJobType.EDIT_RING,
        AIJobType.EDIT_MILESTONE,
    ],
)
def test_new_job_types_have_plan_metadata(intent):
    # build_job_plan / staging rely on these never being empty.
    assert _creates_for_intent(intent)
    assert _expected_output_for_intent(intent)
