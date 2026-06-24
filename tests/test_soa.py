from nis2_engine import Entity, load_controls, run_assessment
from nis2_engine.models import AssessmentAnswer, ComplianceLevel
from nis2_engine.soa import build_statement_of_applicability


def test_soa_covers_all_controls():
    controls = load_controls()
    entity = Entity(name="Operador Energético", sector="energia", employees=200, annual_turnover_eur=50_000_000)
    target_level = ComplianceLevel.ELEVADO

    result = run_assessment(entity, target_level, controls, answers=[])
    soa = build_statement_of_applicability(result, controls)

    assert len(soa.entries) == len(controls)


def test_soa_marks_implemented_controls():
    controls = load_controls()
    entity = Entity(name="Operador Energético", sector="energia", employees=200, annual_turnover_eur=50_000_000)
    target_level = ComplianceLevel.ELEVADO

    answers = [AssessmentAnswer(control_id="GOV-01", implemented=True)]
    result = run_assessment(entity, target_level, controls, answers)
    soa = build_statement_of_applicability(result, controls)

    gov_entry = next(e for e in soa.entries if e.control.id == "GOV-01")
    assert gov_entry.applicable is True
    assert gov_entry.implemented is True


def test_soa_marks_non_applicable_controls_with_justification():
    controls = load_controls()
    entity = Entity(name="PME", sector="alimentacao", employees=60, annual_turnover_eur=5_000_000)
    target_level = ComplianceLevel.BASICO

    result = run_assessment(entity, target_level, controls, answers=[])
    soa = build_statement_of_applicability(result, controls)

    non_applicable = [e for e in soa.entries if not e.applicable]
    assert len(non_applicable) > 0
    assert all(e.justification for e in non_applicable)
    assert all(not e.implemented for e in non_applicable)
