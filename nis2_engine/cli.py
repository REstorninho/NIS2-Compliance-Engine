from __future__ import annotations

import argparse
import sys
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import yaml
from jsonschema.exceptions import ValidationError

from .assessment import run_assessment
from .audit import build_audit_report, build_validation_checklist
from .classification import classify_entity, required_compliance_level
from .history import build_snapshot, compare_snapshots, load_snapshots, save_snapshot
from .incident import compute_deadlines
from .loader import load_controls
from .models import AssessmentAnswer, ComplianceLevel, Entity, EntityType, IncidentNotification
from .reporting import (
    render_audit_report,
    render_validation_checklist_csv,
    render_bcdr_policy,
    render_evidence_plan,
    render_gap_report,
    render_html_report,
    render_incident_alert,
    render_incident_report,
    render_incident_response_policy,
    render_maturity_radar,
    render_progress_report,
    render_roadmap,
    render_self_identification,
    render_soa,
    render_supplier_security_policy,
)
from .roadmap import build_remediation_roadmap
from .soa import build_statement_of_applicability


def load_entity(path: Path) -> Entity:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Entity(
        name=raw["name"],
        sector=raw["sector"],
        employees=int(raw["employees"]),
        annual_turnover_eur=float(raw["annual_turnover_eur"]),
        is_public_body=bool(raw.get("is_public_body", False)),
        is_dns_tld_or_trust_service_provider=bool(raw.get("is_dns_tld_or_trust_service_provider", False)),
    )


def load_answers(path: Path) -> list[AssessmentAnswer]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(raw, list):
        answers_raw = raw
    else:
        answers_raw = raw.get("answers", [])
    answers: list[AssessmentAnswer] = []
    for item in answers_raw:
        maturity_raw = item.get("maturity")
        answers.append(
            AssessmentAnswer(
                control_id=item["control_id"],
                implemented=bool(item.get("implemented", False)),
                notes=item.get("notes", ""),
                evidence_ref=item.get("evidence_ref"),
                maturity=int(maturity_raw) if maturity_raw is not None else None,
            )
        )
    return answers


def load_incident(path: Path, entity: Entity) -> IncidentNotification:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return IncidentNotification(
        incident_id=raw["incident_id"],
        entity=entity,
        detected_at=datetime.fromisoformat(str(raw["detected_at"])),
        severity=raw["severity"],
        description=raw.get("description", ""),
        affected_systems=raw.get("affected_systems", []),
        impact_summary=raw.get("impact_summary", ""),
        indicators_of_compromise=raw.get("indicators_of_compromise", []),
        cross_border_effect=bool(raw.get("cross_border_effect", False)),
        root_cause=raw.get("root_cause", ""),
        mitigation_actions=raw.get("mitigation_actions", []),
        status=raw.get("status", "em_curso"),
    )


def _resolve_target_level(entity: Entity, entity_type: EntityType, override: str | None) -> ComplianceLevel:
    if override:
        return ComplianceLevel(override)
    return required_compliance_level(entity_type)


def cmd_classify(args: argparse.Namespace) -> int:
    entity = load_entity(Path(args.entity))
    entity_type = classify_entity(entity)

    print(f"Entidade:       {entity.name}")
    print(f"Classificação:  {entity_type.value}")
    if entity_type is not EntityType.FORA_DE_AMBITO:
        level = required_compliance_level(entity_type)
        print(f"Nível exigido:  {level.value}")
    else:
        print("Nível exigido:  (fora de âmbito)")

    if args.output:
        target_level = None if entity_type is EntityType.FORA_DE_AMBITO else required_compliance_level(entity_type)
        report = render_self_identification(entity, entity_type, target_level)
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"\nRelatório de autoidentificação escrito em: {args.output}")
    return 0


def cmd_scaffold(args: argparse.Namespace) -> int:
    """Gera um ficheiro de respostas em branco com os controlos exigidos para o
    nível-alvo da entidade — pronto para o consultor preencher."""
    entity = load_entity(Path(args.entity))
    entity_type = classify_entity(entity)
    if entity_type is EntityType.FORA_DE_AMBITO:
        print("Entidade fora de âmbito — não há questionário a gerar.", file=sys.stderr)
        return 1

    target_level = _resolve_target_level(entity, entity_type, args.level)
    controls = load_controls()
    required = [c for c in controls if c.required_at(target_level)]

    scaffold = {
        "entity": entity.name,
        "target_level": target_level.value,
        "answers": [
            {
                "control_id": c.id,
                "title": c.title,
                "qnrcs_function": c.qnrcs_function,
                "implemented": False,
                "maturity": 0,  # 0-5: 0=Inexistente, 1=Inicial, 2=Em desenvolvimento, 3=Definido, 4=Gerido, 5=Otimizado
                "notes": "",
            }
            for c in required
        ],
    }
    out = yaml.safe_dump(scaffold, allow_unicode=True, sort_keys=False)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"Questionário ({len(required)} controlos) escrito em: {args.output}")
    else:
        print(out)
    return 0


