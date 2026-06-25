from __future__ import annotations

from dataclasses import dataclass, field

from .models import AssessmentResult, GapItem

# Fases de remediação por prioridade — alinhadas com _PRIORITY_BY_FUNCTION em
# assessment.py: prioridade alta exige ação imediata, baixa pode ser planeada
# a médio prazo.
_PHASES_BY_PRIORITY = {
    "alta": ("Fase 1", "0-3 meses"),
    "media": ("Fase 2", "3-6 meses"),
    "baixa": ("Fase 3", "6-12 meses"),
}
_PHASE_ORDER = {"alta": 0, "media": 1, "baixa": 2}


@dataclass
class RoadmapPhase:
    name: str
    timeframe: str
    priority: str
    gaps: list[GapItem] = field(default_factory=list)


@dataclass
class RemediationRoadmap:
    entity_name: str
    target_level: str
    phases: list[RoadmapPhase]
    maturity_by_function: dict[str, float]


def build_remediation_roadmap(result: AssessmentResult) -> RemediationRoadmap:
    """Agrupa os gaps por remediar em fases temporais faseadas por prioridade,
    para apoiar o planeamento de remediação do cliente."""
    open_gaps = [g for g in result.gaps if not g.implemented]

    phases: list[RoadmapPhase] = []
    for priority in sorted(_PHASES_BY_PRIORITY, key=lambda p: _PHASE_ORDER[p]):
        name, timeframe = _PHASES_BY_PRIORITY[priority]
        gaps = [g for g in open_gaps if g.priority == priority]
        if gaps:
            phases.append(RoadmapPhase(name=name, timeframe=timeframe, priority=priority, gaps=gaps))

    return RemediationRoadmap(
        entity_name=result.entity.name,
        target_level=result.target_level.value,
        phases=phases,
        maturity_by_function=result.maturity_by_function,
    )
