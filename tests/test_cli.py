import yaml

from nis2_engine.cli import load_answers, load_entity, main
from nis2_engine.models import EntityType


def _write(path, data):
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_load_entity_roundtrip(tmp_path):
    path = _write(
        tmp_path / "entity.yaml",
        {"name": "X", "sector": "energia", "employees": 200, "annual_turnover_eur": 50_000_000},
    )
    entity = load_entity(path)
    assert entity.name == "X"
    assert entity.employees == 200


def test_load_answers_supports_nested_and_flat(tmp_path):
    nested = _write(tmp_path / "a.yaml", {"answers": [{"control_id": "GOV-01", "implemented": True}]})
    flat = _write(tmp_path / "b.yaml", [{"control_id": "GOV-01", "implemented": True}])
    assert load_answers(nested)[0].control_id == "GOV-01"
    assert load_answers(flat)[0].implemented is True


def test_cli_classify_writes_self_identification(tmp_path, capsys):
    entity = _write(
        tmp_path / "entity.yaml",
        {"name": "Energia SA", "sector": "energia", "employees": 200, "annual_turnover_eur": 50_000_000},
    )
    out = tmp_path / "selfid.md"
    rc = main(["classify", str(entity), "-o", str(out)])
    assert rc == 0
    assert out.exists()
    assert "ELEVADO" in out.read_text(encoding="utf-8")


def test_cli_scaffold_then_assess(tmp_path):
    entity = _write(
        tmp_path / "entity.yaml",
        {"name": "Energia SA", "sector": "energia", "employees": 200, "annual_turnover_eur": 50_000_000},
    )
    scaffold = tmp_path / "answers.yaml"
    assert main(["scaffold", str(entity), "-o", str(scaffold)]) == 0
    assert scaffold.exists()

    out_dir = tmp_path / "out"
    assert main(["assess", str(entity), str(scaffold), "-o", str(out_dir)]) == 0
    assert (out_dir / "gap_report.md").exists()
    assert (out_dir / "roadmap.md").exists()
    assert (out_dir / "statement_of_applicability.md").exists()
    assert (out_dir / "self_identification.md").exists()


def test_cli_assess_out_of_scope_returns_error(tmp_path):
    entity = _write(
        tmp_path / "entity.yaml",
        {"name": "Padaria", "sector": "alimentacao", "employees": 5, "annual_turnover_eur": 100_000},
    )
    answers = _write(tmp_path / "answers.yaml", {"answers": []})
    assert main(["assess", str(entity), str(answers), "-o", str(tmp_path / "out")]) == 1


def test_cli_scaffold_out_of_scope_returns_error(tmp_path):
    entity = _write(
        tmp_path / "entity.yaml",
        {"name": "Padaria", "sector": "alimentacao", "employees": 5, "annual_turnover_eur": 100_000},
    )
    assert main(["scaffold", str(entity)]) == 1


def test_cli_policies_writes_all_three_documents(tmp_path):
    entity = _write(
        tmp_path / "entity.yaml",
        {"name": "Energia SA", "sector": "energia", "employees": 200, "annual_turnover_eur": 50_000_000},
    )
    out_dir = tmp_path / "out" / "politicas"
    assert main(["policies", str(entity), "-o", str(out_dir), "--approver", "Maria Silva"]) == 0
    assert (out_dir / "politica_resposta_incidentes.md").exists()
    assert (out_dir / "politica_seguranca_fornecedores.md").exists()
    assert (out_dir / "politica_continuidade_bcdr.md").exists()
    assert "Maria Silva" in (out_dir / "politica_resposta_incidentes.md").read_text(encoding="utf-8")


def test_cli_audit_writes_report(tmp_path):
    out = tmp_path / "audit.md"
    assert main(["audit", "-o", str(out)]) == 0
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "por validar" in content.lower() or "POR_VALIDAR" in content.upper()


def test_cli_assess_with_history_dir_saves_snapshot(tmp_path):
    entity = _write(
        tmp_path / "entity.yaml",
        {"name": "Energia SA", "sector": "energia", "employees": 200, "annual_turnover_eur": 50_000_000},
    )
    scaffold = tmp_path / "answers.yaml"
    assert main(["scaffold", str(entity), "-o", str(scaffold)]) == 0

    history_dir = tmp_path / "history"
    out_dir = tmp_path / "out"
    assert main(["assess", str(entity), str(scaffold), "-o", str(out_dir), "--history-dir", str(history_dir)]) == 0
    assert history_dir.exists()
    assert len(list(history_dir.glob("*.json"))) == 1


def test_cli_progress_requires_at_least_two_snapshots(tmp_path):
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    rc = main(["progress", "Energia SA", "--history-dir", str(history_dir)])
    assert rc == 1


def test_cli_progress_compares_two_assessments(tmp_path):
    entity = _write(
        tmp_path / "entity.yaml",
        {"name": "Energia SA", "sector": "energia", "employees": 200, "annual_turnover_eur": 50_000_000},
    )
    scaffold = tmp_path / "answers.yaml"
    assert main(["scaffold", str(entity), "-o", str(scaffold)]) == 0

    history_dir = tmp_path / "history"
    out_dir = tmp_path / "out"

    assert main(["assess", str(entity), str(scaffold), "-o", str(out_dir), "--history-dir", str(history_dir)]) == 0

    answers = yaml.safe_load(scaffold.read_text(encoding="utf-8"))
    for item in answers["answers"]:
        item["implemented"] = True
        item["maturity"] = 5
    _write(scaffold, answers)

    assert main(["assess", str(entity), str(scaffold), "-o", str(out_dir), "--history-dir", str(history_dir)]) == 0
    assert len(list(history_dir.glob("*.json"))) == 2

    progress_out = tmp_path / "progress.md"
    assert main(["progress", "Energia SA", "--history-dir", str(history_dir), "-o", str(progress_out)]) == 0
    assert progress_out.exists()
    content = progress_out.read_text(encoding="utf-8")
    assert "Relatório de Evolução" in content
