from datetime import date

from nis2_engine import build_obligations_calendar
from nis2_engine.deadlines import _add_months, _next_31_january


def test_add_months_handles_month_end():
    assert _add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert _add_months(date(2026, 3, 1), 6) == date(2026, 9, 1)
    assert _add_months(date(2026, 12, 15), 1) == date(2027, 1, 15)


def test_next_31_january_is_strictly_after():
    assert _next_31_january(date(2026, 3, 1)) == date(2027, 1, 31)
    assert _next_31_january(date(2026, 1, 1)) == date(2026, 1, 31)
    assert _next_31_january(date(2026, 1, 31)) == date(2027, 1, 31)


def test_calendar_has_core_obligations_with_states():
    obligations = build_obligations_calendar("Câmara X", date(2026, 3, 1), today=date(2026, 7, 1))
    nomes = [o.nome for o in obligations]
    assert any("Lista de ativos" in n for n in nomes)
    assert any("Relatório anual" in n for n in nomes)
    assert any("responsável de cibersegurança" in n for n in nomes)
    # Ordenado por data crescente.
    assert obligations == sorted(obligations, key=lambda o: o.due_date)


def test_obligation_state_buckets():
    obligations = build_obligations_calendar("Câmara X", date(2026, 3, 1), today=date(2026, 7, 1))
    designacao = next(o for o in obligations if "responsável" in o.nome)
    # Designação a 3 meses (2026-06-01) já está vencida a 2026-07-01.
    assert designacao.estado(date(2026, 7, 1)) == "vencido"
