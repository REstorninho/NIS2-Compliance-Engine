from __future__ import annotations

from dataclasses import dataclass, field

from .classification import SETORES_ESSENCIAIS
from .models import ComplianceLevel, Entity

# ---------------------------------------------------------------------------
# Anexo II do Regulamento n.º 756/2026 — Matriz de Risco.
#
# Valor de risco (por cenário) =
#     Probabilidade × Impacto × (Dimensão / 3) × Tipo de setor
#
#   · Probabilidade e Impacto: escala 1–5.
#   · Dimensão: Grande = 3, Média = 2, Pequena = 1 → fator (Dimensão/3) ∈
#     {1.0, 0.667, 0.333}.
#   · Tipo de setor: Importância Crítica (Anexo I) = 1.5; Outros Setores
#     Críticos (Anexo II) = 1.0.
#
# O valor total é a soma dos valores de todos os cenários/atores considerados,
# e mapeia para o nível de conformidade exigido:
#     Básico 0–99 · Substancial 100–199 · Elevado 200–1200.
#
# NOTA DE VALIDAÇÃO: as bandas de dimensão (G/M/P) seguem a Recomendação
# 2003/361/CE (PME) por defeito; tal como a classificação setorial, carecem de
# confirmação artigo-a-artigo contra o texto do Regulamento publicado no DRE.
# ---------------------------------------------------------------------------

DIMENSAO_FATOR = {"grande": 3 / 3, "media": 2 / 3, "pequena": 1 / 3}
TIPO_SETOR_FATOR = {"importancia_critica": 1.5, "outros_criticos": 1.0}

# Limiares de nível do Anexo II.
LIMIAR_SUBSTANCIAL = 100
LIMIAR_ELEVADO = 200
VALOR_RISCO_MAXIMO = 1200

PROBABILIDADE_MIN, PROBABILIDADE_MAX = 1, 5
IMPACTO_MIN, IMPACTO_MAX = 1, 5

# Ordem de exigência dos níveis, para a regra de agregação do art. 30.º
# (entidade em mais do que um nível aplica o mais exigente).
_LEVEL_ORDER = {
    ComplianceLevel.BASICO: 0,
    ComplianceLevel.SUBSTANCIAL: 1,
    ComplianceLevel.ELEVADO: 2,
}


def most_demanding(*levels: ComplianceLevel | None) -> ComplianceLevel:
    """Regra de agregação do art. 30.º: devolve o nível mais exigente de entre
    os fornecidos (Elevado > Substancial > Básico). Ignora None."""
    presentes = [lvl for lvl in levels if lvl is not None]
    if not presentes:
        return ComplianceLevel.BASICO
    return max(presentes, key=lambda lvl: _LEVEL_ORDER[lvl])


def classify_dimensao(entity: Entity) -> str:
    """Classifica a dimensão da entidade (grande/media/pequena) para a
    ponderação da matriz, a partir do n.º de trabalhadores e do volume de
    negócios (bandas PME — Recomendação 2003/361/CE)."""
    if entity.employees >= 250 or entity.annual_turnover_eur > 50_000_000:
        return "grande"
    if entity.employees >= 50 or entity.annual_turnover_eur > 10_000_000:
        return "media"
    return "pequena"


def classify_tipo_setor(entity: Entity) -> str:
    """Classifica o tipo de setor: 'importancia_critica' (Anexo I / entidades
    públicas) ou 'outros_criticos' (Anexo II)."""
    if entity.is_public_body or entity.sector.lower().strip() in SETORES_ESSENCIAIS:
        return "importancia_critica"
    return "outros_criticos"


@dataclass
class RiskScenario:
    """Cenário de risco (ameaça/ator) a ponderar na matriz. Probabilidade e
    impacto na escala 1–5."""

    name: str
    probabilidade: int
    impacto: int
    threat_actor: str = ""
    description: str = ""

    def validate(self) -> None:
        if not (PROBABILIDADE_MIN <= self.probabilidade <= PROBABILIDADE_MAX):
            raise ValueError(
                f"Probabilidade do cenário '{self.name}' fora da escala "
                f"{PROBABILIDADE_MIN}–{PROBABILIDADE_MAX}: {self.probabilidade}"
            )
        if not (IMPACTO_MIN <= self.impacto <= IMPACTO_MAX):
            raise ValueError(
                f"Impacto do cenário '{self.name}' fora da escala "
                f"{IMPACTO_MIN}–{IMPACTO_MAX}: {self.impacto}"
            )


