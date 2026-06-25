"""Demonstração end-to-end: classificação -> assessment -> deliverables
(gap report, Statement of Applicability, alerta de incidente 24h/72h).

Uso: python examples/demo_deliverables.py
"""
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from nis2_engine import (
    Entity,
    IncidentNotification,
    build_statement_of_applicability,
    compute_deadlines,
    load_controls,
    render_gap_report,
    run_assessment,
)
from nis2_engine.classification import classify_entity, required_compliance_level
from nis2_engine.models import AssessmentAnswer

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "deliverables"
ENV = Environment(loader=FileSystemLoader(TEMPLATES_DIR))


def _print_section(title: str) -> None:
    print(f"\n{'=' * 80}\n{title}\n{'=' * 80}\n")


def main() -> None:
    # Nota: "turismo" não consta dos Anexos I/II do DL 125/2025 (ver
    # nis2_engine/classification.py), por isso o exemplo usa uma câmara
    # municipal — relevante para o mercado autárquico do Algarve, e
    # diretamente em âmbito como entidade pública relevante.
    entity = Entity(
        name="Câmara Municipal de Exemplo",
        sector="administracao_publica",
        employees=300,
        annual_turnover_eur=0,
        is_public_body=True,
    )

    entity_type = classify_entity(entity)
    target_level = required_compliance_level(entity_type)
    controls = load_controls()

    # Simula respostas parciais ao questionário de maturidade.
    answers = [
        AssessmentAnswer(control_id="GOV-01", implemented=True),
        AssessmentAnswer(control_id="IDN-01", implemented=True),
        AssessmentAnswer(control_id="PRT-01", implemented=False),
    ]
    result = run_assessment(entity, target_level, controls, answers)

    _print_section("1. Gap Report")
    print(render_gap_report(result))

    _print_section("2. Statement of Applicability")
    soa = build_statement_of_applicability(result, controls)
    print(ENV.get_template("soa.md.j2").render(soa=soa, generated_at=datetime.now().strftime("%Y-%m-%d")))

    _print_section("3. Alerta inicial de incidente (24h/72h)")
    incident = IncidentNotification(
        incident_id="INC-2026-001",
        entity=entity,
        detected_at=datetime(2026, 6, 24, 9, 0),
        severity="alto",
        description="Acesso não autorizado detetado num servidor de email institucional.",
        affected_systems=["Servidor de email (Exchange on-prem)"],
        cross_border_effect=False,
    )
    deadlines = compute_deadlines(incident)
    print(ENV.get_template("incident_alert_24h.md.j2").render(incident=incident, deadlines=deadlines))


if __name__ == "__main__":
    main()
