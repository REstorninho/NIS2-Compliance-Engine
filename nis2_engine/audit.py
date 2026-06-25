from __future__ import annotations

from dataclasses import dataclass, field

from .classification import CLASSIFICACAO_ESTADO_VALIDACAO, CLASSIFICACAO_FONTE
from .models import Control


@dataclass
class AuditReport:
    """Relatório de rastreabilidade jurídica: que partes do corpus normativo
    (controlos e classificação setorial) já foram confirmadas artigo-a-artigo
    contra o texto oficial, e quais continuam por validar."""

    total_controls: int
    confirmed_controls: list[Control] = field(default_factory=list)
    pending_controls: list[Control] = field(default_factory=list)
    classification_status: str = CLASSIFICACAO_ESTADO_VALIDACAO
    classification_source: str = CLASSIFICACAO_FONTE

    @property
    def pending_pct(self) -> float:
        if self.total_controls == 0:
            return 0.0
        return round(len(self.pending_controls) / self.total_controls * 100, 1)

    @property
    def fully_validated(self) -> bool:
        return not self.pending_controls and self.classification_status == "confirmado"


def build_audit_report(controls: list[Control]) -> AuditReport:
    confirmed = [c for c in controls if c.estado_validacao == "confirmado"]
    pending = [c for c in controls if c.estado_validacao != "confirmado"]
    return AuditReport(
        total_controls=len(controls),
        confirmed_controls=confirmed,
        pending_controls=pending,
    )
