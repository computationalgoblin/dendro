"""B34-T06 — Enriched tree context for NarrativeContextBuilder.

Validates that _tree_context produces:
- parent_trees: backward-compatible list of names
- ancestors: full chain from immediate parent upward
- siblings: other entities in same parent tree
- children: for containers, their direct child entities
- subtree_trees: for containers, sub-containers inside them
- internal_rules: rules from TreeMeta of parent tree
- external_relations: narrative relations of parent tree
"""

from packages.application.narrative_context_builder import NarrativeContextBuilder
from packages.application.entity_service import EntityService
from packages.application.relation_service import RelationService
from packages.application.tree_meta import TreeMeta
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.project import Project
from packages.domain.result import Ok


class FakeProjectService:
    def __init__(self, project):
        self.active_project = project


def _make_hierarchy():
    """Build: Alta Aristocracia → Hermandad del Acero → Devian, Akshan."""
    project = Project(name="B34-T06 tree context")
    alta = NarrativeEntity(name="Alta Aristocracia", entity_type=EntityType.CONTENEDOR)
    hermandad = NarrativeEntity(name="Hermandad del Acero", entity_type=EntityType.CONTENEDOR)
    devian = NarrativeEntity(name="Devian", entity_type=EntityType.PERSONAJE)
    akshan = NarrativeEntity(name="Akshan", entity_type=EntityType.PERSONAJE)
    brienna = NarrativeEntity(name="Brienna", entity_type=EntityType.PERSONAJE)
    project.entities.extend([alta, hermandad, devian, akshan, brienna])

    rs = RelationService(FakeProjectService(project))
    # alta → contiene → hermandad
    rs.create_relation(alta.id, hermandad.id, "contiene")
    # hermandad → contiene → devian
    rs.create_relation(hermandad.id, devian.id, "contiene")
    # hermandad → contiene → akshan
    rs.create_relation(hermandad.id, akshan.id, "contiene")

    builder = NarrativeContextBuilder(FakeProjectService(project))
    return project, alta, hermandad, devian, akshan, brienna, builder


def test_entity_no_tree_has_empty_context():
    """Entity not in any tree has empty tree_membership."""
    project = Project(name="no-tree")
    devian = NarrativeEntity(name="Devian", entity_type=EntityType.PERSONAJE)
    project.entities.append(devian)
    builder = NarrativeContextBuilder(FakeProjectService(project))

    ctx = builder._tree_context(devian.id)
    assert ctx == {"parent_trees": []}


def test_direct_parent_in_parent_trees():
    """parent_trees contains name of immediate parent."""
    _, _, _, devian, _, _, builder = _make_hierarchy()
    ctx = builder._tree_context(devian.id)
    assert "Hermandad del Acero" in ctx["parent_trees"]


def test_ancestors_chain():
    """Devian has Hermandad as direct parent, Alta as grandparent."""
    _, _, _, devian, _, _, builder = _make_hierarchy()
    ctx = builder._tree_context(devian.id)
    ancestors = ctx.get("ancestors", [])
    assert len(ancestors) == 2
    names = [a["name"] for a in ancestors]
    assert "Hermandad del Acero" in names
    assert "Alta Aristocracia" in names


def test_siblings_in_same_tree():
    """Akshan is sibling of Devian in Hermandad."""
    _, _, _, devian, akshan, _, builder = _make_hierarchy()
    ctx = builder._tree_context(devian.id)
    siblings = ctx.get("siblings", [])
    sibling_names = [s["name"] for s in siblings]
    assert "Akshan" in sibling_names


def test_container_children():
    """Hermandad has Devian and Akshan as children."""
    _, _, hermandad, _, _, _, builder = _make_hierarchy()
    ctx = builder._tree_context(hermandad.id)
    children = ctx.get("children", [])
    child_names = [c["name"] for c in children]
    assert "Devian" in child_names
    assert "Akshan" in child_names


