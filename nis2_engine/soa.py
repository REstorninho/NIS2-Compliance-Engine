from __future__ import annotations

from .models import (
    AssessmentResult,
    Control,
    SoAEntry,
    StatementOfApplicability,
)


def build_statement_of_applicability(result: AssessmentResult, controls: list[Control]) -> StatementOfApplicability:
    """Constrói a Statement of Applicability a partir de um resultado de
    assessment: cada controlo aplicável ao nível-alvo aparece com o estado de
    implementação observado; os não aplicáveis aparecem com justificação
    automática ("não exigido ao nível X").
    """
    implemented_ids = {gap.control.id for gap in result.gaps if gap.implemented}
    applicable_ids = {gap.control.id for gap in result.gaps}

    entries: list[SoAEntry] = []
    for control in controls:
        applicable = control.id in applicable_ids
        if applicable:
            entries.append(
                SoAEntry(
                    control=control,
                    applicable=True,
                    implemented=control.id in implemented_ids,
                )
            )
        else:
            entries.append(
                SoAEntry(
                    control=control,
                    applicable=False,
                    implemented=False,
                    justification=f"Controlo não exigido ao nível de conformidade '{result.target_level.value}'.",
                )
            )

    return StatementOfApplicability(
        entity=result.entity,
        target_level=result.target_level,
        entries=entries,
    )
