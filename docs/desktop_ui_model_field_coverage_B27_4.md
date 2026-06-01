# B27.4 Desktop UI model-field coverage matrix

Estado: B27.3 NO cerrado. Esta matriz es requisito previo antes de añadir más botones o declarar pantallas completas.

Metodología real usada: introspección de dataclasses de `packages/domain/*` + lectura de `hosts/DesktopHostPySide/views/*` y `controllers/*`. La clasificación es conservadora: si no hay inspector lateral ni edición explícita, no se marca como completa.

## Hallazgos P0 confirmados

- `ImportExportView` está roto: usa `basket.candidates`; el modelo real es `ImportBasket.import_candidates`.
- `ImportExportView` usa campos inventados de `ImportCandidate`: `source_segment_id`, `duplicate_of_entity_ids`, `proposed_payload`; los reales son `segment_id`, `possible_duplicates`, `proposed_data`.
- `CorpusView` todavía usa diálogo/panel mínimo; no existe InspectorPanel lateral derecho. Entity edit actual solo cubre `name` + `brief_description`.
- `CorpusView` detail usa `domain_id`/`layer_id`, pero `NarrativeEntity` tiene `domain`, `layers`, `domain_ids`, `layer_ids`.
- Campaign/Faction/Session/Scene muestran listas mínimas; no exponen el modelo completo ni edición completa.
- El estado `complete` prácticamente no aplica a Desktop UI actual porque no hay patrón común de inspector + save/apply/revert + refresh con selección.

## Leyenda

- `complete`: visible y editable mediante UI real, servicio real, guardado y refresh.
- `visible-only`: se muestra total/parcialmente, pero no es editable o no tiene inspector.
- `missing`: no está expuesto.
- `wrong-field-name`: la UI usa un nombre que no existe en el modelo real.
- `broken`: la pantalla crashea o la fila depende de campo roto.
- `deferred`: no P0 de B27.4, se puede dejar para B28/B29 si no bloquea rol/campaña.

