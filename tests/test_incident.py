from datetime import datetime, timedelta

from nis2_engine import (
    Entity,
    IncidentNotification,
    SignificanceCriteria,
    assess_significance,
    compute_deadlines,
    render_incident_end_of_impact,
    render_incident_final_report,
)


def _make_incident(detected_at: datetime) -> IncidentNotification:
    entity = Entity(name="Operador Energético", sector="energia", employees=200, annual_turnover_eur=50_000_000)
    return IncidentNotification(
        incident_id="INC-2026-001",
        entity=entity,
        detected_at=detected_at,
        severity="alto",
        description="Acesso não autorizado detetado em servidor crítico.",
    )


def test_alerta_inicial_is_24h_after_detection():
    detected_at = datetime(2026, 6, 24, 10, 0)
    incident = _make_incident(detected_at)
    deadlines = compute_deadlines(incident)
    assert deadlines.alerta_inicial == detected_at + timedelta(hours=24)


def test_relatorio_detalhado_is_72h_after_detection():
    detected_at = datetime(2026, 6, 24, 10, 0)
    incident = _make_incident(detected_at)
    deadlines = compute_deadlines(incident)
    assert deadlines.relatorio_detalhado == detected_at + timedelta(hours=72)


def test_relatorio_final_is_30_days_after_detection():
    detected_at = datetime(2026, 6, 24, 10, 0)
    incident = _make_incident(detected_at)
    deadlines = compute_deadlines(incident)
    assert deadlines.relatorio_final == detected_at + timedelta(days=30)


def test_time_remaining_is_negative_after_deadline_passed():
    detected_at = datetime(2026, 6, 1, 10, 0)
    incident = _make_incident(detected_at)
    deadlines = compute_deadlines(incident)
    now = datetime(2026, 6, 24, 10, 0)
    assert deadlines.time_remaining("alerta_inicial", now) < timedelta(0)


def test_significance_general_criteria_a_triggers():
    verdict = assess_significance(SignificanceCriteria(perturbacao_operacional_grave=True))
    assert verdict.significativo is True
    assert any("(a)" in c for c in verdict.criterios_acionados)


def test_significance_criteria_b_third_parties_triggers():
    verdict = assess_significance(SignificanceCriteria(afeta_outras_entidades=True))
    assert verdict.significativo is True
    assert any("(b)" in c for c in verdict.criterios_acionados)


def test_significance_not_triggered_without_general_criteria():
    verdict = assess_significance(SignificanceCriteria(utilizadores_afetados=10))
    assert verdict.significativo is False


def test_early_warning_and_rgpd_flags():
    verdict = assess_significance(
        SignificanceCriteria(suspeita_ato_ilicito=True), dados_pessoais_envolvidos=True
    )
    assert verdict.obriga_alerta_precoce is True
    assert verdict.aciona_rgpd is True


def test_significant_impact_duration_is_hours_between_detection_and_end():
    detected_at = datetime(2026, 6, 24, 10, 0)
    incident = _make_incident(detected_at)
    assert incident.significant_impact_duration_hours() is None
    incident.significant_impact_ended_at = detected_at + timedelta(hours=30, minutes=30)
    assert incident.significant_impact_duration_hours() == 30.5


def test_render_end_of_impact_includes_article_43_and_duration():
    detected_at = datetime(2026, 6, 24, 10, 0)
    incident = _make_incident(detected_at)
    incident.significant_impact_ended_at = detected_at + timedelta(hours=12)
    incident.status = "encerrado"
    md = render_incident_end_of_impact(incident)
    assert "Art. 43" in md
    assert "Fim do Impacto Significativo" in md
    assert "12.0 h" in md


def test_render_final_report_is_intercalar_while_open_and_final_when_closed():
    detected_at = datetime(2026, 6, 24, 10, 0)
    incident = _make_incident(detected_at)
    incident.threat_type = "Ransomware"
    incident.lessons_learned = "Reforçar MFA."
    open_md = render_incident_final_report(incident)
    assert "Art. 44" in open_md
    assert "INTERCALAR" in open_md
    assert "Ransomware" in open_md
    assert "Reforçar MFA." in open_md

    incident.status = "encerrado"
    final_md = render_incident_final_report(incident)
    assert "FINAL" in final_md
