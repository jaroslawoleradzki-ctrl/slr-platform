import json
from pathlib import Path

from app.domain.publication import Publication
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.normalization_execution_repository import (
    SqliteNormalizationExecutionRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.tools.integrity import run_cli
from tests.fixtures.factories import (
    make_import_history,
    make_normalization_execution,
    make_publication,
)


def test_cli_missing_positional_project_id_returns_exit_code_2(capsys) -> None:
    exit_code = run_cli([])
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "the following arguments are required: PROJECT_ID" in captured.err


def test_cli_healthy_project_returns_exit_code_0(tmp_path: Path, capsys) -> None:
    db_file = tmp_path / "healthy.db"
    project_id = "lean_energy"

    pub_repo = SqliteProjectPublicationRepository(db_file)
    history_repo = SqliteImportHistoryRepository(db_file)
    norm_repo = SqliteNormalizationExecutionRepository(db_file)

    pub = make_publication(index=1, title="Paper 1")
    pub_repo.add_publications(project_id, [pub])

    history = make_import_history(project_id=project_id, records_count=1)
    history_repo.create(history)

    norm = make_normalization_execution(
        project_id=project_id, processed_records=1, clean_records=1
    )
    norm_repo.save(norm)

    exit_code = run_cli([project_id, "-d", str(db_file)])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "SLR Platform — Data Integrity Audit Report" in captured.out
    assert "Audit Status:  OK" in captured.out
    assert "[PASS]" in captured.out


def test_cli_warning_status_returns_exit_code_0(tmp_path: Path, capsys) -> None:
    db_file = tmp_path / "warning.db"
    project_id = "lean_energy"

    pub_repo = SqliteProjectPublicationRepository(db_file)
    history_repo = SqliteImportHistoryRepository(db_file)

    pub = make_publication(index=1, title="Paper 1")
    pub_repo.add_publications(project_id, [pub])

    # Save orphaned decision to generate WARNING status
    from app.domain.duplicate_review import DuplicateDecision
    from app.repositories.duplicate_review_decision_repository import (
        SqliteDuplicateReviewDecisionRepository,
    )
    from tests.fixtures.factories import make_duplicate_decision

    dec_repo = SqliteDuplicateReviewDecisionRepository(db_file)
    dec_repo.save_decision(
        project_id,
        "orphaned-group-999",
        make_duplicate_decision(
            project_id=project_id,
            group_id="orphaned-group-999",
            decision=DuplicateDecision.APPROVE,
        ),
    )

    history = make_import_history(project_id=project_id, records_count=1)
    history_repo.create(history)

    exit_code = run_cli([project_id, "-d", str(db_file)])
    assert exit_code == 0  # WARNING is not fatal error, exit code is 0

    captured = capsys.readouterr()
    assert "Audit Status:  WARNING" in captured.out
    assert "[WARN]" in captured.out
    assert "DEDUP_DECISION_ORPHANED" in captured.out


def test_cli_project_with_error_returns_exit_code_1(tmp_path: Path, capsys) -> None:
    db_file = tmp_path / "error.db"
    project_id = "lean_energy"

    pub_repo = SqliteProjectPublicationRepository(db_file)

    # Add publication without provenance to trigger WC_PROVENANCE_MISSING error
    pub_no_prov = make_publication(index=1, title="No Prov")
    pub_no_prov_dict = pub_no_prov.model_dump()
    pub_no_prov_dict["provenance"] = []

    pub_bad = Publication.model_validate(pub_no_prov_dict)
    pub_repo.add_publications(project_id, [pub_bad])

    exit_code = run_cli([project_id, "-d", str(db_file)])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Audit Status:  ERROR" in captured.out
    assert "[FAIL]" in captured.out
    assert "WC_PROVENANCE_MISSING" in captured.out


def test_cli_non_existent_project_returns_exit_code_1_and_wc_project_not_found(
    tmp_path: Path, capsys
) -> None:
    db_file = tmp_path / "non_existent.db"
    exit_code = run_cli(["non_existent_project", "-d", str(db_file)])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Audit Status:  ERROR" in captured.out
    assert "WC_PROJECT_NOT_FOUND" in captured.out
    assert "Project 'non_existent_project' was not found" in captured.out


def test_cli_json_output_mode(tmp_path: Path, capsys) -> None:
    db_file = tmp_path / "json_test.db"
    project_id = "ai_architecture"

    pub_repo = SqliteProjectPublicationRepository(db_file)
    pub_repo.get_publications(project_id)  # ensure empty project initialized

    exit_code = run_cli([project_id, "-d", str(db_file), "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["project_id"] == "ai_architecture"
    assert data["status"] == "OK"
    assert "checks" in data
    assert data["database_path"] == str(db_file)
