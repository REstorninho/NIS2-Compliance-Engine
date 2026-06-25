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


# Colunas do checklist de validação manual (ver `build_validation_checklist`).
# Os campos `*_atual` refletem o estado presente no corpus; os últimos quatro
# ficam em branco para o revisor preencher contra o texto oficial do DRE.
VALIDATION_CHECKLIST_FIELDS = [
    "item_id",
    "tipo",
    "titulo",
    "nis2_article_atual",
    "regulamento_756_2026_atual",
    "estado_validacao_atual",
    "fonte_atual",
    "artigo_confirmado_dre",
    "data_confirmacao",
    "confirmado_por",
    "observacoes",
]


def build_validation_checklist(controls: list[Control]) -> list[dict[str, str]]:
    """Gera as linhas de um checklist de validação jurídica manual: uma linha
    por controlo (crosswalk citado vs. estado atual) mais uma linha para a
    classificação setorial, com colunas em branco para um revisor confirmar
    artigo-a-artigo contra o texto oficial do DL 125/2025 e do Regulamento
    n.º 756/2026 publicados em Diário da República."""
    rows: list[dict[str, str]] = [
        {
            "item_id": "CLASSIFICACAO-SETORIAL",
            "tipo": "classificacao",
            "titulo": "Setores essenciais/importantes e regra de dimensão (Anexos I/II)",
            "nis2_article_atual": "",
            "regulamento_756_2026_atual": "",
            "estado_validacao_atual": CLASSIFICACAO_ESTADO_VALIDACAO,
            "fonte_atual": CLASSIFICACAO_FONTE,
            "artigo_confirmado_dre": "",
            "data_confirmacao": "",
            "confirmado_por": "",
            "observacoes": "",
        }
    ]
    for control in sorted(controls, key=lambda c: c.id):
        rows.append(
            {
                "item_id": control.id,
                "tipo": "controlo",
                "titulo": control.title,
                "nis2_article_atual": ", ".join(control.crosswalk.nis2_article),
                "regulamento_756_2026_atual": ", ".join(control.crosswalk.regulamento_756_2026),
                "estado_validacao_atual": control.estado_validacao,
                "fonte_atual": control.fonte,
                "artigo_confirmado_dre": "",
                "data_confirmacao": "",
                "confirmado_por": "",
                "observacoes": "",
            }
        )
    return rows
