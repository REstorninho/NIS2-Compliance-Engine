from __future__ import annotations

from .models import (
    AssessmentAnswer,
    AssessmentResult,
    ComplianceLevel,
    Control,
    Entity,
    GapItem,
)

# Prioridade de remediação por função QNRCS — Responder/Recuperar e Proteger
# pesam mais porque a sua ausência tem maior impacto direto em incidentes.
_PRIORITY_BY_FUNCTION = {
    "Responder": "alta",
    "Recuperar": "alta",
    "Proteger": "alta",
    "Detetar": "media",
    "Identificar": "media",
    "Governar": "baixa",
}


def run_assessment(
    entity: Entity,
    target_level: ComplianceLevel,
    controls: list[Control],
    answers: list[AssessmentAnswer],
) -> AssessmentResult:
    """Cruza as respostas do questionário com os controlos exigidos para o
    nível-alvo do cliente e produz um gap-analysis priorizado.
    """
    answers_by_id = {a.control_id: a for a in answers}

    required = [c for c in controls if c.required_at(target_level)]
    not_applicable = [c for c in controls if not c.required_at(target_level)]

    gaps: list[GapItem] = []
    implemented_count = 0

    for control in required:
        answer = answers_by_id.get(control.id)
        implemented = bool(answer and answer.implemented)
        if implemented:
            implemented_count += 1
        gaps.append(
            GapItem(
                control=control,
                implemented=implemented,
                priority=_PRIORITY_BY_FUNCTION.get(control.qnrcs_function, "media"),
            )
        )

    score_pct = (implemented_count / len(required) * 100) if required else 0.0

    # Roadmap: gaps não implementados, ordenados por prioridade.
    priority_order = {"alta": 0, "media": 1, "baixa": 2}
    gaps.sort(key=lambda g: (g.implemented, priority_order.get(g.priority, 9)))

    return AssessmentResult(
        entity=entity,
        target_level=target_level,
        score_pct=round(score_pct, 1),
        gaps=gaps,
        not_applicable=not_applicable,
    )
