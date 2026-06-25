from nis2_engine import (
    Entity,
    EntityType,
    build_remediation_roadmap,
    classify_entity,
    load_controls,
    render_bcdr_policy,
    render_incident_response_policy,
    render_roadmap,
    render_self_identification,
    render_supplier_security_policy,
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


def test_policy_templates_mention_entity_and_approver():
    entity = Entity(name="Câmara Municipal de Exemplo", sector="administracao_publica", employees=300, annual_turnover_eur=0)

    incident_policy = render_incident_response_policy(entity, approver="Maria Silva")
    supplier_policy = render_supplier_security_policy(entity, approver="Maria Silva")
    bcdr_policy = render_bcdr_policy(entity, approver="Maria Silva")

    for policy in (incident_policy, supplier_policy, bcdr_policy):
        assert entity.name in policy
        assert "Maria Silva" in policy