@dataclass
class RiskScenarioResult:
    scenario: RiskScenario
    valor: float


@dataclass
class RiskMatrixResult:
    entity_name: str
    dimensao: str
    dimensao_fator: float
    tipo_setor: str
    tipo_setor_fator: float
    scenarios: list[RiskScenarioResult]
    total: float
    nivel_matriz: ComplianceLevel
    nivel_referencia: ComplianceLevel | None  # nível pelo tipo de entidade
    nivel_efetivo: ComplianceLevel  # mais exigente (art. 30.º)
    avisos: list[str] = field(default_factory=list)


def compute_scenario_value(
    probabilidade: int, impacto: int, dimensao_fator: float, tipo_setor_fator: float
) -> float:
    """Valor de risco de um cenário, segundo a fórmula do Anexo II."""
    return probabilidade * impacto * dimensao_fator * tipo_setor_fator


def classify_risk_level(total: float) -> ComplianceLevel:
    """Mapeia o valor de risco total para o nível de conformidade do Anexo II."""
    if total >= LIMIAR_ELEVADO:
        return ComplianceLevel.ELEVADO
    if total >= LIMIAR_SUBSTANCIAL:
        return ComplianceLevel.SUBSTANCIAL
    return ComplianceLevel.BASICO


def build_risk_matrix(
    entity: Entity,
    scenarios: list[RiskScenario],
    nivel_referencia: ComplianceLevel | None = None,
) -> RiskMatrixResult:
    """Constrói a matriz de risco (Anexo II) para a entidade: classifica
    dimensão e tipo de setor, calcula o valor de cada cenário e o total,
    mapeia para o nível, e aplica a regra de agregação do art. 30.º contra o
    `nivel_referencia` (tipicamente o nível derivado do tipo de entidade)."""
    if not scenarios:
        raise ValueError("É necessário pelo menos um cenário de risco para a matriz.")
    for scenario in scenarios:
        scenario.validate()

    dimensao = classify_dimensao(entity)
    tipo_setor = classify_tipo_setor(entity)
    dimensao_fator = DIMENSAO_FATOR[dimensao]
    tipo_setor_fator = TIPO_SETOR_FATOR[tipo_setor]

    resultados = [
        RiskScenarioResult(
            scenario=s,
            valor=round(compute_scenario_value(s.probabilidade, s.impacto, dimensao_fator, tipo_setor_fator), 2),
        )
        for s in scenarios
    ]
    total = round(sum(r.valor for r in resultados), 2)

    nivel_matriz = classify_risk_level(total)
    nivel_efetivo = most_demanding(nivel_matriz, nivel_referencia)

    avisos: list[str] = []
    if total > VALOR_RISCO_MAXIMO:
        avisos.append(
            f"Valor total ({total}) excede o máximo da escala do Anexo II "
            f"({VALOR_RISCO_MAXIMO}) — rever o n.º de cenários ou a ponderação."
        )
    if nivel_referencia is not None and _LEVEL_ORDER[nivel_referencia] > _LEVEL_ORDER[nivel_matriz]:
        avisos.append(
            f"O nível pela matriz ({nivel_matriz.value}) é inferior ao exigido pelo tipo "
            f"de entidade ({nivel_referencia.value}); por agregação (art. 30.º) aplica-se "
            f"o mais exigente: {nivel_efetivo.value}."
        )

    return RiskMatrixResult(
        entity_name=entity.name,
        dimensao=dimensao,
        dimensao_fator=round(dimensao_fator, 3),
        tipo_setor=tipo_setor,
        tipo_setor_fator=tipo_setor_fator,
        scenarios=resultados,
        total=total,
        nivel_matriz=nivel_matriz,
        nivel_referencia=nivel_referencia,
        nivel_efetivo=nivel_efetivo,
        avisos=avisos,
    )
