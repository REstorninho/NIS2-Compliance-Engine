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
from .deadlines import build_obligations_calendar
from .dossier import build_dossier_html, collect_sections, render_pdf
from .history import build_portfolio, build_snapshot, compare_snapshots, load_snapshots, save_snapshot
from .incident import SignificanceCriteria, assess_significance, compute_deadlines
from .iso27001 import build_iso27001_crosswalk
from .loader import load_controls
from .models import AssessmentAnswer, ComplianceLevel, Entity, EntityType, IncidentNotification
from .profiles import get_profile, load_profiles
from .risk_matrix import RiskScenario, build_risk_matrix, most_demanding
from .reporting import (
    render_audit_report,
    render_classifier_form,
    render_validation_checklist_csv,
    render_bcdr_policy,
    render_evidence_plan,
    render_gap_report,
    render_html_report,
    render_incident_alert,
    render_incident_end_of_impact,
    render_incident_final_report,
    render_incident_report,
    render_incident_response_policy,
    render_iso27001_crosswalk,
    render_iso27001_document_checklist,
    render_deadlines,
    render_maturity_radar,
    render_portfolio,
    render_progress_report,
    render_risk_matrix,
    render_roadmap,
    render_significance_triage,
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
        significant_impact_ended_at=(
            datetime.fromisoformat(str(raw["significant_impact_ended_at"]))
            if raw.get("significant_impact_ended_at")
            else None
        ),
        threat_type=raw.get("threat_type", ""),
        ongoing_mitigation_actions=raw.get("ongoing_mitigation_actions", []),
        lessons_learned=raw.get("lessons_learned", ""),
    )


def load_risk_scenarios(path: Path) -> list[RiskScenario]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    scenarios_raw = raw.get("scenarios", raw) if isinstance(raw, dict) else raw
    scenarios: list[RiskScenario] = []
    for item in scenarios_raw:
        scenarios.append(
            RiskScenario(
                name=item["name"],
                probabilidade=int(item["probabilidade"]),
                impacto=int(item["impacto"]),
                threat_actor=item.get("threat_actor", ""),
                description=item.get("description", ""),
            )
        )
    return scenarios


def _load_significance(raw: dict) -> SignificanceCriteria | None:
    """Lê o bloco opcional `significance` do YAML do incidente."""
    block = raw.get("significance")
    if not block:
        return None
    return SignificanceCriteria(
        perturbacao_operacional_grave=bool(block.get("perturbacao_operacional_grave", False)),
        afeta_outras_entidades=bool(block.get("afeta_outras_entidades", False)),
        perdas_financeiras_eur=float(block.get("perdas_financeiras_eur", 0.0)),
        utilizadores_afetados=int(block.get("utilizadores_afetados", 0)),
        indisponibilidade_horas=float(block.get("indisponibilidade_horas", 0.0)),
        suspeita_ato_ilicito=bool(block.get("suspeita_ato_ilicito", False)),
        impacto_transfronteirico=bool(block.get("impacto_transfronteirico", False)),
        incidente_recorrente=bool(block.get("incidente_recorrente", False)),
    )


