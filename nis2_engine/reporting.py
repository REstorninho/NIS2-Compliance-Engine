from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .incident import NotificationDeadlines, compute_deadlines
from .models import (
    MATURITY_LABELS,
    AssessmentResult,
    Entity,
    EntityType,
    IncidentNotification,
    StatementOfApplicability,
)
from .roadmap import RemediationRoadmap

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "deliverables"
_POLICIES_DIR = Path(__file__).resolve().parent.parent / "templates" / "policies"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        autoescape=select_autoescape(enabled_extensions=(), default=False),
        trim_blocks=False,
        lstrip_blocks=False,
    )


def _policy_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_POLICIES_DIR),
        autoescape=select_autoescape(enabled_extensions=(), default=False),
        trim_blocks=False,
        lstrip_blocks=False,
    )


def _render_policy(template_name: str, entity: Entity, approver: str = "", generated_at: str | None = None) -> str:
    generated_at = generated_at or datetime.now().strftime("%Y-%m-%d")
    return _policy_env().get_template(template_name).render(entity=entity, approver=approver, generated_at=generated_at)


def render_incident_response_policy(entity: Entity, approver: str = "", generated_at: str | None = None) -> str:
    return _render_policy("politica_resposta_incidentes.md.j2", entity, approver, generated_at)


def render_supplier_security_policy(entity: Entity, approver: str = "", generated_at: str | None = None) -> str:
    return _render_policy("politica_seguranca_fornecedores.md.j2", entity, approver, generated_at)


def render_bcdr_policy(entity: Entity, approver: str = "", generated_at: str | None = None) -> str:
    return _render_policy("politica_continuidade_bcdr.md.j2", entity, approver, generated_at)


def render_gap_report(result: AssessmentResult) -> str:
    return _env().get_template("gap_report.md.j2").render(result=result, maturity_labels=MATURITY_LABELS)


def render_roadmap(roadmap: RemediationRoadmap) -> str:
    return _env().get_template("roadmap.md.j2").render(roadmap=roadmap)


def render_soa(soa: StatementOfApplicability, generated_at: str | None = None) -> str:
    generated_at = generated_at or datetime.now().strftime("%Y-%m-%d")
    return _env().get_template("soa.md.j2").render(soa=soa, generated_at=generated_at)


def render_incident_alert(incident: IncidentNotification, deadlines: NotificationDeadlines | None = None) -> str:
    deadlines = deadlines or compute_deadlines(incident)
    return _env().get_template("incident_alert_24h.md.j2").render(incident=incident, deadlines=deadlines)


def render_incident_report(incident: IncidentNotification, deadlines: NotificationDeadlines | None = None) -> str:
    deadlines = deadlines or compute_deadlines(incident)
    return _env().get_template("incident_report_72h.md.j2").render(incident=incident, deadlines=deadlines)


def render_self_identification(
    entity: Entity,
    entity_type: EntityType,
    target_level,
    generated_at: str | None = None,
) -> str:
    generated_at = generated_at or datetime.now().strftime("%Y-%m-%d")
    return _env().get_template("self_identification.md.j2").render(
        entity=entity,
        entity_type=entity_type,
        target_level=target_level,
        generated_at=generated_at,
    )
