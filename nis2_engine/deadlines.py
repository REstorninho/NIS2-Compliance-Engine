from __future__ import annotations

from dataclasses import dataclass
from datetime import date


def _add_months(d: date, months: int) -> date:
    """Soma `months` meses a uma data, ajustando o dia ao último dia do mês
    quando necessário (ex.: 31 jan + 1 mês → 28/29 fev)."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    # Último dia do mês de destino.
    if month == 12:
        last_day = 31
    else:
        last_day = (date(year, month + 1, 1) - date(year, month, 1)).days
    return date(year, month, min(d.day, last_day))


def _next_31_january(ref: date) -> date:
    """Primeiro 31 de janeiro estritamente posterior a `ref`."""
    candidate = date(ref.year, 1, 31)
    if candidate <= ref:
        candidate = date(ref.year + 1, 1, 31)
    return candidate


# Janela de antecedência (dias) a partir da qual uma obrigação ainda futura é
# sinalizada como "a vencer".
ALERTA_ANTECEDENCIA_DIAS = 30


@dataclass
class Obligation:
    nome: str
    base_legal: str
    due_date: date
    descricao: str = ""
    recorrencia: str = ""  # ex.: "anual", "única"

    def estado(self, today: date) -> str:
        if self.due_date < today:
            return "vencido"
        if (self.due_date - today).days <= ALERTA_ANTECEDENCIA_DIAS:
            return "a_vencer"
        return "futuro"


def build_obligations_calendar(
    entity_name: str,
    reference_date: date,
    today: date | None = None,
) -> list[Obligation]:
    """Gera o calendário de obrigações de uma entidade abrangida, a partir da
    data de qualificação/notificação (`reference_date`).

    NOTA DE VALIDAÇÃO: os prazos exatos (janela de designação do responsável, e
    a regra '31 de janeiro ou 6 meses' do art. 32.º) devem ser confirmados
    contra o DL 125/2025 e o Regulamento n.º 756/2026 publicados. As datas
    abaixo são uma leitura operacional de apoio ao planeamento."""
    today = today or date.today()

    # Art. 32.º — lista de ativos publicamente acessíveis: versão inicial até
    # 31 de janeiro OU 6 meses após notificação (leitura: a data mais favorável
    # à entidade, i.e. a mais tardia das duas).
    lista_ativos_due = max(_next_31_january(reference_date), _add_months(reference_date, 6))

    obligations = [
        Obligation(
            nome="Designação de responsável de cibersegurança e ponto de contacto permanente",
            base_legal="DL 125/2025 (designação/comunicação ao CNCS)",
            due_date=_add_months(reference_date, 3),
            descricao="Comunicar ao CNCS o responsável de cibersegurança e o ponto de contacto "
            "permanente. Prazo exato a confirmar contra o texto oficial.",
            recorrencia="única",
        ),
        Obligation(
            nome="Lista de ativos publicamente acessíveis (versão inicial)",
            base_legal="Art. 32.º",
            due_date=lista_ativos_due,
            descricao="Versão inicial até 31 de janeiro ou 6 meses após notificação. "
            "INFORMAÇÃO CLASSIFICADA DE GRAU RESERVADO — tratar com a confidencialidade devida.",
            recorrencia="anual",
        ),
        Obligation(
            nome="Relatório anual de cibersegurança",
            base_legal="DL 125/2025 (reporte periódico)",
            due_date=_add_months(reference_date, 12),
            descricao="Reporte anual; recorre na data de aniversário da qualificação. "
            "Prazo exato a confirmar contra o texto oficial.",
            recorrencia="anual",
        ),
    ]
    return sorted(obligations, key=lambda o: o.due_date)
