from nis2_engine.history import build_snapshot, compare_snapshots, load_snapshots, save_snapshot
from nis2_engine.models import (
    AssessmentResult,
    ComplianceLevel,
    Control,
    Entity,
    GapItem,
)


def _control(control_id: str, qnrcs_function: str = "Identificar") -> Control:
    return Control(
        id=control_id,
        title=f"Controlo {control_id}",
        qnrcs_function=qnrcs_function,
        levels={"basico": True, "substancial": True, "elevado": True},
        evidence_type="documento",
    )


def _entity() -> Entity:
    return Entity(name="Energia SA", sector="energia", employees=200, annual_turnover_eur=50_000_000)


def _result(gaps: list[GapItem]) -> AssessmentResult:
    return AssessmentResult(
        entity=_entity(),
        target_level=ComplianceLevel.ELEVADO,
        score_pct=50.0,
        gaps=gaps,
        not_applicable=[],
        maturity_score_pct=40.0,
        maturity_by_function={"Identificar": 2.0, "Proteger": 1.0},
    )


def test_build_snapshot_captures_control_status():
    gaps = [
        GapItem(control=_control("GOV-01"), implemented=True, priority="alta", maturity=5),
        GapItem(control=_control("PROT-01", "Proteger"), implemented=False, priority="media", maturity=1),
    ]
    snapshot = build_snapshot(_result(gaps), generated_at="2026-01-01T00:00:00")
    assert snapshot.entity_name == "Energia SA"
    assert snapshot.control_status["GOV-01"] == {"implemented": True, "maturity": 5, "priority": "alta"}
    assert snapshot.maturity_by_function == {"Identificar": 2.0, "Proteger": 1.0}


def test_save_and_load_snapshots_roundtrip(tmp_path):
    gaps = [GapItem(control=_control("GOV-01"), implemented=True, priority="alta", maturity=5)]
    snapshot = build_snapshot(_result(gaps), generated_at="2026-01-01T00:00:00")
    save_snapshot(snapshot, tmp_path)

    loaded = load_snapshots(tmp_path, "Energia SA")
    assert len(loaded) == 1
    assert loaded[0].entity_name == "Energia SA"
    assert loaded[0].control_status["GOV-01"]["implemented"] is True


def test_load_snapshots_returns_empty_for_missing_dir(tmp_path):
    assert load_snapshots(tmp_path / "nope", "Energia SA") == []


def test_load_snapshots_sorted_chronologically(tmp_path):
    early = build_snapshot(_result([]), generated_at="2026-01-01T00:00:00")
    late = build_snapshot(_result([]), generated_at="2026-02-01T00:00:00")
    save_snapshot(late, tmp_path)
    save_snapshot(early, tmp_path)

    loaded = load_snapshots(tmp_path, "Energia SA")
    assert [s.generated_at for s in loaded] == ["2026-01-01T00:00:00", "2026-02-01T00:00:00"]


def test_compare_snapshots_detects_progress_and_regression():
    old_gaps = [
        GapItem(control=_control("GOV-01"), implemented=False, priority="alta", maturity=0),
        GapItem(control=_control("PROT-01", "Proteger"), implemented=True, priority="media", maturity=5),
    ]
    new_gaps = [
        GapItem(control=_control("GOV-01"), implemented=True, priority="alta", maturity=5),
        GapItem(control=_control("PROT-01", "Proteger"), implemented=False, priority="media", maturity=0),
    ]
    old = build_snapshot(_result(old_gaps), generated_at="2026-01-01T00:00:00")
    old.score_pct = 30.0
    old.maturity_score_pct = 25.0
    new = build_snapshot(_result(new_gaps), generated_at="2026-02-01T00:00:00")
    new.score_pct = 60.0
    new.maturity_score_pct = 55.0

    delta = compare_snapshots(old, new)
    assert delta.score_delta == 30.0
    assert delta.maturity_delta == 30.0
    assert delta.newly_implemented == ["GOV-01"]
    assert delta.regressed == ["PROT-01"]
