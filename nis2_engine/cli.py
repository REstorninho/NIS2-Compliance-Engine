from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .assessment import run_assessment
from .audit import build_audit_report
from .classification import classify_entity, required_compliance_level
from .loader import load_controls
from .models import AssessmentAnswer, ComplianceLevel, Entity, EntityType
from .reporting import (
    render_audit_report,
    render_bcdr_policy,
    render_gap_report,
    render_incident_response_policy,
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

    print(f"Entidade:       {entity.name} ({entity_type.value}, nível {target_level.value})")
    print(f"Conformidade:   {result.score_pct}% (maturidade média: {result.maturity_score_pct}%)")
    print(f"Gaps abertos:   {sum(1 for g in result.gaps if not g.implemented)}")
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
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nis2",
        description="Motor de conformidade NIS2 (DL 125/2025 + Regulamento 756/2026).",
    )
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
    p_assess.set_defaults(func=cmd_assess)

    p_policies = sub.add_parser("policies", help="Gera o pacote de políticas chave (resposta a incidentes, fornecedores, BC/DR).")
    p_policies.add_argument("entity", help="Ficheiro YAML com o perfil da entidade.")
    p_policies.add_argument("-o", "--output", default="out/politicas", help="Diretório de saída (default: ./out/politicas).")
    p_policies.add_argument("--approver", default="", help="Nome do responsável que aprova as políticas.")
    p_policies.set_defaults(func=cmd_policies)

    p_audit = sub.add_parser("audit", help="Gera o relatório de rastreabilidade jurídica (controlos confirmados vs. por validar).")
    p_audit.add_argument("-o", "--output", help="Caminho para escrever o relatório de auditoria (markdown).")
    p_audit.set_defaults(func=cmd_audit)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
