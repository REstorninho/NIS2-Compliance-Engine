import pytest

from nis2_engine import get_profile, load_profiles
from nis2_engine.classification import classify_entity
from nis2_engine.models import Entity, EntityType


def test_load_profiles_returns_the_four_verticals():
    profiles = load_profiles()
    ids = {p.id for p in profiles}
    assert {"camara_municipal", "junta_freguesia", "hotelaria", "agencia_viagens"} <= ids


def test_get_profile_unknown_raises_with_available_ids():
    with pytest.raises(KeyError) as exc:
        get_profile("inexistente")
    assert "camara_municipal" in str(exc.value)


def test_public_body_profiles_classify_as_entidade_publica_relevante():
    for pid in ("camara_municipal", "junta_freguesia"):
        p = get_profile(pid)
        entity = Entity(**{k: v for k, v in p.entity_dict().items() if k != "name"}, name=p.nome)
        assert classify_entity(entity) is EntityType.ENTIDADE_PUBLICA_RELEVANTE


def test_tourism_profiles_are_out_of_direct_scope_and_flag_indirect_scope():
    # Hotelaria e turismo NÃO são setores dos anexos: classificação direta fora
    # de âmbito, e o perfil tem de o assinalar e sugerir nível voluntário.
    for pid in ("hotelaria", "agencia_viagens"):
        p = get_profile(pid)
        entity = Entity(
            name=p.nome,
            sector=p.setor,
            employees=p.employees,
            annual_turnover_eur=p.annual_turnover_eur,
            is_public_body=p.is_public_body,
        )
        assert classify_entity(entity) is EntityType.FORA_DE_AMBITO
        assert "INDIRETAMENTE" in p.ambito_nota.upper()
        assert p.nivel_referencia_sugerido == "basico"


def test_profile_scenarios_are_valid_for_risk_matrix():
    p = get_profile("camara_municipal")
    assert p.cenarios
    for c in p.cenarios:
        assert 1 <= c.probabilidade <= 5
        assert 1 <= c.impacto <= 5
    # O scenarios_dict tem de ter a forma que o load_risk_scenarios espera.
    d = p.scenarios_dict()
    assert "scenarios" in d
    assert d["scenarios"][0]["name"] == p.cenarios[0].name