def _write_output(path: str | Path, content: str) -> None:
    """Escreve content em path, criando os diretórios pai em falta — evita que
    `-o pasta/que/nao/existe/ficheiro.md` falhe com 'ficheiro não encontrado'."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")


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
        _write_output(args.output, report)
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
        _write_output(args.output, out)
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

    # Nível-alvo: por omissão deriva do tipo de entidade; --level força-o; e
    # --risk computa-o pela Matriz de Risco (Anexo II), aplicando a agregação
    # do art. 30.º (o mais exigente entre matriz e tipo de entidade).
    matrix = None
    if getattr(args, "risk", None):
        nivel_referencia = required_compliance_level(entity_type)
        scenarios = load_risk_scenarios(Path(args.risk))
        matrix = build_risk_matrix(entity, scenarios, nivel_referencia=nivel_referencia)
        target_level = matrix.nivel_efetivo if not args.level else ComplianceLevel(args.level)
    else:
        target_level = _resolve_target_level(entity, entity_type, args.level)

    controls = load_controls()
    answers = load_answers(Path(args.answers))
    result = run_assessment(entity, target_level, controls, answers)
    soa = build_statement_of_applicability(result, controls)
    roadmap = build_remediation_roadmap(result)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    if matrix is not None:
        (out_dir / "risk_matrix.md").write_text(render_risk_matrix(matrix), encoding="utf-8")
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
    crosswalk = build_iso27001_crosswalk(result)
    (out_dir / "iso27001_crosswalk.md").write_text(render_iso27001_crosswalk(crosswalk), encoding="utf-8")
    (out_dir / "iso27001_document_checklist.md").write_text(
        render_iso27001_document_checklist(entity), encoding="utf-8"
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
        _write_output(args.output, render_progress_report(delta))
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
    MyCiber (DL 125/2025, Art. 23): triagem de impacto significativo, alerta
    inicial (24h) e relatório detalhado (72h), com os prazos calculados a
    partir da deteção do incidente."""
    entity = load_entity(Path(args.entity))
    raw = yaml.safe_load(Path(args.incident).read_text(encoding="utf-8"))
    incident = load_incident(Path(args.incident), entity)
    deadlines = compute_deadlines(incident)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Triagem de impacto significativo (Reg. UE 2024/2690). Usa o bloco
    # opcional `significance` do YAML; na ausência, faz uma triagem mínima a
    # partir dos campos já existentes do incidente.
    criteria = _load_significance(raw) or SignificanceCriteria(
        impacto_transfronteirico=incident.cross_border_effect
    )
    verdict = assess_significance(criteria, dados_pessoais_envolvidos=bool(raw.get("dados_pessoais_envolvidos", False)))
    (out_dir / "triagem_significancia.md").write_text(
        render_significance_triage(incident, verdict), encoding="utf-8"
    )

    (out_dir / "alerta_inicial_24h.md").write_text(
        render_incident_alert(incident, deadlines), encoding="utf-8"
    )
    (out_dir / "relatorio_detalhado_72h.md").write_text(
        render_incident_report(incident, deadlines), encoding="utf-8"
    )
    (out_dir / "fim_impacto_significativo.md").write_text(
        render_incident_end_of_impact(incident, deadlines), encoding="utf-8"
    )
    (out_dir / "relatorio_final.md").write_text(
        render_incident_final_report(incident, deadlines), encoding="utf-8"
    )

    print(f"Incidente:             {incident.incident_id} ({incident.severity})")
    print(f"Detetado em:           {incident.detected_at.isoformat()}")
    print(f"Significativo:         {'SIM' if verdict.significativo else 'a reavaliar'}")
    print(f"Prazo alerta inicial:  {deadlines.alerta_inicial.isoformat()}")
    print(f"Prazo relatório 72h:   {deadlines.relatorio_detalhado.isoformat()}")
    print(f"Prazo relatório final: {deadlines.relatorio_final.isoformat()}")
    duracao = incident.significant_impact_duration_hours()
    if duracao is not None:
        print(f"Duração impacto signif.: {duracao} h")
    print(f"Deliverables escritos em: {out_dir}/")
    return 0


