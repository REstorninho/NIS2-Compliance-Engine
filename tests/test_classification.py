import pytest

from nis2_engine import Entity, EntityType
from nis2_engine.classification import classify_entity, required_compliance_level
from nis2_engine.models import ComplianceLevel


def test_small_entity_without_size_exception_is_out_of_scope():
    entity = Entity(name="Pequena Padaria", sector="alimentacao", employees=5, annual_turnover_eur=300_000)
    assert classify_entity(entity) == EntityType.FORA_DE_AMBITO


def test_tourism_sector_is_out_of_scope_no_direct_nis2_classification():
    """Turismo não consta dos Anexos I/II do DL 125/2025 — uma entidade deste
    setor só entra em âmbito por via indireta (ex: fornecedor de uma entidade
    essencial/importante), nunca por classificação setorial direta."""
    entity = Entity(name="Grupo Hoteleiro Algarve", sector="turismo", employees=80, annual_turnover_eur=12_000_000)
    assert classify_entity(entity) == EntityType.FORA_DE_AMBITO


def test_medium_food_entity_is_importante():
    entity = Entity(name="Distribuidora Alimentar", sector="alimentacao", employees=80, annual_turnover_eur=12_000_000)
    assert classify_entity(entity) == EntityType.IMPORTANTE


def test_energy_entity_is_essencial():
    entity = Entity(name="Operador Energético", sector="energia", employees=200, annual_turnover_eur=50_000_000)
    assert classify_entity(entity) == EntityType.ESSENCIAL


def test_public_body_is_entidade_publica_relevante():
    entity = Entity(name="Câmara Municipal", sector="administracao_publica", employees=10, annual_turnover_eur=0, is_public_body=True)
    assert classify_entity(entity) == EntityType.ENTIDADE_PUBLICA_RELEVANTE


def test_dns_provider_has_no_size_exception():
    entity = Entity(
        name="Provedor DNS",
        sector="infraestrutura_digital",
        employees=3,
        annual_turnover_eur=200_000,
        is_dns_tld_or_trust_service_provider=True,
    )
    assert classify_entity(entity) == EntityType.ESSENCIAL


def test_small_digital_infrastructure_without_dns_exception_is_out_of_scope():
    entity = Entity(name="Pequeno Provedor de Rede", sector="infraestrutura_digital", employees=3, annual_turnover_eur=200_000)
    assert classify_entity(entity) == EntityType.FORA_DE_AMBITO


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
