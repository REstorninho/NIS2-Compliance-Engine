from nis2_engine import (
    Entity,
    EntityType,
    classify_entity,
    render_self_identification,
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
