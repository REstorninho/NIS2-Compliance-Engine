from nis2_engine import (
    Entity,
    EntityType,
    build_remediation_roadmap,
    classify_entity,
    load_controls,
    render_roadmap,
    render_self_identification,
    run_assessment,
)
from nis2_engine.classification import required_compliance_level
from nis2_engine.models import ComplianceLevel


def test_self_identification_in_scope_mentions_level():
    entity = Entity(name="Energia SA", sector="energia", employees=200, annual_turnover_eur=50_000_000)
    entity_type = classify_entity(entity)
    level = required_compliance_level(entity_type)
    report = render_self_identification(entity, entity_type, level)
    assert "ELEVADO" in report
    assert "FORA DE ÂMBITO" not in report


def test_self_identification_out_of_scope_flags_indirect_obligations():
    entity = Entity(name="Padaria", sector="alimentacao", employees=5, annual_turnover_eur=100_000)
    entity_type = classify_entity(entity)
    assert entity_type is EntityType.FORA_DE_AMBITO
    report = render_self_identification(entity, entity_type, None)
    assert "FORA DE ÂMBITO" in report
    assert "cadeia de abastecimento" in report


def test_render_roadmap_lists_open_gaps_by_phase():
    controls = load_controls()
    entity = Entity(name="Operador Energético", sector="energia", employees=200, annual_turnover_eur=50_000_000)
    target_level = ComplianceLevel.ELEVADO
    result = run_assessment(entity, target_level, controls, answers=[])
    roadmap = build_remediation_roadmap(result)

    report = render_roadmap(roadmap)
    assert "Fase 1" in report
    assert "PRT-01" in report