def cmd_assess(args: argparse.Namespace) -> int:
    entity = load_entity(Path(args.entity))
    entity_type = classify_entity(entity)
    if entity_type is EntityType.FORA_DE_AMBITO:
        print("Entidade fora de âmbito — sem nível de conformidade exigido.", file=sys.stderr)
        return 1

    target_level = _resolve_target_level(entity, entity_type, args.level)
    controls = load_controls()
    answers = load_answers(Path(args.answers))
    result = run_assessment(entity, target_level, controls, answers)
    soa = build_statement_of_applicability(result, controls)
    roadmap = build_remediation_roadmap(result)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "gap_report.md").write_text(render_gap_report(result), encoding="utf-8")
    (out_dir / "roadmap.md").write_text(render_roadmap(roadmap), encoding="utf-8")
    (out_dir / "statement_of_applicability.md").write_text(render_soa(soa), encoding="utf-8")
    (out_dir / "self_identification.md").write_text(
        render_self_identification(entity, entity_type, target_level), encoding="utf-8"
    )
    (out_dir / "evidence_plan.md").write_text(render_evidence_plan(result), encoding="utf-8")
    (out_dir / "maturity_radar.svg").write_text(render_maturity_radar(result), encoding="utf-8")
    (out_dir / "report.html").write_text(
        render_html_report(result, entity_type, brand=args.brand), encoding="utf-8"
    )

    print(f"Entidade:       {entity.name} ({entity_type.value}, nível {target_level.value})")
    print(f"Conformidade:   {result.score_pct}% (maturidade média: {result.maturity_score_pct}%)")
    print(f"Gaps abertos:   {sum(1 for g in result.gaps if not g.implemented)}")
    print(f"Deliverables escritos em: {out_dir}/")

    if args.history_dir:
        snapshot = build_snapshot(result)
        snapshot_path = save_snapshot(snapshot, Path(args.history_dir))
        print(f"Snapshot de histórico guardado em: {snapshot_path}")
    return 0


def cmd_progress(args: argparse.Namespace) -> int:
    """Compara os dois assessments mais recentes de uma entidade gravados no
    histórico e gera um relatório de evolução (score, maturidade por função,
    controlos remediados/regredidos)."""
    history_dir = Path(args.history_dir)
    snapshots = load_snapshots(history_dir, args.entity)
    if len(snapshots) < 2:
        print(
            f"Histórico insuficiente para '{args.entity}': {len(snapshots)} snapshot(s) encontrado(s) "
            f"em {history_dir}/ (são necessários pelo menos 2).",
            file=sys.stderr,
        )
        return 1

    old, new = snapshots[-2], snapshots[-1]
    delta = compare_snapshots(old, new)

    print(f"Entidade:              {delta.entity_name}")
    print(f"Período:               {delta.from_date} → {delta.to_date}")
    print(f"Δ Score:               {'+' if delta.score_delta >= 0 else ''}{delta.score_delta} p.p.")
    print(f"Δ Maturidade:          {'+' if delta.maturity_delta >= 0 else ''}{delta.maturity_delta} p.p.")
    print(f"Controlos remediados:  {len(delta.newly_implemented)}")
    print(f"Regressões:            {len(delta.regressed)}")

    if args.output:
        Path(args.output).write_text(render_progress_report(delta), encoding="utf-8")
        print(f"\nRelatório de evolução escrito em: {args.output}")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    """Lista todos os snapshots de assessment gravados para uma entidade, por
    ordem cronológica (data, score de conformidade e maturidade média)."""
    snapshots = load_snapshots(Path(args.history_dir), args.entity)
    if not snapshots:
        print(
            f"Sem snapshots para '{args.entity}' em {args.history_dir}/.",
            file=sys.stderr,
        )
        return 1

    print(f"Histórico de '{args.entity}' ({len(snapshots)} snapshot(s)):\n")
    print(f"{'#':>3}  {'Data':<26}  {'Score':>7}  {'Maturidade':>10}")
    print(f"{'-' * 3}  {'-' * 26}  {'-' * 7}  {'-' * 10}")
    for i, snap in enumerate(snapshots, start=1):
        print(f"{i:>3}  {snap.generated_at:<26}  {snap.score_pct:>6}%  {snap.maturity_score_pct:>9}%")
    return 0


