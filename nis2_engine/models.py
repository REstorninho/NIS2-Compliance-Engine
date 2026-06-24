from __future__ import annotations

from dataclasses import dataclass, field
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

    def required_at(self, level: ComplianceLevel) -> bool:
        return self.levels.get(level.value, False)


@dataclass
class Entity:
    name: str
    sector: str
    employees: int
    annual_turnover_eur: float
    is_public_body: bool = False

    def meets_size_threshold(self) -> bool:
        """Regra de dimensão: >=50 trabalhadores ou >10M€ de volume de negócios."""
        return self.employees >= 50 or self.annual_turnover_eur > 10_000_000


@dataclass
class AssessmentAnswer:
    control_id: str
    implemented: bool
    notes: str = ""
    evidence_ref: str | None = None


@dataclass
class GapItem:
    control: Control
    implemented: bool
    priority: str  # "alta", "media", "baixa" — derivado da função QNRCS


@dataclass
class AssessmentResult:
    entity: Entity
    target_level: ComplianceLevel
    score_pct: float
    gaps: list[GapItem]
    not_applicable: list[Control]