def test_subtree_trees():
    """Alta Aristocracia has Hermandad as subtree (sub-container)."""
    _, alta, _, _, _, _, builder = _make_hierarchy()
    ctx = builder._tree_context(alta.id)
    subtrees = ctx.get("subtree_trees", [])
    assert len(subtrees) == 1
    assert subtrees[0]["name"] == "Hermandad del Acero"


def test_internal_rules_from_parent():
    """Parent tree's internal_rules appear in child's context."""
    project = Project(name="rules-test")
    tree = NarrativeEntity(
        name="Orden Secreta", entity_type=EntityType.CONTENEDOR,
        custom_metadata=TreeMeta(internal_rules=["Solo se entra por invitación", "Traición = muerte"]).merge_into({}),
    )
    member = NarrativeEntity(name="Novato", entity_type=EntityType.PERSONAJE)
    project.entities.extend([tree, member])
    rs = RelationService(FakeProjectService(project))
    rs.create_relation(tree.id, member.id, "contiene")

    builder = NarrativeContextBuilder(FakeProjectService(project))
    ctx = builder._tree_context(member.id)
    rules = ctx.get("internal_rules", [])
    assert "Solo se entra por invitación" in rules
    assert "Traición = muerte" in rules


def test_external_relations_of_parent():
    """Parent tree's narrative relations appear in child's context."""
    project = Project(name="ext-rel-test")
    tree = NarrativeEntity(name="Hermandad", entity_type=EntityType.CONTENEDOR)
    member = NarrativeEntity(name="Devian", entity_type=EntityType.PERSONAJE)
    rival = NarrativeEntity(name="Gremio Oscuro", entity_type=EntityType.CONTENEDOR)
    project.entities.extend([tree, member, rival])
    rs = RelationService(FakeProjectService(project))
    rs.create_relation(tree.id, member.id, "contiene")
    rs.create_relation(tree.id, rival.id, "es_enemigo_de", {"description": "Enemistad antigua"})

    builder = NarrativeContextBuilder(FakeProjectService(project))
    ctx = builder._tree_context(member.id)
    ext_rels = ctx.get("external_relations", [])
    assert len(ext_rels) >= 1
    types = [r["relation_type"] for r in ext_rels]
    assert "es_enemigo_de" in types


def test_build_for_entity_includes_enriched_context():
    """Full build_for_entity includes tree_membership with all fields."""
    _, _, _, devian, _, _, builder = _make_hierarchy()
    context = builder.build_for_entity(devian.id)
    entity_data = context.get("target", {})
    tree = entity_data.get("tree_membership", {})
    assert "parent_trees" in tree
    assert "Hermandad del Acero" in tree["parent_trees"]


def test_backward_compat_parent_trees_is_list():
    """parent_trees is always a list of strings (backward compat)."""
    _, _, _, devian, _, _, builder = _make_hierarchy()
    ctx = builder._tree_context(devian.id)
    assert isinstance(ctx["parent_trees"], list)
    for name in ctx["parent_trees"]:
        assert isinstance(name, str)


def test_no_duplicate_siblings():
    """Siblings should not contain duplicates."""
    _, _, _, devian, _, _, builder = _make_hierarchy()
    ctx = builder._tree_context(devian.id)
    siblings = ctx.get("siblings", [])
    ids = [s["id"] for s in siblings]
    assert len(ids) == len(set(ids))


def test_container_with_no_children():
    """Empty container has no children/subtree_trees keys."""
    project = Project(name="empty-tree")
    tree = NarrativeEntity(name="Vacío", entity_type=EntityType.CONTENEDOR)
    project.entities.append(tree)
    builder = NarrativeContextBuilder(FakeProjectService(project))
    ctx = builder._tree_context(tree.id)
    assert ctx["parent_trees"] == []
    assert "children" not in ctx
    assert "subtree_trees" not in ctx