def cmd_incident(args: argparse.Namespace) -> int:
    """Gera os deliverables do regime de notificação de incidentes ao CNCS via
    MyCiber (DL 125/2025, Art. 23): alerta inicial (24h) e relatório detalhado
    (72h), com os prazos calculados a partir da deteção do incidente."""
    entity = load_entity(Path(args.entity))
    incident = load_incident(Path(args.incident), entity)
    deadlines = compute_deadlines(incident)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "alerta_inicial_24h.md").write_text(
        render_incident_alert(incident, deadlines), encoding="utf-8"
    )
    (out_dir / "relatorio_detalhado_72h.md").write_text(
        render_incident_report(incident, deadlines), encoding="utf-8"
    )

    print(f"Incidente:             {incident.incident_id} ({incident.severity})")
    print(f"Detetado em:           {incident.detected_at.isoformat()}")
    print(f"Prazo alerta inicial:  {deadlines.alerta_inicial.isoformat()}")
    print(f"Prazo relatório 72h:   {deadlines.relatorio_detalhado.isoformat()}")
    print(f"Prazo relatório final: {deadlines.relatorio_final.isoformat()}")
    print(f"Deliverables escritos em: {out_dir}/")
    return 0


def cmd_policies(args: argparse.Namespace) -> int:
    """Gera o pacote de políticas/procedimentos chave (evidência documental)
    para a entidade: resposta a incidentes, segurança de fornecedores e
    continuidade de negócio/BC-DR."""
    entity = load_entity(Path(args.entity))

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "politica_resposta_incidentes.md").write_text(
        render_incident_response_policy(entity, approver=args.approver), encoding="utf-8"
    )
    (out_dir / "politica_seguranca_fornecedores.md").write_text(
        render_supplier_security_policy(entity, approver=args.approver), encoding="utf-8"
    )
    (out_dir / "politica_continuidade_bcdr.md").write_text(
        render_bcdr_policy(entity, approver=args.approver), encoding="utf-8"
    )

    print(f"Pacote de políticas para {entity.name} escrito em: {out_dir}/")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """Gera o relatório de rastreabilidade jurídica: que controlos e que
    classificação setorial já foram confirmados artigo-a-artigo contra o
    texto oficial, e o que continua por validar."""
    controls = load_controls()
    report = build_audit_report(controls)

    print(f"Classificação setorial: {report.classification_status} ({report.classification_source})")
    print(f"Controlos confirmados:  {len(report.confirmed_controls)}/{report.total_controls}")
    print(f"Controlos por validar:  {len(report.pending_controls)}/{report.total_controls} ({report.pending_pct}%)")

    if args.output:
        Path(args.output).write_text(render_audit_report(report), encoding="utf-8")
        print(f"\nRelatório de auditoria escrito em: {args.output}")

    if args.checklist:
        rows = build_validation_checklist(controls)
        Path(args.checklist).write_text(render_validation_checklist_csv(rows), encoding="utf-8")
        print(f"Checklist de validação manual (CSV) escrito em: {args.checklist}")
    return 0


def cmd_list_controls(args: argparse.Namespace) -> int:
    """Lista o catálogo de controlos QNRCS, com filtro opcional por nível
    exigido ou função — útil para consultar o que vai ser pedido antes de
    preencher o `entity.yaml`/`answers.yaml`, sem ter de abrir `data/controls/`."""
    controls = load_controls()
    if args.level:
        level = ComplianceLevel(args.level)
        controls = [c for c in controls if c.required_at(level)]
    if args.function:
        controls = [c for c in controls if c.qnrcs_function.lower() == args.function.lower()]
    controls = sorted(controls, key=lambda c: c.id)

    print(f"{'ID':<8} {'Função':<13} {'B/S/E':<6} Título")
    print(f"{'-' * 8} {'-' * 13} {'-' * 6} {'-' * 40}")
    for c in controls:
        niveis = "".join(
            letra if c.levels.get(nivel) else "·"
            for letra, nivel in (("B", "basico"), ("S", "substancial"), ("E", "elevado"))
        )
        print(f"{c.id:<8} {c.qnrcs_function:<13} {niveis:<6} {c.title}")
    print(f"\nTotal: {len(controls)} controlo(s).")
    return 0


