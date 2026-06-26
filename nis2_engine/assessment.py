from __future__ import annotations

from .models import (
    MATURITY_IMPLEMENTED_THRESHOLD,
    AssessmentAnswer,
    AssessmentResult,
    ComplianceLevel,
    Control,
    Entity,
    GapItem,
)

# Prioridade de remediação por função QNRCS — Responder/Recuperar e Proteger
# pesam mais porque a sua ausência tem maior impacto direto em incidentes.
PRIORITY_BY_FUNCTION = {
    "Responder": "alta",
    "Recuperar": "alta",
    "Proteger": "alta",
    "Detetar": "media",
    "Identificar": "media",
    "Governar": "baixa",
}
# Alias retrocompatível (nome privado anterior).
_PRIORITY_BY_FUNCTION = PRIORITY_BY_FUNCTION


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
    maturity_sum = 0
    maturity_by_function_sum: dict[str, int] = {}
    maturity_by_function_count: dict[str, int] = {}

    for control in required:
        answer = answers_by_id.get(control.id)
        maturity = answer.effective_maturity() if answer else 0
        implemented = maturity >= MATURITY_IMPLEMENTED_THRESHOLD
        if implemented:
            implemented_count += 1
        maturity_sum += maturity
        maturity_by_function_sum[control.qnrcs_function] = (
            maturity_by_function_sum.get(control.qnrcs_function, 0) + maturity
        )
        maturity_by_function_count[control.qnrcs_function] = (
            maturity_by_function_count.get(control.qnrcs_function, 0) + 1
        )
        gaps.append(
            GapItem(
                control=control,
                implemented=implemented,
                priority=PRIORITY_BY_FUNCTION.get(control.qnrcs_function, "media"),
                maturity=maturity,
            )
        )

    score_pct = (implemented_count / len(required) * 100) if required else 0.0
    maturity_score_pct = (maturity_sum / (len(required) * 5) * 100) if required else 0.0
    maturity_by_function = {
        function: round(maturity_by_function_sum[function] / maturity_by_function_count[function], 2)
        for function in maturity_by_function_sum
    }

    # Roadmap: gaps não implementados, ordenados por prioridade.
    priority_order = {"alta": 0, "media": 1, "baixa": 2}
    gaps.sort(key=lambda g: (g.implemented, priority_order.get(g.priority, 9)))

    return AssessmentResult(
        entity=entity,
        target_level=target_level,
        score_pct=round(score_pct, 1),
        gaps=gaps,
        not_applicable=not_applicable,
        maturity_score_pct=round(maturity_score_pct, 1),
        maturity_by_function=maturity_by_function,
    )
