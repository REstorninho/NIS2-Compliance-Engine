from __future__ import annotations

from .models import ComplianceLevel, Entity, EntityType

# Setores do Anexo I (entidades essenciais) e Anexo II (entidades importantes)
# do regime jurídico da cibersegurança. Lista indicativa para o motor de
# classificação — a ser expandida com a tabela completa dos anexos.
SETORES_ESSENCIAIS = {
    "energia",
    "transportes",
    "banca",
    "infraestruturas_mercado_financeiro",
    "saude",
    "agua_potavel",
    "aguas_residuais",
    "infraestrutura_digital",
    "administracao_publica",
    "espaco",
}

SETORES_IMPORTANTES = {
    "servicos_postais",
    "gestao_residuos",
    "quimicos",
    "alimentacao",
    "fabricacao",
    "fornecedores_digitais",
    "investigacao",
    "turismo",
}

# Setores/entidades com exceção de dimensão (aplicam-se independentemente do
# número de trabalhadores ou volume de negócios) — ex: prestadores de DNS,
# registos de TLD, fornecedores de redes/serviços de comunicações públicas.
SETORES_SEM_EXCECAO_DIMENSAO = {
    "infraestrutura_digital",
    "fornecedores_digitais_criticos",
}


def classify_entity(entity: Entity) -> EntityType:
    """Determina o tipo de entidade nos termos do DL 125/2025.

    Aplica a regra de dimensão (>=50 trabalhadores ou >10M€) exceto para
    setores com exceção expressa, e classifica como essencial/importante de
    acordo com o setor declarado.
    """
    sector = entity.sector.lower().strip()

    if entity.is_public_body:
        return EntityType.ENTIDADE_PUBLICA_RELEVANTE

    sem_excecao = sector in SETORES_SEM_EXCECAO_DIMENSAO
    if not sem_excecao and not entity.meets_size_threshold():
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