def cmd_risk(args: argparse.Namespace) -> int:
    """Aplica a Matriz de Risco do Anexo II a partir de cenários de risco e
    determina o nível de conformidade exigido (matriz + agregação art. 30.º)."""
    entity = load_entity(Path(args.entity))
    entity_type = classify_entity(entity)
    nivel_referencia = (
        None if entity_type is EntityType.FORA_DE_AMBITO else required_compliance_level(entity_type)
    )
    scenarios = load_risk_scenarios(Path(args.scenarios))
    matrix = build_risk_matrix(entity, scenarios, nivel_referencia=nivel_referencia)

    print(f"Entidade:           {matrix.entity_name}")
    print(f"Dimensão:           {matrix.dimensao} (fator {matrix.dimensao_fator})")
    print(f"Tipo de setor:      {matrix.tipo_setor} (fator {matrix.tipo_setor_fator})")
    print(f"Valor de risco:     {matrix.total}")
    print(f"Nível pela matriz:  {matrix.nivel_matriz.value}")
    if matrix.nivel_referencia:
        print(f"Nível por tipo:     {matrix.nivel_referencia.value}")
    print(f"Nível efetivo:      {matrix.nivel_efetivo.value}")
    for aviso in matrix.avisos:
        print(f"  ⚠️ {aviso}")

    if args.output:
        _write_output(args.output, render_risk_matrix(matrix))
        print(f"\nMatriz de risco escrita em: {args.output}")
    return 0


def cmd_deadlines(args: argparse.Namespace) -> int:
    """Gera o calendário de obrigações da entidade a partir da data de
    qualificação/notificação (lista de ativos art. 32.º, relatório anual,
    designação de responsável/ponto de contacto)."""
    from datetime import date

    entity = load_entity(Path(args.entity))
    reference_date = date.fromisoformat(args.since)
    obligations = build_obligations_calendar(entity.name, reference_date)

    print(f"Entidade: {entity.name}  ·  Referência: {reference_date}\n")
    print(f"{'Estado':<10} {'Prazo':<12} Obrigação")
    print(f"{'-' * 10} {'-' * 12} {'-' * 40}")
    for o in obligations:
        print(f"{o.estado(date.today()):<10} {str(o.due_date):<12} {o.nome}")

    if args.output:
        _write_output(args.output, render_deadlines(entity.name, reference_date, obligations))
        print(f"\nCalendário de obrigações escrito em: {args.output}")
    return 0


def cmd_portfolio(args: argparse.Namespace) -> int:
    """Vista agregada da carteira de clientes a partir dos snapshots gravados
    com `nis2 assess --history-dir`: nível, score, maturidade e tendência por
    entidade."""
    entries = build_portfolio(Path(args.history_dir))
    if not entries:
        print(f"Sem snapshots em {args.history_dir}/.", file=sys.stderr)
        return 1

    print(f"Carteira de clientes ({len(entries)} entidade(s)):\n")
    print(f"{'Entidade':<32} {'Nível':<12} {'Score':>7} {'Mat.':>7} {'Tend.':>5}")
    print(f"{'-' * 32} {'-' * 12} {'-' * 7} {'-' * 7} {'-' * 5}")
    for e in entries:
        print(f"{e.entity_name[:32]:<32} {e.target_level:<12} {e.score_pct:>6}% {e.maturity_score_pct:>6}% {e.trend:>5}")

    if args.output:
        _write_output(args.output, render_portfolio(entries))
        print(f"\nCarteira escrita em: {args.output}")
    return 0


def cmd_profiles(args: argparse.Namespace) -> int:
    """Lista os perfis setoriais pré-preenchidos disponíveis (autarquias,
    juntas de freguesia, hotelaria, turismo)."""
    profiles = load_profiles()
    if not profiles:
        print("Sem perfis setoriais disponíveis.", file=sys.stderr)
        return 1
    print(f"Perfis setoriais disponíveis ({len(profiles)}):\n")
    for p in profiles:
        ambito = "público" if p.is_public_body else "privado"
        print(f"  {p.id:<18} {p.nome}  ({p.setor}, {ambito})")
        print(f"  {'':<18} {p.descricao.splitlines()[0] if p.descricao else ''}")
    print('\nUse: nis2 profile <id> -o <pasta>  para gerar entity.yaml + scenarios.yaml.')
    return 0


