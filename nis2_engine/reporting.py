from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .audit import VALIDATION_CHECKLIST_FIELDS, AuditReport
from .charts import render_maturity_radar_svg
from .classification import SETORES_ESSENCIAIS, SETORES_IMPORTANTES
from .history import ProgressDelta
from .incident import NotificationDeadlines, compute_deadlines
from .models import (
    MATURITY_LABELS,
    SIZE_THRESHOLD_EMPLOYEES,
    SIZE_THRESHOLD_TURNOVER_EUR,
    AssessmentResult,
    ComplianceLevel,
    Entity,
    EntityType,
    IncidentNotification,
    StatementOfApplicability,
)
from .roadmap import RemediationRoadmap

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "deliverables"
_POLICIES_DIR = Path(__file__).resolve().parent.parent / "templates" / "policies"
_WEB_DIR = Path(__file__).resolve().parent.parent / "templates" / "web"


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


def _web_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_WEB_DIR),
        autoescape=select_autoescape(enabled_extensions=(), default=False),
        trim_blocks=False,
        lstrip_blocks=False,
    )


# Rótulos legíveis para os setores do âmbito NIS2 (apresentação no formulário).
_SECTOR_LABELS = {
    "energia": "Energia",
    "transportes": "Transportes",
    "banca": "Banca",
    "infraestruturas_mercado_financeiro": "Infraestruturas do mercado financeiro",
    "saude": "Saúde",
    "agua_potavel": "Água potável",
    "aguas_residuais": "Águas residuais",
    "infraestrutura_digital": "Infraestrutura digital",
    "gestao_servicos_tic": "Gestão de serviços TIC",
    "administracao_publica": "Administração pública",
    "espaco": "Espaço",
    "servicos_postais": "Serviços postais",
    "gestao_residuos": "Gestão de resíduos",
    "quimicos": "Produtos químicos",
    "alimentacao": "Produção/distribuição alimentar",
    "fabricacao": "Fabricação",
    "servicos_digitais": "Prestadores de serviços digitais",
    "investigacao": "Investigação",
}


def build_classifier_config() -> dict:
    """Monta a configuração que o formulário HTML injeta no browser, a partir
    da fonte de verdade do motor (listas de setores, limiares de dimensão e
    mapeamento de nível). Garante que o formulário nunca diverge de
    `classify_entity`/`required_compliance_level`."""
    essenciais = sorted(SETORES_ESSENCIAIS)
    importantes = sorted(SETORES_IMPORTANTES)
    sectors = [
        {"value": s, "label": _SECTOR_LABELS.get(s, s), "grupo": "essencial"} for s in essenciais
    ] + [
        {"value": s, "label": _SECTOR_LABELS.get(s, s), "grupo": "importante"} for s in importantes
    ]
    sectors.append({"value": "outro", "label": "Outro / não listado", "grupo": "fora de âmbito"})
    return {
        "essenciais": essenciais,
        "importantes": importantes,
        "size_employees": SIZE_THRESHOLD_EMPLOYEES,
        "size_turnover": SIZE_THRESHOLD_TURNOVER_EUR,
        "sectors": sectors,
        "sectorHints": {
            "outro": "Setor fora dos Anexos I/II — em princípio fora de âmbito por classificação direta.",
        },
        "level_mapping": {
            EntityType.ESSENCIAL.value: ComplianceLevel.ELEVADO.value,
            EntityType.IMPORTANTE.value: ComplianceLevel.SUBSTANCIAL.value,
            EntityType.ENTIDADE_PUBLICA_RELEVANTE.value: ComplianceLevel.ELEVADO.value,
            EntityType.FORA_DE_AMBITO.value: "",
        },
    }


def render_classifier_form(brand: str = "") -> str:
    """Gera um formulário HTML self-contained (sem servidor, sem dependências
    externas) que classifica a entidade quanto ao âmbito NIS2 em tempo real no
    browser, replicando `classify_entity`, e mantém um histórico local
    (localStorage) com exportação para YAML (alimenta a CLI) e CSV."""
    config = build_classifier_config()
    return _web_env().get_template("classifier_form.html.j2").render(
        brand=brand or "REGENTE",
        config_json=json.dumps(config, ensure_ascii=False),
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


def render_audit_report(report: AuditReport, generated_at: str | None = None) -> str:
    generated_at = generated_at or datetime.now().strftime("%Y-%m-%d")
    return _env().get_template("audit_report.md.j2").render(report=report, generated_at=generated_at)


def render_validation_checklist_csv(rows: list[dict[str, str]]) -> str:
    """Serializa o checklist de validação jurídica manual (ver
    `audit.build_validation_checklist`) como CSV, pronto a abrir em
    Excel/Sheets para um revisor preencher contra o texto oficial do DRE."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=VALIDATION_CHECKLIST_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def render_progress_report(delta: ProgressDelta) -> str:
    return _env().get_template("progress_report.md.j2").render(delta=delta)


def render_evidence_plan(result: AssessmentResult) -> str:
    return _env().get_template("evidence_plan.md.j2").render(result=result)


def render_maturity_radar(result: AssessmentResult) -> str:
    """Devolve um gráfico radar SVG (sem dependências) da maturidade média por
    função QNRCS — pronto a embeber em HTML/markdown ou a gravar como .svg."""
    return render_maturity_radar_svg(result.maturity_by_function)


def render_html_report(
    result: AssessmentResult,
    entity_type: EntityType,
    brand: str = "",
    generated_at: str | None = None,
) -> str:
    """Relatório HTML self-contained (radar embebido, sumário e gaps), imprimível
    para PDF a partir de qualquer browser, com marca do consultor configurável."""
    generated_at = generated_at or datetime.now().strftime("%Y-%m-%d")
    return _env().get_template("report.html.j2").render(
        result=result,
        entity_type=entity_type,
        radar_svg=render_maturity_radar_svg(result.maturity_by_function),
        brand=brand or "Relatório de Cibersegurança",
        generated_at=generated_at,
    )


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
