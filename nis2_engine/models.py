from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ComplianceLevel(str, Enum):
    BASICO = "basico"
    SUBSTANCIAL = "substancial"
    ELEVADO = "elevado"


class EntityType(str, Enum):
    ESSENCIAL = "essencial"
    IMPORTANTE = "importante"
    ENTIDADE_PUBLICA_RELEVANTE = "entidade_publica_relevante"
    FORA_DE_AMBITO = "fora_de_ambito"


@dataclass
class Crosswalk:
    nis2_article: list[str] = field(default_factory=list)
    regulamento_756_2026: list[str] = field(default_factory=list)
    iso27001_annex_a: list[str] = field(default_factory=list)
    cis_controls_v8: list[str] = field(default_factory=list)
    rgpd: list[str] = field(default_factory=list)


@dataclass
class Control:
    id: str
    title: str
    qnrcs_function: str
    levels: dict[str, bool]
    evidence_type: str
    description: str = ""
    crosswalk: Crosswalk = field(default_factory=Crosswalk)
    evidence_contract: dict | None = None
    # Rastreabilidade jurídica: se o crosswalk legal foi confirmado
    # artigo-a-artigo contra o texto oficial (DRE) ou apenas via fontes
    # secundárias. Por omissão "por_validar" — só passa a "confirmado" depois
    # de uma validação explícita (ver `nis2 audit`).
    estado_validacao: str = "por_validar"
    fonte: str = ""

    def required_at(self, level: ComplianceLevel) -> bool:
        return self.levels.get(level.value, False)


# Regra de dimensão (DL 125/2025): uma entidade atinge o limiar se tiver pelo
# menos SIZE_THRESHOLD_EMPLOYEES trabalhadores OU um volume de negócios anual
# superior a SIZE_THRESHOLD_TURNOVER_EUR. Constantes nomeadas para servirem de
# fonte de verdade única (motor + formulário HTML gerado por `nis2 form`).
SIZE_THRESHOLD_EMPLOYEES = 50
SIZE_THRESHOLD_TURNOVER_EUR = 10_000_000


@dataclass
class Entity:
    name: str
    sector: str
    employees: int
    annual_turnover_eur: float
    is_public_body: bool = False
    # Prestador de serviços de confiança qualificados, registo de TLD, ou
    # prestador de serviço de sistema de nomes de domínio (DNS) — qualifica-se
    # como entidade essencial independentemente da dimensão (DL 125/2025).
    is_dns_tld_or_trust_service_provider: bool = False

    def meets_size_threshold(self) -> bool:
        """Regra de dimensão: >=50 trabalhadores ou >10M€ de volume de negócios."""
        return (
            self.employees >= SIZE_THRESHOLD_EMPLOYEES
            or self.annual_turnover_eur > SIZE_THRESHOLD_TURNOVER_EUR
        )


MATURITY_LABELS = {
    0: "Inexistente",
    1: "Inicial",
    2: "Em desenvolvimento",
    3: "Definido",
    4: "Gerido",
    5: "Otimizado",
}

# Maturidade mínima ("Definido") a partir da qual um controlo é considerado
# implementado para efeitos binários (SoA, templates legados).
MATURITY_IMPLEMENTED_THRESHOLD = 3


@dataclass
class AssessmentAnswer:
    control_id: str
    implemented: bool
    notes: str = ""
    evidence_ref: str | None = None
    # Escala de maturidade graduada 0-5 (ver MATURITY_LABELS). Se None, deriva-se
    # de `implemented` (5 se True, 0 se False) — compatibilidade com dados antigos.
    maturity: int | None = None

    def effective_maturity(self) -> int:
        if self.maturity is not None:
            return max(0, min(5, self.maturity))
        return 5 if self.implemented else 0


@dataclass
class GapItem:
    control: Control
    implemented: bool
    priority: str  # "alta", "media", "baixa" — derivado da função QNRCS
    maturity: int = 0  # maturidade observada (0-5)


@dataclass
class AssessmentResult:
    entity: Entity
    target_level: ComplianceLevel
    score_pct: float
    gaps: list[GapItem]
    not_applicable: list[Control]
    # Score contínuo (média de maturidade/5 * 100) e média de maturidade por
    # função QNRCS — dados de suporte a um futuro gráfico radar.
    maturity_score_pct: float = 0.0
    maturity_by_function: dict[str, float] = field(default_factory=dict)


@dataclass
class SoAEntry:
    """Linha da Statement of Applicability: um controlo, é aplicável ou não, e
    com que estado de implementação, à semelhança do Anexo A da ISO 27001."""

    control: Control
    applicable: bool
    implemented: bool
    justification: str = ""
    evidence_ref: str | None = None


@dataclass
class StatementOfApplicability:
    entity: Entity
    target_level: ComplianceLevel
    entries: list[SoAEntry]


@dataclass
class IncidentNotification:
    """Dados de um incidente para gerar os deliverables do regime de
    notificação ao CNCS via MyCiber (DL 125/2025, Art. 23): alerta inicial em
    24h, relatório detalhado em 72h, e relatório final em 1 mês."""

    incident_id: str
    entity: Entity
    detected_at: datetime
    severity: str  # "baixo", "medio", "alto", "critico"
    description: str
    affected_systems: list[str] = field(default_factory=list)
    impact_summary: str = ""
    indicators_of_compromise: list[str] = field(default_factory=list)
    cross_border_effect: bool = False
    root_cause: str = ""
    mitigation_actions: list[str] = field(default_factory=list)
    status: str = "em_curso"
    # Campos das fases finais do regime de notificação:
    # - fim do impacto significativo (Art. 43.º): momento em que o impacto
    #   significativo cessou; permite calcular a duração total.
    # - relatório final (Art. 44.º): tipo de ameaça/causa raiz consolidada,
    #   medidas de mitigação ainda em curso e lições aprendidas.
    significant_impact_ended_at: datetime | None = None
    threat_type: str = ""
    ongoing_mitigation_actions: list[str] = field(default_factory=list)
    lessons_learned: str = ""

    def significant_impact_duration_hours(self) -> float | None:
        """Duração (horas) do impacto significativo, da deteção ao seu fim.
        None se o fim ainda não estiver registado."""
        if self.significant_impact_ended_at is None:
            return None
        delta = self.significant_impact_ended_at - self.detected_at
        return round(delta.total_seconds() / 3600, 1)
