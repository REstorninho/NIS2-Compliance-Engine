from __future__ import annotations

from .models import ComplianceLevel, Entity, EntityType

# Setores do Anexo I (entidades essenciais) e Anexo II (entidades importantes)
# do DL 125/2025, confirmados por fontes secundárias (CMS, Crowe, PWC) na
# ausência de acesso direto ao texto do Diário da República nesta sessão.
# IMPORTANTE: "turismo" NÃO consta de nenhum dos dois anexos e foi removido
# (estava incorretamente listado numa versão anterior). Uma entidade do setor
# do turismo só fica em âmbito por via indireta: ser fornecedora/subcontratada
# de uma entidade essencial/importante (gestão de risco da cadeia de
# abastecimento, Art. 21(2)(d)), nunca por classificação setorial direta.
# Esta lista ainda não foi validada artigo-a-artigo contra o texto oficial —
# ver README/TODO de validação jurídica.
SETORES_ESSENCIAIS = {
    "energia",
    "transportes",
    "banca",
    "infraestruturas_mercado_financeiro",
    "saude",
    "agua_potavel",
    "aguas_residuais",
    "infraestrutura_digital",
    "gestao_servicos_tic",
    "administracao_publica",
    "espaco",
}

SETORES_IMPORTANTES = {
    "servicos_postais",
    "gestao_residuos",
    "quimicos",
    "alimentacao",
    "fabricacao",
    "servicos_digitais",
    "investigacao",
}

# Estado de validação jurídica desta classificação setorial — usado por
# `nis2 audit`. Passa a "confirmado" só depois de uma validação artigo-a-artigo
# contra o texto oficial do DL 125/2025 publicado em Diário da República.
CLASSIFICACAO_ESTADO_VALIDACAO = "por_validar"
CLASSIFICACAO_FONTE = "CMS, Crowe, PWC (fontes secundárias) — sem confirmação direta no DRE"

def classify_entity(entity: Entity) -> EntityType:
    """Determina o tipo de entidade nos termos do DL 125/2025.

    Aplica a regra de dimensão (>=50 trabalhadores ou >10M€) exceto para
    prestadores de serviços de confiança qualificados, registos de TLD e
    prestadores de serviço DNS (exceção expressa, independente da dimensão),
    e classifica como essencial/importante de acordo com o setor declarado.
    """
    sector = entity.sector.lower().strip()

    if entity.is_public_body:
        return EntityType.ENTIDADE_PUBLICA_RELEVANTE

    if entity.is_dns_tld_or_trust_service_provider:
        return EntityType.ESSENCIAL

    if not entity.meets_size_threshold():
        return EntityType.FORA_DE_AMBITO

    if sector in SETORES_ESSENCIAIS:
        return EntityType.ESSENCIAL
    if sector in SETORES_IMPORTANTES:
        return EntityType.IMPORTANTE

    return EntityType.FORA_DE_AMBITO


def required_compliance_level(entity_type: EntityType) -> ComplianceLevel:
    """Mapeia o tipo de entidade para o nível mínimo da matriz de risco
    (Anexo II do Regulamento 756/2026). Entidades essenciais e entidades
    públicas relevantes têm como referência o nível 'elevado'; entidades
    importantes o nível 'substancial'. O nível efetivo pode ser ajustado por
    avaliação de risco caso a caso — este é o ponto de partida.
    """
    mapping = {
        EntityType.ESSENCIAL: ComplianceLevel.ELEVADO,
        EntityType.ENTIDADE_PUBLICA_RELEVANTE: ComplianceLevel.ELEVADO,
        EntityType.IMPORTANTE: ComplianceLevel.SUBSTANCIAL,
    }
    if entity_type not in mapping:
        raise ValueError(f"Entidade fora de âmbito não tem nível de conformidade exigido: {entity_type}")
    return mapping[entity_type]
