from nis2_engine import Entity, load_controls, run_assessment
from nis2_engine.models import AssessmentAnswer, ComplianceLevel


def test_full_implementation_yields_100_percent_score():
    controls = load_controls()
    entity = Entity(name="Operador Energético", sector="energia", employees=200, annual_turnover_eur=50_000_000)
    target_level = ComplianceLevel.ELEVADO

    required_ids = [c.id for c in controls if c.required_at(target_level)]
    answers = [AssessmentAnswer(control_id=cid, implemented=True) for cid in required_ids]

    result = run_assessment(entity, target_level, controls, answers)

    assert result.score_pct == 100.0
    assert all(g.implemented for g in result.gaps)


def test_no_answers_yields_zero_score_and_all_gaps():
    controls = load_controls()
    entity = Entity(name="Distribuidora Alimentar", sector="alimentacao", employees=80, annual_turnover_eur=12_000_000)
    target_level = ComplianceLevel.SUBSTANCIAL

    result = run_assessment(entity, target_level, controls, answers=[])

    assert result.score_pct == 0.0
    assert all(not g.implemented for g in result.gaps)
    assert len(result.gaps) == len([c for c in controls if c.required_at(target_level)])


def test_gaps_are_sorted_unimplemented_first_by_priority():
    controls = load_controls()
    entity = Entity(name="Operador Energético", sector="energia", employees=200, annual_turnover_eur=50_000_000)
    target_level = ComplianceLevel.ELEVADO

    result = run_assessment(entity, target_level, controls, answers=[])

    unimplemented = [g for g in result.gaps if not g.implemented]
    priorities = [g.priority for g in unimplemented]
    priority_rank = {"alta": 0, "media": 1, "baixa": 2}
    ranks = [priority_rank[p] for p in priorities]
    assert ranks == sorted(ranks)


def test_basico_level_excludes_non_required_controls():
    controls = load_controls()
    entity = Entity(name="PME", sector="alimentacao", employees=60, annual_turnover_eur=5_000_000)
    target_level = ComplianceLevel.BASICO

    result = run_assessment(entity, target_level, controls, answers=[])

    assert all(not c.levels["basico"] for c in result.not_applicable)
    for gap in result.gaps:
        assert gap.control.required_at(target_level)


def test_maturity_score_reflects_graduated_scale():
    controls = load_controls()
    entity = Entity(name="Operador Energético", sector="energia", employees=200, annual_turnover_eur=50_000_000)
    target_level = ComplianceLevel.ELEVADO

    required_ids = [c.id for c in controls if c.required_at(target_level)]
    # Maturidade 2 ("Em desenvolvimento") não atinge o limiar de implementado.
    answers = [AssessmentAnswer(control_id=cid, implemented=False, maturity=2) for cid in required_ids]

    result = run_assessment(entity, target_level, controls, answers)

    assert result.score_pct == 0.0
    assert result.maturity_score_pct == 40.0  # 2/5 * 100
    assert all(g.maturity == 2 for g in result.gaps)
    assert all(not g.implemented for g in result.gaps)
    assert set(result.maturity_by_function) == {c.qnrcs_function for c in controls if c.required_at(target_level)}


def test_maturity_implemented_threshold_overrides_binary_flag():
    controls = load_controls()
    entity = Entity(name="Operador Energético", sector="energia", employees=200, annual_turnover_eur=50_000_000)
    target_level = ComplianceLevel.ELEVADO

    required_ids = [c.id for c in controls if c.required_at(target_level)]
    # implemented=True mas maturity baixa: a maturidade graduada prevalece.
    answers = [AssessmentAnswer(control_id=cid, implemented=True, maturity=1) for cid in required_ids]

    result = run_assessment(entity, target_level, controls, answers)

    assert all(not g.implemented for g in result.gaps)
    assert all(g.maturity == 1 for g in result.gaps)
