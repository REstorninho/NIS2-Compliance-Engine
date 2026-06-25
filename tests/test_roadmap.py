from nis2_engine import Entity, build_remediation_roadmap, load_controls, run_assessment
from nis2_engine.models import AssessmentAnswer, ComplianceLevel


def test_roadmap_groups_gaps_by_priority_phase():
    controls = load_controls()
    entity = Entity(name="Operador Energético", sector="energia", employees=200, annual_turnover_eur=50_000_000)
    target_level = ComplianceLevel.ELEVADO

    result = run_assessment(entity, target_level, controls, answers=[])
    roadmap = build_remediation_roadmap(result)

    assert roadmap.entity_name == entity.name
    assert roadmap.target_level == target_level.value
    # Fases ordenadas por prioridade decrescente de urgência.
    priorities = [phase.priority for phase in roadmap.phases]
    assert priorities == sorted(priorities, key=lambda p: {"alta": 0, "media": 1, "baixa": 2}[p])
    for phase in roadmap.phases:
        assert all(gap.priority == phase.priority for gap in phase.gaps)
        assert all(not gap.implemented for gap in phase.gaps)


def test_roadmap_has_no_phases_when_fully_implemented():
    controls = load_controls()
    entity = Entity(name="Operador Energético", sector="energia", employees=200, annual_turnover_eur=50_000_000)
    target_level = ComplianceLevel.ELEVADO

    required_ids = [c.id for c in controls if c.required_at(target_level)]
    answers = [AssessmentAnswer(control_id=cid, implemented=True) for cid in required_ids]
    result = run_assessment(entity, target_level, controls, answers)
    roadmap = build_remediation_roadmap(result)

    assert roadmap.phases == []
