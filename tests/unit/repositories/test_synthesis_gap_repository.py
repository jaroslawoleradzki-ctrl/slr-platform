"""Unit tests for SqliteSynthesisGapRepository (Task 10.6)."""

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.synthesis import ResearchGapType
from app.repositories.synthesis_gap_repository import SqliteSynthesisGapRepository


@pytest.fixture
def repo(tmp_path: Path):
    migrations_dir = Path(__file__).parents[3] / "migrations"
    db_path = tmp_path / "test_gap_repo.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    for sql_file in sorted(migrations_dir.glob("*.sql")):
        conn.executescript(sql_file.read_text(encoding="utf-8"))
    conn.commit()

    proj_id = "test-proj-gap-repo"
    rel_id = str(uuid4())
    group_item_id = str(uuid4())
    pub_id = str(uuid4())
    rev_id = str(uuid4())
    conn.execute(
        "INSERT INTO projects (project_id, title, description) VALUES (?, ?, ?);",
        (proj_id, "Test Project", "Desc"),
    )
    conn.execute(
        """
        INSERT INTO synthesis_analytical_relations (
            relation_id, project_id, publication_id, latest_revision_id, group_item_id,
            item_index, source_practice, source_effect, direction, evidence_character, approval_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            rel_id,
            proj_id,
            pub_id,
            rev_id,
            group_item_id,
            1,
            "5S Practice",
            "Energy effect",
            "positive",
            "empirical",
            "approved",
        ),
    )
    pathway_id = str(uuid4())
    conn.execute(
        "INSERT INTO synthesis_mechanism_categories (project_id, category_id, name) VALUES (?, ?, ?);",
        (proj_id, "idle_reduction", "Idle Reduction"),
    )
    conn.execute(
        """
        INSERT INTO synthesis_mechanism_pathways (
            pathway_id, project_id, analytical_relation_id, group_item_id, publication_id,
            latest_revision_id, source_mechanism_text, analytical_mechanism_category_id, approval_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            pathway_id,
            proj_id,
            rel_id,
            group_item_id,
            pub_id,
            rev_id,
            "Turned off conveyors during changeovers.",
            "idle_reduction",
            "approved",
        ),
    )
    conn.execute(
        "INSERT INTO synthesis_context_categories (project_id, category_id, name) VALUES (?, ?, ?);",
        (proj_id, "org_factors", "Organizational Factors"),
    )
    context_link_id = str(uuid4())
    conn.execute(
        """
        INSERT INTO synthesis_relation_context_links (
            link_id, project_id, analytical_relation_id, group_item_id, publication_id,
            latest_revision_id, source_context_text, analytical_context_category_id, context_impact, approval_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            context_link_id,
            proj_id,
            rel_id,
            group_item_id,
            pub_id,
            rev_id,
            "Plant size moderated outcomes.",
            "org_factors",
            "STRENGTHEN",
            "approved",
        ),
    )
    conn.commit()
    conn.close()

    return (
        SqliteSynthesisGapRepository(db_path),
        proj_id,
        rel_id,
        group_item_id,
        pathway_id,
        context_link_id,
        pub_id,
        rev_id,
    )


def _create_gap(repository, project_id, gap_type="thematic", gap_id=None):
    gap_id = gap_id or str(uuid4())
    return repository.create_gap(
        gap_id=gap_id,
        project_id=project_id,
        gap_type=gap_type,
        title="Under-studied combination",
        rationale="Only one eligible source covers this combination; publication count alone is not proof.",
        researcher_id="researcher-1",
    )


def test_create_and_get_gap(repo):
    repository, proj_id, *_ = repo
    created = _create_gap(repository, proj_id)
    assert created["gap_id"] is not None
    assert created["project_id"] == proj_id

    fetched = repository.get_gap(proj_id, created["gap_id"])
    assert fetched is not None
    assert fetched["title"] == "Under-studied combination"
    assert fetched["rationale"] == (
        "Only one eligible source covers this combination; publication count alone is not proof."
    )
    assert fetched["researcher_id"] == "researcher-1"
    assert fetched["created_at"].tzinfo is not None
    assert fetched["updated_at"].tzinfo is not None


def test_all_five_gap_types_persisted(repo):
    repository, proj_id, *_ = repo
    for gap_type in list(ResearchGapType):
        gap_id = str(uuid4())
        repository.create_gap(
            gap_id=gap_id,
            project_id=proj_id,
            gap_type=gap_type.value,
            title=f"Gap for {gap_type.value}",
            rationale="Researcher justification.",
            researcher_id="researcher-1",
        )
        fetched = repository.get_gap(proj_id, gap_id)
        assert fetched is not None
        assert fetched["gap_type"] == gap_type.value


def test_list_gaps_deterministic_order(repo):
    repository, proj_id, *_ = repo
    ids = []
    for i in range(3):
        gap_id = str(uuid4())
        repository.create_gap(
            gap_id=gap_id,
            project_id=proj_id,
            gap_type="methodological",
            title=f"Gap {i}",
            rationale="Justification.",
            researcher_id="researcher-1",
        )
        ids.append(gap_id)

    listed = repository.list_gaps(proj_id)
    assert [g["gap_id"] for g in listed] == ids


def test_list_gaps_by_type(repo):
    repository, proj_id, *_ = repo
    thematic_id = str(uuid4())
    mechanism_id = str(uuid4())
    repository.create_gap(
        gap_id=thematic_id, project_id=proj_id, gap_type="thematic",
        title="Thematic", rationale="R", researcher_id="r",
    )
    repository.create_gap(
        gap_id=mechanism_id, project_id=proj_id, gap_type="mechanism",
        title="Mechanism", rationale="R", researcher_id="r",
    )

    thematic = repository.list_gaps_by_type(proj_id, "thematic")
    assert [g["gap_id"] for g in thematic] == [thematic_id]
    assert repository.list_gaps_by_type(proj_id, "contextual") == []


def test_update_gap(repo):
    repository, proj_id, *_ = repo
    gap_id = str(uuid4())
    repository.create_gap(
        gap_id=gap_id, project_id=proj_id, gap_type="contextual",
        title="Old title", rationale="Old rationale", researcher_id="r",
    )

    updated = repository.update_gap(
        proj_id, gap_id, gap_type="methodological", title="New title", rationale="New rationale"
    )
    assert updated is not None
    assert updated["gap_type"] == "methodological"
    assert updated["title"] == "New title"
    assert updated["rationale"] == "New rationale"


def test_update_gap_missing_returns_none(repo):
    repository, proj_id, *_ = repo
    assert repository.update_gap(proj_id, str(uuid4()), title="X") is None


def test_project_isolation(repo):
    repository, proj_id, *_ = repo
    created = _create_gap(repository, proj_id)

    assert repository.get_gap("other-project", created["gap_id"]) is None
    assert repository.list_gaps("other-project") == []
    assert repository.count_by_type("other-project") == {}


def test_create_gap_rejects_missing_project(repo):
    repository, *_ = repo
    with pytest.raises(sqlite3.IntegrityError):
        _create_gap(repository, "does-not-exist")


def test_link_lifecycle(repo):
    repository, proj_id, rel_id, group_item_id, pathway_id, context_link_id, pub_id, rev_id = repo
    gap_id = str(uuid4())
    _create_gap(repository, proj_id, gap_id=gap_id)

    link_id = str(uuid4())
    link = repository.add_link(
        link_id=link_id,
        project_id=proj_id,
        gap_id=gap_id,
        link_type="analytical_relation",
        target_id=rel_id,
        group_item_id=group_item_id,
        publication_id=pub_id,
        latest_revision_id=rev_id,
    )
    assert link["link_id"] == link_id
    assert link["link_type"] == "analytical_relation"
    assert link["target_id"] == rel_id

    by_target = repository.get_link_by_gap_target(proj_id, gap_id, "analytical_relation", rel_id)
    assert by_target is not None

    links = repository.list_links_for_gap(proj_id, gap_id)
    assert len(links) == 1
    assert links[0]["target_id"] == rel_id

    assert repository.remove_link(link_id) is True
    assert repository.list_links_for_gap(proj_id, gap_id) == []


def test_link_idempotent_no_duplicates(repo):
    repository, proj_id, rel_id, group_item_id, pathway_id, context_link_id, pub_id, rev_id = repo
    gap_id = str(uuid4())
    _create_gap(repository, proj_id, gap_id=gap_id)

    repository.add_link(
        link_id=str(uuid4()), project_id=proj_id, gap_id=gap_id, link_type="mechanism_pathway",
        target_id=pathway_id, group_item_id=group_item_id, publication_id=pub_id, latest_revision_id=rev_id,
    )
    repository.add_link(
        link_id=str(uuid4()), project_id=proj_id, gap_id=gap_id, link_type="mechanism_pathway",
        target_id=pathway_id, group_item_id=group_item_id, publication_id=pub_id, latest_revision_id=rev_id,
    )

    links = repository.list_links_for_gap(proj_id, gap_id)
    assert len(links) == 1


def test_link_requires_existing_gap(repo):
    repository, proj_id, rel_id, group_item_id, *_ = repo
    with pytest.raises(sqlite3.IntegrityError):
        repository.add_link(
            link_id=str(uuid4()), project_id=proj_id, gap_id=str(uuid4()),
            link_type="analytical_relation", target_id=rel_id,
            group_item_id=group_item_id, publication_id=str(uuid4()), latest_revision_id=str(uuid4()),
        )


def test_link_cross_project_gap_rejected(repo):
    repository, proj_id, rel_id, group_item_id, *_ = repo
    other_gap_id = str(uuid4())
    conn = sqlite3.connect(repository.db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(
        "INSERT INTO projects (project_id, title, description) VALUES (?, ?, ?);",
        ("other-project", "Other", "Desc"),
    )
    conn.execute(
        "INSERT INTO synthesis_research_gaps (project_id, gap_id, gap_type, title, rationale, researcher_id)"
        " VALUES (?, ?, 'thematic', 'T', 'R', 'r');",
        ("other-project", other_gap_id),
    )
    conn.commit()
    conn.close()

    with pytest.raises(sqlite3.IntegrityError):
        repository.add_link(
            link_id=str(uuid4()), project_id=proj_id, gap_id=other_gap_id,
            link_type="analytical_relation", target_id=rel_id,
            group_item_id=group_item_id, publication_id=str(uuid4()), latest_revision_id=str(uuid4()),
        )


def test_delete_gap_removes_links_but_keeps_source_evidence(repo):
    repository, proj_id, rel_id, group_item_id, pathway_id, context_link_id, pub_id, rev_id = repo
    gap_id = str(uuid4())
    _create_gap(repository, proj_id, gap_id=gap_id)

    repository.add_link(
        link_id=str(uuid4()), project_id=proj_id, gap_id=gap_id, link_type="analytical_relation",
        target_id=rel_id, group_item_id=group_item_id, publication_id=pub_id, latest_revision_id=rev_id,
    )
    repository.add_link(
        link_id=str(uuid4()), project_id=proj_id, gap_id=gap_id, link_type="mechanism_pathway",
        target_id=pathway_id, group_item_id=group_item_id, publication_id=pub_id, latest_revision_id=rev_id,
    )
    repository.add_link(
        link_id=str(uuid4()), project_id=proj_id, gap_id=gap_id, link_type="context_factor_link",
        target_id=context_link_id, group_item_id=group_item_id, publication_id=pub_id, latest_revision_id=rev_id,
    )
    assert len(repository.list_links_for_gap(proj_id, gap_id)) == 3

    deleted = repository.delete_gap(proj_id, gap_id)
    assert deleted is True

    assert repository.get_gap(proj_id, gap_id) is None
    assert repository.list_links_for_gap(proj_id, gap_id) == []

    conn = sqlite3.connect(repository.db_path)
    try:
        rel_count = conn.execute(
            "SELECT COUNT(*) FROM synthesis_analytical_relations WHERE relation_id = ?;", (rel_id,)
        ).fetchone()[0]
        pathway_count = conn.execute(
            "SELECT COUNT(*) FROM synthesis_mechanism_pathways WHERE pathway_id = ?;", (pathway_id,)
        ).fetchone()[0]
        context_count = conn.execute(
            "SELECT COUNT(*) FROM synthesis_relation_context_links WHERE link_id = ?;", (context_link_id,)
        ).fetchone()[0]
        assert rel_count == 1
        assert pathway_count == 1
        assert context_count == 1
    finally:
        conn.close()


def test_count_by_type(repo):
    repository, proj_id, *_ = repo
    _create_gap(repository, proj_id, gap_type="thematic")
    _create_gap(repository, proj_id, gap_type="thematic")
    _create_gap(repository, proj_id, gap_type="inconsistent_evidence")

    counts = repository.count_by_type(proj_id)
    assert counts["thematic"] == 2
    assert counts["inconsistent_evidence"] == 1
    assert counts.get("mechanism", 0) == 0


def test_delete_for_project(repo):
    repository, proj_id, rel_id, group_item_id, *_ = repo
    gap_id = str(uuid4())
    _create_gap(repository, proj_id, gap_id=gap_id)
    repository.add_link(
        link_id=str(uuid4()), project_id=proj_id, gap_id=gap_id, link_type="analytical_relation",
        target_id=rel_id, group_item_id=group_item_id, publication_id=str(uuid4()), latest_revision_id=str(uuid4()),
    )

    repository.delete_for_project(proj_id)

    assert repository.list_gaps(proj_id) == []
    assert repository.list_links_for_gap(proj_id, gap_id) == []