| Modelo | Campo | Visible en UI | Editable en UI | Pantalla | Inspector | Servicio usado | Estado |
| ------ | ----- | ------------- | -------------- | -------- | --------- | -------------- | ------ |
| NarrativeEntity | `id` | Yes | No | `corpus_view.py` | No | `entity_controller` | visible-only |
| NarrativeEntity | `name` | Yes | Yes | `corpus_view.py` | No | `entity_controller` | visible-only |
| NarrativeEntity | `aliases` | No | No | `corpus_view.py` | No | `entity_controller` | missing |
| NarrativeEntity | `entity_type` | Yes | No | `corpus_view.py` | No | `entity_controller` | visible-only |
| NarrativeEntity | `brief_description` | Yes | Yes | `corpus_view.py` | No | `entity_controller` | visible-only |
| NarrativeEntity | `extended_description` | Yes | No | `corpus_view.py` | No | `entity_controller` | visible-only |
| NarrativeEntity | `canon_state` | Yes | No | `corpus_view.py` | No | `entity_controller` | visible-only |
| NarrativeEntity | `visibility_state` | Yes | No | `corpus_view.py` | No | `entity_controller` | visible-only |
| NarrativeEntity | `certainty_level` | No | No | `corpus_view.py` | No | `entity_controller` | missing |
| NarrativeEntity | `tags` | Yes | No | `corpus_view.py` | No | `entity_controller` | visible-only |
| NarrativeEntity | `domain — detail uses domain_id; actual field is domain/domain_ids` | No | No | `corpus_view.py` | No | `entity_controller` | wrong-field-name |
| NarrativeEntity | `layers — detail uses layer_id; actual field is layers/layer_ids` | No | No | `corpus_view.py` | No | `entity_controller` | wrong-field-name |
| NarrativeEntity | `origin` | No | No | `corpus_view.py` | No | `entity_controller` | missing |
| NarrativeEntity | `domain_ids` | No | No | `corpus_view.py` | No | `entity_controller` | missing |
| NarrativeEntity | `layer_ids` | No | No | `corpus_view.py` | No | `entity_controller` | missing |
| NarrativeEntity | `created_at` | No | No | `corpus_view.py` | No | `entity_controller` | missing |
| NarrativeEntity | `updated_at` | No | No | `corpus_view.py` | No | `entity_controller` | missing |
| NarrativeEntity | `private_notes` | No | No | `corpus_view.py` | No | `entity_controller` | missing |
| NarrativeEntity | `exportable_notes` | No | No | `corpus_view.py` | No | `entity_controller` | missing |
| NarrativeEntity | `narrative_importance` | No | No | `corpus_view.py` | No | `entity_controller` | missing |
| NarrativeEntity | `development_level` | No | No | `corpus_view.py` | No | `entity_controller` | missing |
| NarrativeEntity | `custom_metadata` | Yes | No | `corpus_view.py` | No | `entity_controller` | visible-only |
| NarrativeEntity | `custom_type_id` | No | No | `corpus_view.py` | No | `entity_controller` | missing |
| NarrativeEntity | `custom_fields` | No | No | `corpus_view.py` | No | `entity_controller` | missing |
| NarrativeRelation | `id` | Yes | No | `relation_view.py` | No | `relation_controller` | visible-only |
| NarrativeRelation | `source_id` | Yes | No | `relation_view.py` | No | `relation_controller` | visible-only |
| NarrativeRelation | `target_id` | Yes | No | `relation_view.py` | No | `relation_controller` | visible-only |
| NarrativeRelation | `relation_type` | Yes | No | `relation_view.py` | No | `relation_controller` | visible-only |
| NarrativeRelation | `direction` | No | No | `relation_view.py` | No | `relation_controller` | missing |
| NarrativeRelation | `description` | Yes | No | `relation_view.py` | No | `relation_controller` | visible-only |
| NarrativeRelation | `intensity` | No | No | `relation_view.py` | No | `relation_controller` | missing |
| NarrativeRelation | `temporality` | No | No | `relation_view.py` | No | `relation_controller` | missing |
| NarrativeRelation | `causality` | No | No | `relation_view.py` | No | `relation_controller` | missing |
| NarrativeRelation | `canon_state` | Yes | No | `relation_view.py` | No | `relation_controller` | visible-only |
| NarrativeRelation | `visibility_state` | Yes | No | `relation_view.py` | No | `relation_controller` | visible-only |
| NarrativeRelation | `certainty_level` | No | No | `relation_view.py` | No | `relation_controller` | missing |
| NarrativeRelation | `source` | Yes | No | `relation_view.py` | No | `relation_controller` | visible-only |
| NarrativeRelation | `created_at` | No | No | `relation_view.py` | No | `relation_controller` | missing |
| NarrativeRelation | `updated_at` | No | No | `relation_view.py` | No | `relation_controller` | missing |
| NarrativeRelation | `validity_conditions` | No | No | `relation_view.py` | No | `relation_controller` | missing |
| NarrativeRelation | `tags` | No | No | `relation_view.py` | No | `relation_controller` | missing |
| NarrativeRelation | `custom_metadata` | Yes | No | `relation_view.py` | No | `relation_controller` | visible-only |
| NarrativeRelation | `custom_relation_type_id` | No | No | `relation_view.py` | No | `relation_controller` | missing |
| NarrativeRelation | `custom_fields` | No | No | `relation_view.py` | No | `relation_controller` | missing |
| NarrativeRelation | `layer_ids` | No | No | `relation_view.py` | No | `relation_controller` | missing |
| Candidate | `id` | Yes | No | `candidate_view.py` | No | `candidate_controller` | visible-only |
| Candidate | `candidate_type` | Yes | No | `candidate_view.py` | No | `candidate_controller` | visible-only |
| Candidate | `state` | Yes | No | `candidate_view.py` | No | `candidate_controller` | visible-only |
| Candidate | `title` | Yes | No | `candidate_view.py` | No | `candidate_controller` | visible-only |
| Candidate | `proposed_data` | Yes | No | `candidate_view.py` | No | `candidate_controller` | visible-only |
| Candidate | `affected_entity_ids` | No | No | `candidate_view.py` | No | `candidate_controller` | missing |
| Candidate | `affected_relation_ids` | No | No | `candidate_view.py` | No | `candidate_controller` | missing |
| Candidate | `source` | Yes | No | `candidate_view.py` | No | `candidate_controller` | visible-only |
| Candidate | `source_id` | Yes | No | `candidate_view.py` | No | `candidate_controller` | visible-only |
| Candidate | `confidence` | Yes | No | `candidate_view.py` | No | `candidate_controller` | visible-only |
| Candidate | `justification` | No | No | `candidate_view.py` | No | `candidate_controller` | missing |
| Candidate | `expected_impact` | No | No | `candidate_view.py` | No | `candidate_controller` | missing |
| Candidate | `possible_contradictions` | No | No | `candidate_view.py` | No | `candidate_controller` | missing |
| Candidate | `created_at` | No | No | `candidate_view.py` | No | `candidate_controller` | missing |
| Candidate | `reviewed_at` | No | No | `candidate_view.py` | No | `candidate_controller` | missing |
| Candidate | `resolution_note` | No | No | `candidate_view.py` | No | `candidate_controller` | missing |
| Candidate | `final_action` | No | No | `candidate_view.py` | No | `candidate_controller` | missing |
| Candidate | `metadata` | Yes | No | `candidate_view.py` | No | `candidate_controller` | visible-only |
| ImportBasket | `id` | Yes | No | `import_export_view.py` | No | `import_controller` | visible-only |
| ImportBasket | `source_id` | No | No | `import_export_view.py` | No | `import_controller` | missing |
| ImportBasket | `segments` | No | No | `import_export_view.py` | No | `import_controller` | missing |
| ImportBasket | `import_candidates — UI uses basket.candidates instead of basket.import_candidates` | No | No | `import_export_view.py` | No | `import_controller` | wrong-field-name |
| ImportBasket | `review_state` | Yes | No | `import_export_view.py` | No | `import_controller` | visible-only |
| ImportBasket | `created_at` | No | No | `import_export_view.py` | No | `import_controller` | missing |
| ImportBasket | `updated_at` | No | No | `import_export_view.py` | No | `import_controller` | missing |
| ImportBasket | `metadata` | No | No | `import_export_view.py` | No | `import_controller` | missing |
| ImportCandidate | `id` | Yes | No | `import_export_view.py` | No | `import_controller` | visible-only |
| ImportCandidate | `segment_id — UI uses source_segment_id` | No | No | `import_export_view.py` | No | `import_controller` | wrong-field-name |
| ImportCandidate | `candidate_type` | Yes | No | `import_export_view.py` | No | `import_controller` | visible-only |
| ImportCandidate | `proposed_data — UI uses proposed_payload` | No | No | `import_export_view.py` | No | `import_controller` | wrong-field-name |
| ImportCandidate | `proposed_relations` | No | No | `import_export_view.py` | No | `import_controller` | missing |
| ImportCandidate | `confidence` | No | No | `import_export_view.py` | No | `import_controller` | missing |
| ImportCandidate | `possible_duplicates — UI uses duplicate_of_entity_ids` | No | No | `import_export_view.py` | No | `import_controller` | wrong-field-name |
| ImportCandidate | `possible_contradictions` | Yes | No | `import_export_view.py` | No | `import_controller` | visible-only |
| ImportCandidate | `review_state` | Yes | No | `import_export_view.py` | No | `import_controller` | visible-only |
| DocumentSegment | `id` | Yes | No | `import_export_view.py` | No | `import_controller` | visible-only |
| DocumentSegment | `source_id` | No | No | `import_export_view.py` | No | `import_controller` | missing |
| DocumentSegment | `section` | No | No | `import_export_view.py` | No | `import_controller` | missing |
| DocumentSegment | `raw_text` | No | No | `import_export_view.py` | No | `import_controller` | missing |
| DocumentSegment | `start_offset` | No | No | `import_export_view.py` | No | `import_controller` | missing |
| DocumentSegment | `end_offset` | No | No | `import_export_view.py` | No | `import_controller` | missing |
| DocumentSegment | `confidence` | No | No | `import_export_view.py` | No | `import_controller` | missing |
| DocumentSegment | `metadata` | No | No | `import_export_view.py` | No | `import_controller` | missing |
| Campaign | `name` | Yes | No | `campaign_view.py` | No | `campaign_controller` | visible-only |
| Campaign | `id` | Yes | No | `campaign_view.py` | No | `campaign_controller` | visible-only |
| Campaign | `description` | Yes | No | `campaign_view.py` | No | `campaign_controller` | visible-only |
| Campaign | `world_entity_id` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Campaign | `game_system` | Yes | No | `campaign_view.py` | No | `campaign_controller` | visible-only |
| Campaign | `tone` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Campaign | `genre` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Campaign | `state` | Yes | No | `campaign_view.py` | No | `campaign_controller` | visible-only |
| Campaign | `players` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Campaign | `player_character_entity_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Campaign | `session_entity_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Campaign | `session_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Campaign | `active_plot_entity_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Campaign | `active_faction_entity_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Campaign | `active_location_entity_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Campaign | `secret_entity_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Campaign | `clue_entity_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Campaign | `clock_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Campaign | `private_notes` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Campaign | `public_summaries` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Campaign | `visibility_rules` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Campaign | `history` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Campaign | `metadata` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Campaign | `created_at` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Campaign | `updated_at` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| CampaignPlayer | `name` | Yes | No | `campaign_view.py` | No | `campaign_controller` | visible-only |
| CampaignPlayer | `metadata` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| CampaignPlayer | `id` | Yes | No | `campaign_view.py` | No | `campaign_controller` | visible-only |
| PlayerCharacterProfile | `entity_id` | Yes | No | `campaign_view.py` | No | `campaign_controller` | visible-only |
| PlayerCharacterProfile | `player_id` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| PlayerCharacterProfile | `id` | Yes | No | `campaign_view.py` | No | `campaign_controller` | visible-only |
| PlayerCharacterProfile | `objectives` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| PlayerCharacterProfile | `backstory` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| PlayerCharacterProfile | `secret_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| PlayerCharacterProfile | `known_entity_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| PlayerCharacterProfile | `known_secret_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| PlayerCharacterProfile | `known_clue_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| PlayerCharacterProfile | `unknown_entity_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| PlayerCharacterProfile | `unknown_secret_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| PlayerCharacterProfile | `unknown_clue_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| PlayerCharacterProfile | `personal_arc_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| PlayerCharacterProfile | `debt_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| PlayerCharacterProfile | `promise_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| PlayerCharacterProfile | `conflict_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| PlayerCharacterProfile | `current_state` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| PlayerCharacterProfile | `session_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| PlayerCharacterProfile | `metadata` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| PlayerCharacterProfile | `created_at` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| PlayerCharacterProfile | `updated_at` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| CampaignClock | `name` | Yes | No | `campaign_view.py` | No | `campaign_controller` | visible-only |
| CampaignClock | `max_value` | Yes | No | `campaign_view.py` | No | `campaign_controller` | visible-only |
| CampaignClock | `id` | Yes | No | `campaign_view.py` | No | `campaign_controller` | visible-only |
| CampaignClock | `description` | Yes | No | `campaign_view.py` | No | `campaign_controller` | visible-only |
| CampaignClock | `linked_entity_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| CampaignClock | `current_value` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| CampaignClock | `state` | Yes | No | `campaign_view.py` | No | `campaign_controller` | visible-only |
| CampaignClock | `visibility_state` | Yes | No | `campaign_view.py` | No | `campaign_controller` | visible-only |
| CampaignClock | `metadata` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| CampaignClock | `created_at` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| CampaignClock | `updated_at` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| CampaignClock | `faction_id` | Yes | No | `campaign_view.py` | No | `campaign_controller` | visible-only |
| CampaignClock | `front_id` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| CampaignClock | `advance_conditions` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| CampaignClock | `retreat_conditions` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| CampaignClock | `stage_consequences` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| CampaignClock | `session_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| CampaignClock | `affected_entity_ids` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| CampaignClock | `history` | No | No | `campaign_view.py` | No | `campaign_controller` | missing |
| Faction | `entity_id` | Yes | No | `campaign_view.py` | No | `faction_controller` | visible-only |
| Faction | `name` | Yes | No | `campaign_view.py` | No | `faction_controller` | visible-only |
| Faction | `id` | Yes | No | `campaign_view.py` | No | `faction_controller` | visible-only |
| Faction | `objectives` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Faction | `resources` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Faction | `leader_entity_ids` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Faction | `member_entity_ids` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Faction | `ally_faction_ids` | Yes | No | `campaign_view.py` | No | `faction_controller` | visible-only |
| Faction | `enemy_faction_ids` | Yes | No | `campaign_view.py` | No | `faction_controller` | visible-only |
| Faction | `territory_entity_ids` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Faction | `plan_ids` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Faction | `secret_ids` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Faction | `methods` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Faction | `ideology` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Faction | `state` | Yes | No | `campaign_view.py` | No | `faction_controller` | visible-only |
| Faction | `clock_ids` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Faction | `possible_reactions` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Faction | `relation_with_pcs` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Faction | `relation_with_factions` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Faction | `event_ids` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Faction | `inaction_consequences` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Faction | `intervention_consequences` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Faction | `visibility_state` | Yes | No | `campaign_view.py` | No | `faction_controller` | visible-only |
| Faction | `metadata` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Faction | `created_at` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Faction | `updated_at` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Front | `name` | Yes | No | `campaign_view.py` | No | `faction_controller` | visible-only |
| Front | `front_type` | Yes | No | `campaign_view.py` | No | `faction_controller` | visible-only |
| Front | `id` | Yes | No | `campaign_view.py` | No | `faction_controller` | visible-only |
| Front | `description` | Yes | No | `campaign_view.py` | No | `faction_controller` | visible-only |
| Front | `faction_id` | Yes | No | `campaign_view.py` | No | `faction_controller` | visible-only |
| Front | `state` | Yes | No | `campaign_view.py` | No | `faction_controller` | visible-only |
| Front | `stages` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Front | `current_stage_index` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Front | `entity_id` | Yes | No | `campaign_view.py` | No | `faction_controller` | visible-only |
| Front | `clock_id` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Front | `advance_conditions` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Front | `retreat_conditions` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Front | `session_ids` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Front | `affected_entity_ids` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Front | `visibility_state` | Yes | No | `campaign_view.py` | No | `faction_controller` | visible-only |
| Front | `history` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Front | `metadata` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Front | `created_at` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Front | `updated_at` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| FrontStage | `name` | Yes | No | `campaign_view.py` | No | `faction_controller` | visible-only |
| FrontStage | `threshold` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| FrontStage | `description` | Yes | No | `campaign_view.py` | No | `faction_controller` | visible-only |
| FrontStage | `consequences` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| FrontStage | `conditions` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| FrontStage | `is_terminal` | No | No | `campaign_view.py` | No | `faction_controller` | missing |
| Secret/Secreto | `content` | Yes | No | `campaign_view.py` | No | `secrets_controller` | visible-only |
| Secret/Secreto | `id` | Yes | No | `campaign_view.py` | No | `secrets_controller` | visible-only |
| Secret/Secreto | `entity_id` | Yes | No | `campaign_view.py` | No | `secrets_controller` | visible-only |
| Secret/Secreto | `affected_entity_ids` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Secret/Secreto | `revelation_state` | Yes | No | `campaign_view.py` | No | `secrets_controller` | visible-only |
| Secret/Secreto | `who_knows_entity_ids` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Secret/Secreto | `who_suspects_entity_ids` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Secret/Secreto | `who_ignores_entity_ids` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Secret/Secreto | `who_hides_entity_ids` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Secret/Secreto | `associated_clue_ids` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Secret/Secreto | `revelation_consequences` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Secret/Secreto | `concealment_consequences` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Secret/Secreto | `planned_revelation_session_ids` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Secret/Secreto | `actual_revelation_session_id` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Secret/Secreto | `revelation_form` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Secret/Secreto | `importance` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Secret/Secreto | `canon_state` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Secret/Secreto | `visibility_state` | Yes | No | `campaign_view.py` | No | `secrets_controller` | visible-only |
| Secret/Secreto | `metadata` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Secret/Secreto | `created_at` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Secret/Secreto | `updated_at` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Clue/Pista | `content` | Yes | No | `campaign_view.py` | No | `secrets_controller` | visible-only |
| Clue/Pista | `id` | Yes | No | `campaign_view.py` | No | `secrets_controller` | visible-only |
| Clue/Pista | `entity_id` | Yes | No | `campaign_view.py` | No | `secrets_controller` | visible-only |
| Clue/Pista | `associated_secret_id` | Yes | No | `campaign_view.py` | No | `secrets_controller` | visible-only |
| Clue/Pista | `source_entity_id` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Clue/Pista | `location_entity_id` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Clue/Pista | `associated_npc_entity_id` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Clue/Pista | `delivery_form` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Clue/Pista | `delivery_state` | Yes | No | `campaign_view.py` | No | `secrets_controller` | visible-only |
| Clue/Pista | `clarity` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Clue/Pista | `redundancy` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Clue/Pista | `loss_risk` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Clue/Pista | `planned_session_ids` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Clue/Pista | `delivered_session_id` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Clue/Pista | `character_ids_who_know` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Clue/Pista | `probable_interpretation` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Clue/Pista | `possible_misinterpretations` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Clue/Pista | `metadata` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Clue/Pista | `created_at` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Clue/Pista | `updated_at` | No | No | `campaign_view.py` | No | `secrets_controller` | missing |
| Session | `name` | Yes | No | `session_view.py` | No | `session_controller` | visible-only |
| Session | `campaign_id` | Yes | No | `session_view.py` | No | `session_controller` | visible-only |
| Session | `id` | Yes | No | `session_view.py` | No | `session_controller` | visible-only |
| Session | `entity_id` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `session_number` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `real_date` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `internal_date` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `context_summary` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `gm_objectives` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `player_known_objectives` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `planned_scenes` | Yes | No | `session_view.py` | No | `session_controller` | visible-only |
| Session | `optional_scenes` | Yes | No | `session_view.py` | No | `session_controller` | visible-only |
| Session | `planned_location_ids` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `planned_npc_ids` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `relevant_faction_ids` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `active_conflict_ids` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `available_clue_ids` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `revealable_secret_ids` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `clock_ids` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `rumors` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `encounters` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `rewards` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `complications` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `expected_consequences` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `open_questions` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `improvised_material` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `private_notes` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `player_safe_summary` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `continuity_checklist` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `ia_suggestion_candidate_ids` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `state` | Yes | No | `session_view.py` | No | `session_controller` | visible-only |
| Session | `post_session_summary` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `source_id` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `metadata` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `created_at` | No | No | `session_view.py` | No | `session_controller` | missing |
| Session | `updated_at` | No | No | `session_view.py` | No | `session_controller` | missing |
| Scene/SessionScene | `name` | Yes | No | `session_view.py` | No | `session_controller` | visible-only |
| Scene/SessionScene | `id` | Yes | No | `session_view.py` | No | `session_controller` | visible-only |
| Scene/SessionScene | `description` | No | No | `session_view.py` | No | `session_controller` | missing |
| Scene/SessionScene | `scene_type` | Yes | No | `session_view.py` | No | `session_controller` | visible-only |
| Scene/SessionScene | `order` | Yes | No | `session_view.py` | No | `session_controller` | visible-only |
| Scene/SessionScene | `location_id` | No | No | `session_view.py` | No | `session_controller` | missing |
| Scene/SessionScene | `npc_ids` | No | No | `session_view.py` | No | `session_controller` | missing |
| Scene/SessionScene | `notes` | No | No | `session_view.py` | No | `session_controller` | missing |
| Live metadata | `id` | Yes | No | `live_post_view.py` | No | `live_mode_controller` | visible-only |
| Live metadata | `event_type` | No | No | `live_post_view.py` | No | `live_mode_controller` | missing |
| Live metadata | `timestamp` | No | No | `live_post_view.py` | No | `live_mode_controller` | missing |
| Live metadata | `affected_entity_id` | No | No | `live_post_view.py` | No | `live_mode_controller` | missing |
| Live metadata | `affected_relation_id` | No | No | `live_post_view.py` | No | `live_mode_controller` | missing |
| Live metadata | `affected_source_id` | No | No | `live_post_view.py` | No | `live_mode_controller` | missing |
| Live metadata | `previous_value` | No | No | `live_post_view.py` | No | `live_mode_controller` | missing |
| Live metadata | `new_value` | No | No | `live_post_view.py` | No | `live_mode_controller` | missing |
| Live metadata | `change_origin` | No | No | `live_post_view.py` | No | `live_mode_controller` | missing |
| Live metadata | `reason` | No | No | `live_post_view.py` | No | `live_mode_controller` | missing |
| Live metadata | `operation` | No | No | `live_post_view.py` | No | `live_mode_controller` | missing |
| Live metadata | `responsible` | No | No | `live_post_view.py` | No | `live_mode_controller` | missing |
| Live metadata | `reversible` | No | No | `live_post_view.py` | No | `live_mode_controller` | missing |
| Live metadata | `metadata` | No | No | `live_post_view.py` | No | `live_mode_controller` | missing |
| PostSession artifacts | `id` | Yes | No | `live_post_view.py` | No | `post_session_controller` | visible-only |
| PostSession artifacts | `candidate_type` | No | No | `live_post_view.py` | No | `post_session_controller` | missing |
| PostSession artifacts | `state` | Yes | No | `live_post_view.py` | No | `post_session_controller` | visible-only |
| PostSession artifacts | `title` | Yes | No | `live_post_view.py` | No | `post_session_controller` | visible-only |
| PostSession artifacts | `proposed_data` | No | No | `live_post_view.py` | No | `post_session_controller` | missing |
| PostSession artifacts | `affected_entity_ids` | No | No | `live_post_view.py` | No | `post_session_controller` | missing |
| PostSession artifacts | `affected_relation_ids` | No | No | `live_post_view.py` | No | `post_session_controller` | missing |
| PostSession artifacts | `source` | Yes | No | `live_post_view.py` | No | `post_session_controller` | visible-only |
| PostSession artifacts | `source_id` | No | No | `live_post_view.py` | No | `post_session_controller` | missing |
| PostSession artifacts | `confidence` | No | No | `live_post_view.py` | No | `post_session_controller` | missing |
| PostSession artifacts | `justification` | No | No | `live_post_view.py` | No | `post_session_controller` | missing |
| PostSession artifacts | `expected_impact` | No | No | `live_post_view.py` | No | `post_session_controller` | missing |
| PostSession artifacts | `possible_contradictions` | No | No | `live_post_view.py` | No | `post_session_controller` | missing |
| PostSession artifacts | `created_at` | No | No | `live_post_view.py` | No | `post_session_controller` | missing |
| PostSession artifacts | `reviewed_at` | No | No | `live_post_view.py` | No | `post_session_controller` | missing |
| PostSession artifacts | `resolution_note` | No | No | `live_post_view.py` | No | `post_session_controller` | missing |
| PostSession artifacts | `final_action` | No | No | `live_post_view.py` | No | `post_session_controller` | missing |
| PostSession artifacts | `metadata` | No | No | `live_post_view.py` | No | `post_session_controller` | missing |
| WritingUnit | `id` | Yes | No | `writing_view.py` | No | `writing_controller` | visible-only |
| WritingUnit | `name` | No | No | `writing_view.py` | No | `writing_controller` | missing |
| WritingUnit | `unit_type` | Yes | No | `writing_view.py` | No | `writing_controller` | visible-only |
| WritingUnit | `content` | No | No | `writing_view.py` | No | `writing_controller` | missing |
| WritingUnit | `summary` | No | No | `writing_view.py` | No | `writing_controller` | missing |
| WritingUnit | `parent_id` | No | No | `writing_view.py` | No | `writing_controller` | missing |
| WritingUnit | `order` | No | No | `writing_view.py` | No | `writing_controller` | missing |
| WritingUnit | `entity_ids` | No | No | `writing_view.py` | No | `writing_controller` | missing |
| WritingUnit | `framework_ids` | No | No | `writing_view.py` | No | `writing_controller` | missing |
| WritingUnit | `domain_ids` | No | No | `writing_view.py` | No | `writing_controller` | missing |
| WritingUnit | `layer_ids` | No | No | `writing_view.py` | No | `writing_controller` | missing |
| WritingUnit | `timeline_event_ids` | No | No | `writing_view.py` | No | `writing_controller` | missing |
| WritingUnit | `source_ids` | No | No | `writing_view.py` | No | `writing_controller` | missing |
| WritingUnit | `revision_state` | Yes | No | `writing_view.py` | No | `writing_controller` | visible-only |
| WritingUnit | `author_notes` | No | No | `writing_view.py` | No | `writing_controller` | missing |
| WritingUnit | `canon_state` | No | No | `writing_view.py` | No | `writing_controller` | missing |
| WritingUnit | `visibility_state` | No | No | `writing_view.py` | No | `writing_controller` | missing |
| WritingUnit | `tags` | No | No | `writing_view.py` | No | `writing_controller` | missing |
| WritingUnit | `metadata` | No | No | `writing_view.py` | No | `writing_controller` | missing |
| WritingUnit | `created_at` | No | No | `writing_view.py` | No | `writing_controller` | missing |
| WritingUnit | `updated_at` | No | No | `writing_view.py` | No | `writing_controller` | missing |
| StructuredIssue | `id` | Yes | No | `issues_history_view.py` | No | `issue_controller` | visible-only |
| StructuredIssue | `type` | Yes | No | `issues_history_view.py` | No | `issue_controller` | visible-only |
| StructuredIssue | `severity` | Yes | No | `issues_history_view.py` | No | `issue_controller` | visible-only |
| StructuredIssue | `state` | No | No | `issues_history_view.py` | No | `issue_controller` | missing |
| StructuredIssue | `affected_entity_ids` | Yes | No | `issues_history_view.py` | No | `issue_controller` | visible-only |
| StructuredIssue | `affected_relation_ids` | No | No | `issues_history_view.py` | No | `issue_controller` | missing |
| StructuredIssue | `affected_source_ids` | No | No | `issues_history_view.py` | No | `issue_controller` | missing |
| StructuredIssue | `description` | Yes | No | `issues_history_view.py` | No | `issue_controller` | visible-only |
| StructuredIssue | `evidence` | No | No | `issues_history_view.py` | No | `issue_controller` | missing |
| StructuredIssue | `possible_solutions` | No | No | `issues_history_view.py` | No | `issue_controller` | missing |
| StructuredIssue | `detected_at` | No | No | `issues_history_view.py` | No | `issue_controller` | missing |
| StructuredIssue | `reviewed_at` | No | No | `issues_history_view.py` | No | `issue_controller` | missing |
| StructuredIssue | `resolution` | No | No | `issues_history_view.py` | No | `issue_controller` | missing |
| StructuredIssue | `is_intentional` | No | No | `issues_history_view.py` | No | `issue_controller` | missing |
| StructuredIssue | `metadata` | No | No | `issues_history_view.py` | No | `issue_controller` | missing |
| Source | `id` | Yes | No | `source_view.py` | No | `source_controller` | visible-only |
| Source | `source_type` | Yes | No | `source_view.py` | No | `source_controller` | visible-only |
| Source | `name` | No | No | `source_view.py` | No | `source_controller` | missing |
| Source | `description` | No | No | `source_view.py` | No | `source_controller` | missing |
| Source | `reference` | No | No | `source_view.py` | No | `source_controller` | missing |
| Source | `fragment` | No | No | `source_view.py` | No | `source_controller` | missing |
| Source | `incorporated_at` | No | No | `source_view.py` | No | `source_controller` | missing |
| Source | `state` | No | No | `source_view.py` | No | `source_controller` | missing |
| Source | `metadata` | No | No | `source_view.py` | No | `source_controller` | missing |
| Source | `derived_entity_ids` | No | No | `source_view.py` | No | `source_controller` | missing |
| Source | `derived_relation_ids` | No | No | `source_view.py` | No | `source_controller` | missing |
| TimelineEvent | `id` | Yes | No | `timeline_view.py` | No | `timeline_controller` | visible-only |
| TimelineEvent | `name` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |
| TimelineEvent | `description` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |
| TimelineEvent | `entity_id` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |
| TimelineEvent | `temporality` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |
| TimelineEvent | `domain_ids` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |
| TimelineEvent | `layer_ids` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |
| TimelineEvent | `participant_ids` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |
| TimelineEvent | `location_id` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |
| TimelineEvent | `cause_ids` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |
| TimelineEvent | `consequence_ids` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |
| TimelineEvent | `source_ids` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |
| TimelineEvent | `canon_state` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |
| TimelineEvent | `visibility_state` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |
| TimelineEvent | `session_ids` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |
| TimelineEvent | `faction_ids` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |
| TimelineEvent | `secret_ids` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |
| TimelineEvent | `clue_ids` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |
| TimelineEvent | `metadata` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |
| TimelineEvent | `created_at` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |
| TimelineEvent | `updated_at` | No | No | `timeline_view.py` | No | `timeline_controller` | missing |

## Cobertura actual resumida por modelo

- NarrativeEntity: missing: 13, visible-only: 9, wrong-field-name: 2
- NarrativeRelation: missing: 12, visible-only: 9
- Candidate: missing: 9, visible-only: 9
- ImportBasket: missing: 5, visible-only: 2, wrong-field-name: 1
- ImportCandidate: missing: 2, visible-only: 4, wrong-field-name: 3
- DocumentSegment: missing: 7, visible-only: 1
- Campaign: missing: 20, visible-only: 5
- CampaignPlayer: missing: 1, visible-only: 2
- PlayerCharacterProfile: missing: 19, visible-only: 2
- CampaignClock: missing: 12, visible-only: 7
- Faction: missing: 19, visible-only: 7
- Front: missing: 11, visible-only: 8
- FrontStage: missing: 4, visible-only: 2
- Secret/Secreto: missing: 16, visible-only: 5
- Clue/Pista: missing: 15, visible-only: 5
- Session: missing: 30, visible-only: 6
- Scene/SessionScene: missing: 4, visible-only: 4
- Live metadata: missing: 13, visible-only: 1
- PostSession artifacts: missing: 14, visible-only: 4
- WritingUnit: missing: 18, visible-only: 3
- StructuredIssue: missing: 10, visible-only: 5
- Source: missing: 9, visible-only: 2
- TimelineEvent: missing: 20, visible-only: 1

## Tickets propuestos para revisión del usuario

No implementar hasta que el usuario apruebe explícitamente estos tickets o una variante corregida.

### B27.4-T01 — UI shell InspectorPanel común + error handling
- Prioridad: P0
- Perfil: UI Agent
- Objetivo: introducir layout estándar Sidebar/Centro/Inspector derecho/LogPanel/Topbar y patrón común `InspectorPanel` reutilizable, sin escribir persistencia desde views.
- Criterios: selección conserva ID; copy ID; save/apply/revert; refresh sin perder selección; excepciones a LogPanel/QMessageBox.

### B27.4-T02 — Import UI field-name fix + import candidate inspector
- Prioridad: P0
- Objetivo: sustituir `basket.candidates` por `basket.import_candidates`, eliminar campos inventados y exponer Basket/Segment/ImportCandidate reales.
- Tests: test/smoke de `_rows()` con `ImportBasket(import_candidates=[...])`; no traceback.

### B27.4-T03 — AI provider real OpenCode Zen en Desktop UI
- Prioridad: P0
- Objetivo: Desktop UI usa la misma factory/OrchestratorService que CLI, topbar saneada, Test AI Provider, error real sin API key.
- Criterios: con `NARRATIVE_AI_PROVIDER=openai_compatible` no muestra simulated salvo fallback explícito con reason.

### B27.4-T04 — Entity Inspector model-complete
- Prioridad: P0
- Objetivo: inspector lateral de NarrativeEntity con campos principales reales, relaciones entrantes/salientes, candidates, issues, history, fuentes y vínculos narrativos.
- Criterios: no abrir pestaña/dialog por entidad; edit de más que descripción; usa `EntityService`/servicios asociados.

### B27.4-T05 — Campaign Inspector/create/edit completo
- Prioridad: P0
- Objetivo: formulario completo para `Campaign`, players, PCs, plots, factions, locations, secrets/clues, clocks, notes, summaries, visibility rules, sessions.

### B27.4-T06 — Faction/Front/Stage Inspector
- Prioridad: P0
- Objetivo: entidades FACCION pendientes de extensión, creación de `Faction`, objetivos, leaders/members, allies/enemies, fronts, stages y clocks.

### B27.4-T07 — Session/Scene full inspector/editor
- Prioridad: P0
- Objetivo: editar campos principales de `Session` y `SessionScene`, links a entidades/pistas/secretos/facciones/clocks, reorder, issues y suggest material.

### B27.4-T08 — Candidate/notes/NPC inspector completeness
- Prioridad: P1
- Objetivo: Candidate full inspector/edit, notas editables, NPC subtype completeness y errores en LogPanel.

### B27.4-T09 — Issues/Writing/Export inspector parity
- Prioridad: P1
- Objetivo: Issues detail/resolve, WritingUnit inspector completo, export no-leak UI.

### B27.4-T10 — Timeline/Framework/Sources/Layers parity
- Prioridad: P2
- Objetivo: completar pantallas no bloqueantes para campaña/rol tras P0/P1.

