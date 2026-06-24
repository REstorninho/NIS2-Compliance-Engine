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