def cmd_profile(args: argparse.Namespace) -> int:
    """Materializa um perfil setorial: escreve `entity.yaml` e `scenarios.yaml`
    prontos a alimentar `nis2 risk` / `nis2 assess --risk`, e imprime a nota de
    âmbito e as notas de prioridade do setor."""
    try:
        profile = get_profile(args.profile_id)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    entity_path = out_dir / "entity.yaml"
    scenarios_path = out_dir / "scenarios.yaml"
    entity_path.write_text(
        yaml.safe_dump(profile.entity_dict(), allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    scenarios_path.write_text(
        yaml.safe_dump(profile.scenarios_dict(), allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    print(f"Perfil: {profile.nome} ({profile.id})\n")
    if profile.ambito_nota:
        print("Âmbito:")
        print(f"  {profile.ambito_nota.strip()}\n")
    if profile.nivel_referencia_sugerido:
        print(f"Nível de referência sugerido: {profile.nivel_referencia_sugerido}\n")
    if profile.ativos_criticos:
        print("Ativos críticos típicos:")
        for a in profile.ativos_criticos:
            print(f"  - {a}")
        print()
    if profile.notas:
        print("Notas de prioridade:")
        for n in profile.notas:
            print(f"  - {n}")
        print()
    print(f"Ficheiros gerados:\n  {entity_path}\n  {scenarios_path}")
    print(f"\nPróximo passo: nis2 risk {entity_path} {scenarios_path}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Arranca a web app local: introdução de dados por formulário, escolha de
    deliverables e exportação em Markdown e PDF, reutilizando o motor."""
    from .webapp import serve

    serve(host=args.host, port=args.port, brand=args.brand, open_browser=not args.no_browser)
    return 0


def cmd_dossier(args: argparse.Namespace) -> int:
    """Agrega os deliverables Markdown de uma pasta num único dossier HTML com
    a marca do consultor (capa + índice + impressão), e opcionalmente exporta
    PDF (`--pdf`) se houver um motor disponível."""
    md_dir = Path(args.input)
    if not md_dir.is_dir():
        print(f"Pasta não encontrada: {md_dir}", file=sys.stderr)
        return 1
    sections = collect_sections(md_dir)
    if not sections:
        print(f"Sem ficheiros .md em {md_dir}/.", file=sys.stderr)
        return 1

    html_doc = build_dossier_html(args.title, sections, brand=args.brand)
    out_html = Path(args.output)
    _write_output(out_html, html_doc)
    print(f"Dossier ({len(sections)} secções) escrito em: {out_html}")

    if args.pdf:
        pdf_path = out_html.with_suffix(".pdf")
        if render_pdf(html_doc, pdf_path):
            print(f"PDF gerado em: {pdf_path}")
        else:
            print(
                "Sem motor de PDF disponível (weasyprint/Chromium). "
                f"Abra {out_html} no browser e use Imprimir → Guardar como PDF.",
                file=sys.stderr,
            )
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
        _write_output(args.output, render_audit_report(report))
        print(f"\nRelatório de auditoria escrito em: {args.output}")

    if args.checklist:
        rows = build_validation_checklist(controls)
        _write_output(args.checklist, render_validation_checklist_csv(rows))
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


def cmd_form(args: argparse.Namespace) -> int:
    """Gera um formulário HTML self-contained para classificar entidades quanto
    ao âmbito NIS2 no browser (sem servidor), com histórico local e exportação
    de YAML para alimentar `nis2 classify`/`scaffold`/`assess`."""
    html = render_classifier_form(brand=args.brand)
    _write_output(args.output, html)
    print(f"Formulário de classificação escrito em: {args.output}")
    print("Abre o ficheiro num browser para preencher o perfil e ver a classificação em tempo real.")
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
    p_assess.add_argument("--risk", help="Ficheiro YAML com cenários de risco — computa o nível-alvo pela Matriz de Risco (Anexo II) em vez do tipo de entidade.")
    p_assess.set_defaults(func=cmd_assess)

    p_risk = sub.add_parser("risk", help="Aplica a Matriz de Risco (Anexo II) a cenários de risco e determina o nível exigido.")
    p_risk.add_argument("entity", help="Ficheiro YAML com o perfil da entidade.")
    p_risk.add_argument("scenarios", help="Ficheiro YAML com os cenários de risco (name, probabilidade, impacto, threat_actor).")
    p_risk.add_argument("-o", "--output", help="Caminho para escrever o relatório da matriz (markdown).")
    p_risk.set_defaults(func=cmd_risk)

    p_deadlines = sub.add_parser("deadlines", help="Gera o calendário de obrigações da entidade (art. 32.º, relatório anual, designação).")
    p_deadlines.add_argument("entity", help="Ficheiro YAML com o perfil da entidade.")
    p_deadlines.add_argument("--since", required=True, help="Data de qualificação/notificação (YYYY-MM-DD).")
    p_deadlines.add_argument("-o", "--output", help="Caminho para escrever o calendário (markdown).")
    p_deadlines.set_defaults(func=cmd_deadlines)

    p_portfolio = sub.add_parser("portfolio", help="Vista agregada da carteira de clientes a partir dos snapshots de histórico.")
    p_portfolio.add_argument("--history-dir", required=True, help="Diretório com os snapshots gravados por 'nis2 assess --history-dir'.")
    p_portfolio.add_argument("-o", "--output", help="Caminho para escrever a carteira (markdown).")
    p_portfolio.set_defaults(func=cmd_portfolio)

    p_profiles = sub.add_parser("profiles", help="Lista os perfis setoriais pré-preenchidos (autarquias, juntas, hotelaria, turismo).")
    p_profiles.set_defaults(func=cmd_profiles)

    p_profile = sub.add_parser("profile", help="Materializa um perfil setorial em entity.yaml + scenarios.yaml prontos a usar.")
    p_profile.add_argument("profile_id", help="Id do perfil (ver 'nis2 profiles').")
    p_profile.add_argument("-o", "--output", required=True, help="Pasta onde escrever entity.yaml e scenarios.yaml.")
    p_profile.set_defaults(func=cmd_profile)

    p_serve = sub.add_parser("serve", help="Arranca a web app local (formulário + escolha de deliverables + exportação MD/PDF).")
    p_serve.add_argument("--host", default="127.0.0.1", help="Host de escuta (por omissão 127.0.0.1).")
    p_serve.add_argument("--port", type=int, default=8000, help="Porta (por omissão 8000).")
    p_serve.add_argument("--brand", default="REGENTE", help="Marca/consultor a apresentar na app.")
    p_serve.add_argument("--no-browser", action="store_true", help="Não abrir o browser automaticamente.")
    p_serve.set_defaults(func=cmd_serve)

    p_dossier = sub.add_parser("dossier", help="Agrega os deliverables Markdown de uma pasta num dossier HTML com marca (e PDF opcional).")
    p_dossier.add_argument("input", help="Pasta com os ficheiros .md (ex.: a saída de 'nis2 assess').")
    p_dossier.add_argument("-o", "--output", required=True, help="Caminho do dossier HTML a escrever.")
    p_dossier.add_argument("--title", default="Relatório de Conformidade NIS2", help="Título na capa do dossier.")
    p_dossier.add_argument("--brand", default="REGENTE", help="Marca/consultor a apresentar na capa e rodapé.")
    p_dossier.add_argument("--pdf", action="store_true", help="Tentar exportar também PDF (weasyprint/Chromium se disponíveis).")
    p_dossier.set_defaults(func=cmd_dossier)

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

    p_form = sub.add_parser(
        "form", help="Gera um formulário HTML para classificar entidades no browser (com histórico local)."
    )
    p_form.add_argument("-o", "--output", default="out/classificador.html", help="Caminho do HTML a gerar (default: ./out/classificador.html).")
    p_form.add_argument("--brand", default="", help="Nome/marca do consultor a apresentar no formulário.")
    p_form.set_defaults(func=cmd_form)

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
