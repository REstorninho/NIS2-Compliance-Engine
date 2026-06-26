from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .assessment import PRIORITY_BY_FUNCTION
from .audit import VALIDATION_CHECKLIST_FIELDS, AuditReport
from .charts import QNRCS_FUNCTION_ORDER, render_maturity_radar_svg
from .classification import SETORES_ESSENCIAIS, SETORES_IMPORTANTES
from .history import ProgressDelta
from .incident import NotificationDeadlines, compute_deadlines
from .iso27001 import ISO27001_MANDATORY_DOCUMENTS, ISO27001Crosswalk
from .loader import load_controls
from .models import (
    MATURITY_IMPLEMENTED_THRESHOLD,
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
from .risk_matrix import (
    DIMENSAO_FATOR,
    LIMIAR_ELEVADO,
    LIMIAR_SUBSTANCIAL,
    TIPO_SETOR_FATOR,
)
from .roadmap import PHASES_BY_PRIORITY, PHASE_ORDER, RemediationRoadmap

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
        "controls": [
            {
                "id": c.id,
                "title": c.title,
                "fn": c.qnrcs_function,
                "levels": {
                    "basico": bool(c.levels.get("basico")),
                    "substancial": bool(c.levels.get("substancial")),
                    "elevado": bool(c.levels.get("elevado")),
                },
            }
            for c in sorted(load_controls(), key=lambda c: c.id)
        ],
        "priority_by_function": dict(PRIORITY_BY_FUNCTION),
        "radar_order": list(QNRCS_FUNCTION_ORDER),
        "maturity_threshold": MATURITY_IMPLEMENTED_THRESHOLD,
        "maturity_labels": {str(k): v for k, v in MATURITY_LABELS.items()},
        "phases": [
            {"priority": p, "name": PHASES_BY_PRIORITY[p][0], "timeframe": PHASES_BY_PRIORITY[p][1]}
            for p in sorted(PHASES_BY_PRIORITY, key=lambda p: PHASE_ORDER[p])
        ],
        # Matriz de Risco (Anexo II) — fonte de verdade para o cálculo no browser.
        "risk": {
            "dimensao_fator": DIMENSAO_FATOR,
            "tipo_setor_fator": TIPO_SETOR_FATOR,
            "limiar_substancial": LIMIAR_SUBSTANCIAL,
            "limiar_elevado": LIMIAR_ELEVADO,
            "dimensao_bands": {
                "grande_emp": 250,
                "grande_turn": 50_000_000,
                "media_emp": SIZE_THRESHOLD_EMPLOYEES,
                "media_turn": SIZE_THRESHOLD_TURNOVER_EUR,
            },
            "level_order": {"basico": 0, "substancial": 1, "elevado": 2},
        },
    }


def render_classifier_form(brand: str = "") -> str:
    """Gera um formulário HTML self-contained (sem servidor, sem dependências
    externas) que classifica a entidade quanto ao âmbito NIS2 em tempo real no
    browser, replicando `classify_entity`, e mantém um histórico local
    (localStorage) com exportação para YAML (alimenta a CLI) e CSV."""
    config = build_classifier_config()
    config["brand"] = brand or "REGENTE"
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


def render_risk_matrix(matrix) -> str:
    """Relatório da Matriz de Risco (Anexo II): cenários, valor total, nível
    pela matriz, nível de referência e nível efetivo (agregação art. 30.º)."""
    return _env().get_template("risk_matrix.md.j2").render(matrix=matrix)


def render_significance_triage(incident: IncidentNotification, verdict) -> str:
    """Relatório de triagem de impacto significativo (Reg. UE 2024/2690)."""
    return _env().get_template("significance_triage.md.j2").render(incident=incident, verdict=verdict)


def render_deadlines(entity_name: str, reference_date, obligations: list, today=None) -> str:
    """Calendário de obrigações NIS2 da entidade, com o estado de cada prazo."""
    from datetime import date

    today = today or date.today()
    estado_icon = {"vencido": "🔴", "a_vencer": "🟠", "futuro": "🟢"}
    return _env().get_template("deadlines.md.j2").render(
        entity_name=entity_name,
        reference_date=reference_date,
        today=today,
        today_date=today,
        obligations=obligations,
        estado_icon=estado_icon,
    )


def render_portfolio(entries: list, generated_at: str | None = None) -> str:
    """Vista agregada da carteira de clientes (um cliente por linha)."""
    generated_at = generated_at or datetime.now().strftime("%Y-%m-%d")
    return _env().get_template("portfolio.md.j2").render(entries=entries, generated_at=generated_at)


def render_iso27001_crosswalk(crosswalk: ISO27001Crosswalk) -> str:
    """Relatório de crosswalk dual NIS2 ↔ ISO/IEC 27001/27002:2022, gerado a
    partir de um assessment já calculado (ver `build_iso27001_crosswalk`)."""
    return _env().get_template("iso27001_crosswalk.md.j2").render(crosswalk=crosswalk)


def render_iso27001_document_checklist(entity: Entity, generated_at: str | None = None) -> str:
    """Checklist dos documentos mínimos exigidos por um SGSI certificável
    segundo a ISO/IEC 27001:2022, complementar à SoA já gerada para NIS2."""
    generated_at = generated_at or datetime.now().strftime("%Y-%m-%d")
    return _env().get_template("iso27001_document_checklist.md.j2").render(
        entity=entity,
        generated_at=generated_at,
        documents=ISO27001_MANDATORY_DOCUMENTS,
    )


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
