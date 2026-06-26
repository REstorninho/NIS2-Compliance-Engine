import pytest

from nis2_engine import (
    Entity,
    RiskScenario,
    build_risk_matrix,
    classify_dimensao,
    classify_risk_level,
    classify_tipo_setor,
    most_demanding,
)
from nis2_engine.models import ComplianceLevel


def test_scenario_value_follows_anexo_ii_formula():
    # Grande (fator 1.0) + importância crítica (1.5): 4×5×1.0×1.5 = 30
    entity = Entity(name="X", sector="energia", employees=300, annual_turnover_eur=0)
    matrix = build_risk_matrix(entity, [RiskScenario(name="c1", probabilidade=4, impacto=5)])
    assert matrix.dimensao == "grande"
    assert matrix.tipo_setor == "importancia_critica"
    assert matrix.scenarios[0].valor == 30.0
    assert matrix.total == 30.0


def test_dimensao_bands():
    assert classify_dimensao(Entity("a", "energia", 300, 0)) == "grande"
    assert classify_dimensao(Entity("a", "energia", 0, 60_000_000)) == "grande"
    assert classify_dimensao(Entity("a", "energia", 60, 0)) == "media"
    assert classify_dimensao(Entity("a", "energia", 10, 0)) == "pequena"


def test_tipo_setor_critico_vs_outros():
    assert classify_tipo_setor(Entity("a", "energia", 50, 0)) == "importancia_critica"
    assert classify_tipo_setor(Entity("a", "fabricacao", 50, 0)) == "outros_criticos"
    # Entidade pública é sempre importância crítica.
    assert classify_tipo_setor(Entity("a", "outro", 1, 0, is_public_body=True)) == "importancia_critica"


def test_level_thresholds():
    assert classify_risk_level(0) is ComplianceLevel.BASICO
    assert classify_risk_level(99) is ComplianceLevel.BASICO
    assert classify_risk_level(100) is ComplianceLevel.SUBSTANCIAL
    assert classify_risk_level(199) is ComplianceLevel.SUBSTANCIAL
    assert classify_risk_level(200) is ComplianceLevel.ELEVADO


def test_most_demanding_aggregation_art30():
    assert most_demanding(ComplianceLevel.BASICO, ComplianceLevel.ELEVADO) is ComplianceLevel.ELEVADO
    assert most_demanding(ComplianceLevel.SUBSTANCIAL, None) is ComplianceLevel.SUBSTANCIAL
    assert most_demanding(None) is ComplianceLevel.BASICO


def test_aggregation_raises_matrix_level_to_type_floor():
    # Poucos cenários → matriz dá substancial, mas tipo essencial força elevado.
    entity = Entity(name="X", sector="energia", employees=300, annual_turnover_eur=0)
    scenarios = [RiskScenario(name="c", probabilidade=5, impacto=5)]  # 37.5 → básico
    matrix = build_risk_matrix(entity, scenarios, nivel_referencia=ComplianceLevel.ELEVADO)
    assert matrix.nivel_efetivo is ComplianceLevel.ELEVADO
    assert matrix.avisos  # deve sinalizar a agregação


def test_empty_scenarios_raise():
    entity = Entity(name="X", sector="energia", employees=300, annual_turnover_eur=0)
    with pytest.raises(ValueError):
        build_risk_matrix(entity, [])


def test_out_of_range_probabilidade_raises():
    entity = Entity(name="X", sector="energia", employees=300, annual_turnover_eur=0)
    with pytest.raises(ValueError):
        build_risk_matrix(entity, [RiskScenario(name="c", probabilidade=6, impacto=3)])
