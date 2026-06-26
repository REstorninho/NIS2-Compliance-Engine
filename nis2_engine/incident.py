from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import IncidentNotification

# Prazos do regime de notificação de incidentes ao CNCS via MyCiber
# (DL 125/2025, Art. 23): alerta inicial em 24h, relatório detalhado/
# intermédio em 72h, relatório final em 1 mês após o relatório detalhado.
DEADLINE_ALERTA_INICIAL = timedelta(hours=24)
DEADLINE_RELATORIO_DETALHADO = timedelta(hours=72)
DEADLINE_RELATORIO_FINAL = timedelta(days=30)


@dataclass
class NotificationDeadlines:
    alerta_inicial: datetime
    relatorio_detalhado: datetime
    relatorio_final: datetime

    def time_remaining(self, stage: str, now: datetime) -> timedelta:
        deadline = getattr(self, stage)
        return deadline - now


def compute_deadlines(incident: IncidentNotification) -> NotificationDeadlines:
    return NotificationDeadlines(
        alerta_inicial=incident.detected_at + DEADLINE_ALERTA_INICIAL,
        relatorio_detalhado=incident.detected_at + DEADLINE_RELATORIO_DETALHADO,
        relatorio_final=incident.detected_at + DEADLINE_RELATORIO_FINAL,
    )


# ---------------------------------------------------------------------------
# Triagem de impacto significativo — Reg. de Execução (UE) 2024/2690, art. 3.º
#
# Critérios gerais: um incidente é significativo se, no mínimo:
#   (a) causou ou é capaz de causar perturbação operacional grave dos serviços
#       OU perdas financeiras para a entidade; ou
#   (b) afetou ou é capaz de afetar outras pessoas singulares ou coletivas,
#       causando danos materiais ou imateriais consideráveis.
#
# NOTA DE VALIDAÇÃO: os limiares QUANTITATIVOS específicos por setor/tipo de
# entidade (n.º de utilizadores, horas de indisponibilidade, montante das
# perdas) constam dos artigos setoriais do Reg. 2024/2690 e/ou de instrução
# técnica do CNCS, e carecem de confirmação. Os campos quantitativos abaixo são
# tratados como evidência de suporte ao critério (a)/(b), não como gatilhos
# automáticos com limiar fixo.
# ---------------------------------------------------------------------------


@dataclass
class SignificanceCriteria:
    perturbacao_operacional_grave: bool = False  # critério (a)
    afeta_outras_entidades: bool = False  # critério (b) — danos a terceiros
    perdas_financeiras_eur: float = 0.0  # suporte ao critério (a)
    utilizadores_afetados: int = 0  # suporte
    indisponibilidade_horas: float = 0.0  # suporte
    suspeita_ato_ilicito: bool = False  # aciona conteúdo do alerta precoce
    impacto_transfronteirico: bool = False  # aciona conteúdo do alerta precoce
    incidente_recorrente: bool = False  # suporte


@dataclass
class SignificanceVerdict:
    significativo: bool
    criterios_acionados: list[str]
    fundamentacao: str
    obriga_alerta_precoce: bool
    aciona_rgpd: bool


def assess_significance(
    criteria: SignificanceCriteria, dados_pessoais_envolvidos: bool = False
) -> SignificanceVerdict:
    """Determina se um incidente tem impacto significativo nos termos do
    art. 3.º do Reg. de Execução (UE) 2024/2690, devolvendo um veredicto
    fundamentado. Sinaliza também se obriga a alerta precoce (24h, por suspeita
    de ato ilícito ou impacto transfronteiriço) e se aciona o regime do RGPD
    (notificação à CNPD) por envolver dados pessoais."""
    criterios: list[str] = []

    if criteria.perturbacao_operacional_grave:
        criterios.append("(a) Perturbação operacional grave dos serviços")
    if criteria.perdas_financeiras_eur > 0:
        criterios.append(
            f"(a) Perdas financeiras para a entidade ({criteria.perdas_financeiras_eur:.0f} €)"
        )
    if criteria.afeta_outras_entidades:
        criterios.append("(b) Danos materiais/imateriais consideráveis a terceiros")

    suporte: list[str] = []
    if criteria.utilizadores_afetados > 0:
        suporte.append(f"{criteria.utilizadores_afetados} utilizadores afetados")
    if criteria.indisponibilidade_horas > 0:
        suporte.append(f"{criteria.indisponibilidade_horas:g} h de indisponibilidade")
    if criteria.incidente_recorrente:
        suporte.append("incidente recorrente")

    significativo = bool(criterios)

    if significativo:
        fundamentacao = (
            "Incidente considerado SIGNIFICATIVO: cumpre pelo menos um critério geral do "
            "art. 3.º do Reg. (UE) 2024/2690. Deve seguir o regime de notificação ao CNCS "
            "(alerta inicial 24h, notificação 72h, relatório final 1 mês). "
            "Confirmar os limiares quantitativos setoriais aplicáveis."
        )
    else:
        fundamentacao = (
            "Sem critério geral acionado com os dados fornecidos — NÃO determinado como "
            "significativo. Reavaliar à medida que o impacto se concretize; em caso de dúvida, "
            "tratar como significativo e notificar."
        )
    if suporte:
        fundamentacao += " Indicadores de suporte: " + "; ".join(suporte) + "."

    return SignificanceVerdict(
        significativo=significativo,
        criterios_acionados=criterios,
        fundamentacao=fundamentacao,
        obriga_alerta_precoce=criteria.suspeita_ato_ilicito or criteria.impacto_transfronteirico,
        aciona_rgpd=dados_pessoais_envolvidos,
    )