def _version_string() -> str:
    try:
        return version("nis2-engine")
    except PackageNotFoundError:
        return "dev"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nis2",
        description="Motor de conformidade NIS2 (DL 125/2025 + Regulamento 756/2026).",
    )
    parser.add_argument("--version", action="version", version=f"nis2 {_version_string()}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_classify = sub.add_parser("classify", help="Classifica a entidade e (opcionalmente) gera o relatório de autoidentificação.")
    p_classify.add_argument("entity", help="Ficheiro YAML com o perfil da entidade.")
    p_classify.add_argument("-o", "--output", help="Caminho para escrever o relatório de autoidentificação (markdown).")
    p_classify.set_defaults(func=cmd_classify)

    p_scaffold = sub.add_parser("scaffold", help="Gera um questionário de maturidade em branco para a entidade.")
    p_scaffold.add_argument("entity", help="Ficheiro YAML com o perfil da entidade.")
    p_scaffold.add_argument("-o", "--output", help="Caminho para escrever o questionário (YAML). Por omissão, stdout.")
    p_scaffold.add_argument("--level", choices=[l.value for l in ComplianceLevel], help="Forçar nível-alvo em vez do derivado da classificação.")
    p_scaffold.set_defaults(func=cmd_scaffold)

    p_assess = sub.add_parser("assess", help="Corre o assessment e gera todos os deliverables.")
    p_assess.add_argument("entity", help="Ficheiro YAML com o perfil da entidade.")
    p_assess.add_argument("answers", help="Ficheiro YAML com as respostas ao questionário.")
    p_assess.add_argument("-o", "--output", default="out", help="Diretório de saída para os deliverables (default: ./out).")
    p_assess.add_argument("--level", choices=[l.value for l in ComplianceLevel], help="Forçar nível-alvo em vez do derivado da classificação.")
    p_assess.add_argument("--history-dir", help="Diretório onde gravar um snapshot deste assessment (para comparação futura com 'nis2 progress').")
    p_assess.add_argument("--brand", default="", help="Nome/marca do consultor a apresentar no relatório HTML.")
    p_assess.set_defaults(func=cmd_assess)

    p_progress = sub.add_parser("progress", help="Compara os dois assessments mais recentes de uma entidade e gera um relatório de evolução.")
    p_progress.add_argument("entity", help="Nome da entidade (igual ao usado no perfil YAML).")
    p_progress.add_argument("--history-dir", required=True, help="Diretório com os snapshots gravados por 'nis2 assess --history-dir'.")
    p_progress.add_argument("-o", "--output", help="Caminho para escrever o relatório de evolução (markdown).")
    p_progress.set_defaults(func=cmd_progress)

    p_history = sub.add_parser("history", help="Lista os snapshots de assessment gravados para uma entidade.")
    p_history.add_argument("entity", help="Nome da entidade (igual ao usado no perfil YAML).")
    p_history.add_argument("--history-dir", required=True, help="Diretório com os snapshots gravados por 'nis2 assess --history-dir'.")
    p_history.set_defaults(func=cmd_history)

    p_incident = sub.add_parser("incident", help="Gera o alerta inicial (24h) e o relatório detalhado (72h) de notificação de um incidente ao CNCS via MyCiber.")
    p_incident.add_argument("entity", help="Ficheiro YAML com o perfil da entidade.")
    p_incident.add_argument("incident", help="Ficheiro YAML com os dados do incidente.")
    p_incident.add_argument("-o", "--output", default="out/incidente", help="Diretório de saída (default: ./out/incidente).")
    p_incident.set_defaults(func=cmd_incident)

    p_policies = sub.add_parser("policies", help="Gera o pacote de políticas chave (resposta a incidentes, fornecedores, BC/DR).")
    p_policies.add_argument("entity", help="Ficheiro YAML com o perfil da entidade.")
    p_policies.add_argument("-o", "--output", default="out/politicas", help="Diretório de saída (default: ./out/politicas).")
    p_policies.add_argument("--approver", default="", help="Nome do responsável que aprova as políticas.")
    p_policies.set_defaults(func=cmd_policies)

    p_audit = sub.add_parser("audit", help="Gera o relatório de rastreabilidade jurídica (controlos confirmados vs. por validar).")
    p_audit.add_argument("-o", "--output", help="Caminho para escrever o relatório de auditoria (markdown).")
    p_audit.add_argument(
        "--checklist",
        help="Caminho para escrever o checklist de validação jurídica manual (CSV), com colunas em "
        "branco para confirmar cada controlo artigo-a-artigo contra o texto oficial do DRE.",
    )
    p_audit.set_defaults(func=cmd_audit)

    p_list_controls = sub.add_parser(
        "list-controls", help="Lista o catálogo de controlos QNRCS (filtrável por nível/função)."
    )
    p_list_controls.add_argument(
        "--level", choices=[l.value for l in ComplianceLevel], help="Filtrar pelos controlos exigidos a este nível."
    )
    p_list_controls.add_argument("--function", help="Filtrar pela função QNRCS (ex.: Governar, Proteger).")
    p_list_controls.set_defaults(func=cmd_list_controls)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"Erro: ficheiro não encontrado — {exc.filename or exc}", file=sys.stderr)
        return 1
    except KeyError as exc:
        print(f"Erro: campo obrigatório em falta no ficheiro YAML — {exc.args[0]}", file=sys.stderr)
        return 1
    except yaml.YAMLError as exc:
        print(f"Erro: YAML inválido — {exc}", file=sys.stderr)
        return 1
    except ValidationError as exc:
        print(f"Erro: controlo não cumpre o schema esperado — {exc.message}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
