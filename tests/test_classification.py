import pytest

from nis2_engine import Entity, EntityType
from nis2_engine.classification import classify_entity, required_compliance_level
from nis2_engine.models import ComplianceLevel


def test_small_entity_without_size_exception_is_out_of_scope():
    entity = Entity(name="Pequeno Hotel", sector="turismo", employees=5, annual_turnover_eur=300_000)
    assert classify_entity(entity) == EntityType.FORA_DE_AMBITO


def test_medium_tourism_entity_is_importante():
    entity = Entity(name="Grupo Hoteleiro Algarve", sector="turismo", employees=80, annual_turnover_eur=12_000_000)
    assert classify_entity(entity) == EntityType.IMPORTANTE


def test_energy_entity_is_essencial():
    entity = Entity(name="Operador Energético", sector="energia", employees=200, annual_turnover_eur=50_000_000)
    assert classify_entity(entity) == EntityType.ESSENCIAL


def test_public_body_is_entidade_publica_relevante():
    entity = Entity(name="Câmara Municipal", sector="administracao_publica", employees=10, annual_turnover_eur=0, is_public_body=True)
    assert classify_entity(entity) == EntityType.ENTIDADE_PUBLICA_RELEVANTE


def test_digital_infrastructure_has_no_size_exception():
    entity = Entity(name="Provedor DNS", sector="infraestrutura_digital", employees=3, annual_turnover_eur=200_000)
    assert classify_entity(entity) == EntityType.ESSENCIAL


@pytest.mark.parametrize(
    "entity_type,expected_level",
    [
        (EntityType.ESSENCIAL, ComplianceLevel.ELEVADO),
        (EntityType.ENTIDADE_PUBLICA_RELEVANTE, ComplianceLevel.ELEVADO),
        (EntityType.IMPORTANTE, ComplianceLevel.SUBSTANCIAL),
    ],
)
def test_required_compliance_level(entity_type, expected_level):
    assert required_compliance_level(entity_type) == expected_level


def test_required_compliance_level_raises_for_out_of_scope():
    with pytest.raises(ValueError):
        required_compliance_level(EntityType.FORA_DE_AMBITO)
