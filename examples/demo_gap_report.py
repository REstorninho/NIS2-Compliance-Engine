"""Demonstração end-to-end: classificação -> assessment -> relatório.

Uso: python examples/demo_gap_report.py
"""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from nis2_engine import Entity, load_controls, run_assessment
from nis2_engine.classification import classify_entity, required_compliance_level
from nis2_engine.models import AssessmentAnswer

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "deliverables"


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

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("gap_report.md.j2")
    print(template.render(result=result))


if __name__ == "__main__":
    main()
