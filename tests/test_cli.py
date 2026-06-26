import yaml

from nis2_engine.cli import load_answers, load_entity, load_risk_scenarios, main
from nis2_engine.models import EntityType


def test_cli_profiles_lists_verticals(capsys):
    assert main(["profiles"]) == 0
    out = capsys.readouterr().out
    assert "camara_municipal" in out
    assert "hotelaria" in out


def test_cli_profile_scaffolds_entity_and_scenarios(tmp_path):
    out_dir = tmp_path / "perfil"
    assert main(["profile", "camara_municipal", "-o", str(out_dir)]) == 0
    entity_path = out_dir / "entity.yaml"
    scenarios_path = out_dir / "scenarios.yaml"
    assert entity_path.exists()
    assert scenarios_path.exists()
    # Os ficheiros gerados têm de ser consumíveis pelos loaders da CLI.
    entity = load_entity(entity_path)
    assert entity.is_public_body is True
    scenarios = load_risk_scenarios(scenarios_path)
    assert scenarios
    assert 1 <= scenarios[0].probabilidade <= 5


def test_cli_profile_unknown_returns_error(tmp_path, capsys):
    rc = main(["profile", "nao_existe", "-o", str(tmp_path / "x")])
    assert rc == 1
    assert "não encontrado" in capsys.readouterr().err


def test_cli_dossier_aggregates_md_into_branded_html(tmp_path):
    md_dir = tmp_path / "out"
    md_dir.mkdir()
    (md_dir / "risk_matrix.md").write_text("# Matriz\n\n- cenário", encoding="utf-8")
    (md_dir / "gap_report.md").write_text("# Gap\n\nconteúdo", encoding="utf-8")
    dossier = tmp_path / "dossier.html"
    rc = main(["dossier", str(md_dir), "-o", str(dossier), "--brand", "Acme"])
    assert rc == 0
    html = dossier.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert "Acme" in html
    assert "Matriz de Risco (Anexo II)" in html
    assert "Gap Analysis" in html


def _write(path, data):
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_load_entity_roundtrip(tmp_path):
    path = _write(
        tmp_path / "entity.yaml",
        {"name": "X", "sector": "energia", "employees": 200, "annual_turnover_eur": 50_000_000},
    )
    entity = load_entity(path)
    assert entity.name == "X"
    assert entity.employees == 200


def test_load_answers_supports_nested_and_flat(tmp_path):
    nested = _write(tmp_path / "a.yaml", {"answers": [{"control_id": "GOV-01", "implemented": True}]})
    flat = _write(tmp_path / "b.yaml", [{"control_id": "GOV-01", "implemented": True}])
    assert load_answers(nested)[0].control_id == "GOV-01"
    assert load_answers(flat)[0].implemented is True


def test_cli_classify_writes_self_identification(tmp_path, capsys):
    entity = _write(
        tmp_path / "entity.yaml",
        {"name": "Energia SA", "sector": "energia", "employees": 200, "annual_turnover_eur": 50_000_000},
    )
    out = tmp_path / "selfid.md"
    rc = main(["classify", str(entity), "-o", str(out)])
    assert rc == 0
    assert out.exists()
    assert "ELEVADO" in out.read_text(encoding="utf-8")


def test_cli_scaffold_then_assess(tmp_path):
    entity = _write(
        tmp_path / "entity.yaml",
        {"name": "Energia SA", "sector": "energia", "employees": 200, "annual_turnover_eur": 50_000_000},
    )
    scaffold = tmp_path / "answers.yaml"
    assert main(["scaffold", str(entity), "-o", str(scaffold)]) == 0
    assert scaffold.exists()

    out_dir = tmp_path / "out"
    assert main(["assess", str(entity), str(scaffold), "-o", str(out_dir), "--brand", "Acme"]) == 0
    assert (out_dir / "gap_report.md").exists()
    assert (out_dir / "roadmap.md").exists()
    assert (out_dir / "statement_of_applicability.md").exists()
    assert (out_dir / "self_identification.md").exists()
    assert (out_dir / "evidence_plan.md").exists()
    assert (out_dir / "maturity_radar.svg").exists()
    report_html = out_dir / "report.html"
    assert report_html.exists()
    html = report_html.read_text(encoding="utf-8")
    assert "<svg" in html
    assert "Acme" in html
    assert (out_dir / "iso27001_crosswalk.md").exists()
    assert (out_dir / "iso27001_document_checklist.md").exists()


def test_cli_assess_out_of_scope_returns_error(tmp_path):
    entity = _write(
        tmp_path / "entity.yaml",
        {"name": "Padaria", "sector": "alimentacao", "employees": 5, "annual_turnover_eur": 100_000},
    )
    answers = _write(tmp_path / "answers.yaml", {"answers": []})
    assert main(["assess", str(entity), str(answers), "-o", str(tmp_path / "out")]) == 1


def test_cli_scaffold_out_of_scope_returns_error(tmp_path):
    entity = _write(
        tmp_path / "entity.yaml",
        {"name": "Padaria", "sector": "alimentacao", "employees": 5, "annual_turnover_eur": 100_000},
    )
    assert main(["scaffold", str(entity)]) == 1


def test_cli_policies_writes_all_three_documents(tmp_path):
    entity = _write(
        tmp_path / "entity.yaml",
        {"name": "Energia SA", "sector": "energia", "employees": 200, "annual_turnover_eur": 50_000_000},
    )
    out_dir = tmp_path / "out" / "politicas"
    assert main(["policies", str(entity), "-o", str(out_dir), "--approver", "Maria Silva"]) == 0
    assert (out_dir / "politica_resposta_incidentes.md").exists()
    assert (out_dir / "politica_seguranca_fornecedores.md").exists()
    assert (out_dir / "politica_continuidade_bcdr.md").exists()
    assert "Maria Silva" in (out_dir / "politica_resposta_incidentes.md").read_text(encoding="utf-8")


def test_cli_audit_writes_report(tmp_path):
    out = tmp_path / "audit.md"
    assert main(["audit", "-o", str(out)]) == 0
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "por validar" in content.lower() or "POR_VALIDAR" in content.upper()


def test_cli_audit_writes_validation_checklist_csv(tmp_path):
    checklist = tmp_path / "checklist.csv"
    assert main(["audit", "--checklist", str(checklist)]) == 0
    assert checklist.exists()
    content = checklist.read_text(encoding="utf-8")
    assert "CLASSIFICACAO-SETORIAL" in content
    assert "artigo_confirmado_dre" in content


def test_cli_assess_with_history_dir_saves_snapshot(tmp_path):
    entity = _write(
        tmp_path / "entity.yaml",
        {"name": "Energia SA", "sector": "energia", "employees": 200, "annual_turnover_eur": 50_000_000},
    )
    scaffold = tmp_path / "answers.yaml"
    assert main(["scaffold", str(entity), "-o", str(scaffold)]) == 0

    history_dir = tmp_path / "history"
    out_dir = tmp_path / "out"
    assert main(["assess", str(entity), str(scaffold), "-o", str(out_dir), "--history-dir", str(history_dir)]) == 0
    assert history_dir.exists()
    assert len(list(history_dir.glob("*.json"))) == 1


def test_cli_progress_requires_at_least_two_snapshots(tmp_path):
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    rc = main(["progress", "Energia SA", "--history-dir", str(history_dir)])
    assert rc == 1


def test_cli_progress_compares_two_assessments(tmp_path):
    entity = _write(
        tmp_path / "entity.yaml",
        {"name": "Energia SA", "sector": "energia", "employees": 200, "annual_turnover_eur": 50_000_000},
    )
    scaffold = tmp_path / "answers.yaml"
    assert main(["scaffold", str(entity), "-o", str(scaffold)]) == 0

    history_dir = tmp_path / "history"
    out_dir = tmp_path / "out"

    assert main(["assess", str(entity), str(scaffold), "-o", str(out_dir), "--history-dir", str(history_dir)]) == 0

    answers = yaml.safe_load(scaffold.read_text(encoding="utf-8"))
    for item in answers["answers"]:
        item["implemented"] = True
        item["maturity"] = 5
    _write(scaffold, answers)

    assert main(["assess", str(entity), str(scaffold), "-o", str(out_dir), "--history-dir", str(history_dir)]) == 0
    assert len(list(history_dir.glob("*.json"))) == 2

    progress_out = tmp_path / "progress.md"
    assert main(["progress", "Energia SA", "--history-dir", str(history_dir), "-o", str(progress_out)]) == 0
    assert progress_out.exists()
    content = progress_out.read_text(encoding="utf-8")
    assert "Relatório de Evolução" in content


def test_cli_incident_writes_alert_and_report(tmp_path):
    entity = _write(
        tmp_path / "entity.yaml",
        {"name": "Energia SA", "sector": "energia", "employees": 200, "annual_turnover_eur": 50_000_000},
    )
    incident = _write(
        tmp_path / "incident.yaml",
        {
            "incident_id": "INC-2026-001",
            "detected_at": "2026-06-24T09:00:00",
            "severity": "alto",
            "description": "Acesso não autorizado detetado num servidor de email.",
            "affected_systems": ["Servidor de email"],
            "cross_border_effect": False,
        },
    )
    out_dir = tmp_path / "out" / "incidente"
    assert main(["incident", str(entity), str(incident), "-o", str(out_dir)]) == 0
    alert = out_dir / "alerta_inicial_24h.md"
    report = out_dir / "relatorio_detalhado_72h.md"
    assert alert.exists()
    assert report.exists()
    assert "INC-2026-001" in alert.read_text(encoding="utf-8")
    assert "2026-06-25 09:00" in alert.read_text(encoding="utf-8")
    assert "Em investigação." in report.read_text(encoding="utf-8")


def test_cli_incident_writes_end_of_impact_and_final_report(tmp_path):
    entity = _write(
        tmp_path / "entity.yaml",
        {"name": "Energia SA", "sector": "energia", "employees": 200, "annual_turnover_eur": 50_000_000},
    )
    incident = _write(
        tmp_path / "incident.yaml",
        {
            "incident_id": "INC-2026-009",
            "detected_at": "2026-06-24T09:00:00",
            "severity": "alto",
            "description": "Ransomware num servidor de ficheiros.",
            "threat_type": "Ransomware",
            "significant_impact_ended_at": "2026-06-25T09:00:00",
            "ongoing_mitigation_actions": ["Restauro a partir de cópias offline"],
            "lessons_learned": "Testar restauros trimestralmente.",
            "status": "encerrado",
        },
    )
    out_dir = tmp_path / "out" / "incidente"
    assert main(["incident", str(entity), str(incident), "-o", str(out_dir)]) == 0
    end = out_dir / "fim_impacto_significativo.md"
    final = out_dir / "relatorio_final.md"
    assert end.exists()
    assert final.exists()
    # Fim do impacto: 24h de duração (deteção -> fim).
    assert "24.0 h" in end.read_text(encoding="utf-8")
    final_text = final.read_text(encoding="utf-8")
    assert "Art. 44" in final_text
    assert "FINAL" in final_text
    assert "Ransomware" in final_text
    assert "Testar restauros trimestralmente." in final_text


def test_cli_history_lists_snapshots(tmp_path, capsys):
    entity = _write(
        tmp_path / "entity.yaml",
        {"name": "Energia SA", "sector": "energia", "employees": 200, "annual_turnover_eur": 50_000_000},
    )
    scaffold = tmp_path / "answers.yaml"
    assert main(["scaffold", str(entity), "-o", str(scaffold)]) == 0

    history_dir = tmp_path / "history"
    out_dir = tmp_path / "out"
    assert main(["assess", str(entity), str(scaffold), "-o", str(out_dir), "--history-dir", str(history_dir)]) == 0

    assert main(["history", "Energia SA", "--history-dir", str(history_dir)]) == 0
    captured = capsys.readouterr()
    assert "1 snapshot(s)" in captured.out


def test_cli_history_no_snapshots_returns_error(tmp_path):
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    assert main(["history", "Inexistente", "--history-dir", str(history_dir)]) == 1


def test_cli_list_controls_lists_full_catalog(capsys):
    assert main(["list-controls"]) == 0
    captured = capsys.readouterr()
    assert "GOV-01" in captured.out
    assert "Total:" in captured.out


def test_cli_list_controls_filters_by_level(capsys):
    assert main(["list-controls", "--level", "basico"]) == 0
    captured = capsys.readouterr()
    assert "GOV-01" in captured.out


def test_cli_list_controls_filters_by_function(capsys):
    assert main(["list-controls", "--function", "Governar"]) == 0
    captured = capsys.readouterr()
    assert "Proteger" not in captured.out
    assert "Governar" in captured.out


def test_cli_list_controls_shows_detail_for_control_id(capsys):
    assert main(["list-controls", "GOV-01"]) == 0
    captured = capsys.readouterr()
    assert "GOV-01" in captured.out
    assert "Crosswalk:" in captured.out


def test_cli_list_controls_unknown_id_errors_with_available_list(capsys):
    assert main(["list-controls", "XXX-99"]) == 1
    captured = capsys.readouterr()
    assert "não encontrado" in captured.err
    assert "GOV-01" in captured.err


def test_cli_missing_entity_file_returns_friendly_error(tmp_path, capsys):
    missing = tmp_path / "nao_existe.yaml"
    rc = main(["classify", str(missing)])
    assert rc == 1
    captured = capsys.readouterr()
    assert "não encontrado" in captured.err


def test_cli_entity_missing_required_field_returns_friendly_error(tmp_path, capsys):
    entity = _write(tmp_path / "entity.yaml", {"name": "X", "sector": "energia"})
    rc = main(["classify", str(entity)])
    assert rc == 1
    captured = capsys.readouterr()
    assert "campo obrigatório" in captured.err


def test_cli_debug_flag_prints_traceback_on_error(tmp_path, capsys):
    missing = tmp_path / "nao_existe.yaml"
    rc = main(["--debug", "classify", str(missing)])
    assert rc == 1
    captured = capsys.readouterr()
    assert "Traceback (most recent call last):" in captured.err
    assert "FileNotFoundError" in captured.err
    assert "não encontrado" in captured.err


def test_cli_without_debug_flag_omits_traceback(tmp_path, capsys):
    missing = tmp_path / "nao_existe.yaml"
    rc = main(["classify", str(missing)])
    assert rc == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err


def test_cli_classify_creates_missing_output_directories(tmp_path):
    entity = _write(
        tmp_path / "entity.yaml",
        {"name": "Energia SA", "sector": "energia", "employees": 200, "annual_turnover_eur": 50_000_000},
    )
    out = tmp_path / "pasta" / "que" / "nao" / "existe" / "selfid.md"
    assert main(["classify", str(entity), "-o", str(out)]) == 0
    assert out.exists()


def test_cli_form_writes_self_contained_html(tmp_path):
    out = tmp_path / "sub" / "classificador.html"
    assert main(["form", "-o", str(out), "--brand", "Acme"]) == 0
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert "Acme" in html
    assert "nis2-config" in html


def test_cli_version_flag(capsys):
    raised = False
    try:
        main(["--version"])
    except SystemExit as exc:
        raised = True
        assert exc.code == 0
    assert raised
    captured = capsys.readouterr()
    assert "nis2" in captured.out


def _energia(tmp_path):
    return _write(
        tmp_path / "entity.yaml",
        {"name": "Energia SA", "sector": "energia", "employees": 200, "annual_turnover_eur": 50_000_000},
    )


def test_cli_risk_computes_level_and_writes_report(tmp_path):
    entity = _energia(tmp_path)
    scenarios = _write(
        tmp_path / "scenarios.yaml",
        {"scenarios": [
            {"name": "Ransomware", "probabilidade": 4, "impacto": 5},
            {"name": "Phishing", "probabilidade": 5, "impacto": 3},
        ]},
    )
    out = tmp_path / "risk.md"
    assert main(["risk", str(entity), str(scenarios), "-o", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "Matriz de Risco" in text
    assert "Nível efetivo" in text


def test_cli_deadlines_writes_calendar(tmp_path):
    entity = _energia(tmp_path)
    out = tmp_path / "deadlines.md"
    assert main(["deadlines", str(entity), "--since", "2026-03-01", "-o", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "Calendário de Obrigações" in text
    assert "Art. 32" in text


def test_cli_assess_with_risk_writes_matrix(tmp_path):
    entity = _energia(tmp_path)
    scaffold = tmp_path / "answers.yaml"
    assert main(["scaffold", str(entity), "-o", str(scaffold)]) == 0
    scenarios = _write(
        tmp_path / "scenarios.yaml",
        {"scenarios": [{"name": "c", "probabilidade": 5, "impacto": 5}]},
    )
    out_dir = tmp_path / "out"
    assert main(["assess", str(entity), str(scaffold), "-o", str(out_dir), "--risk", str(scenarios)]) == 0
    assert (out_dir / "risk_matrix.md").exists()


def test_cli_incident_writes_significance_triage(tmp_path):
    entity = _energia(tmp_path)
    incident = _write(
        tmp_path / "incident.yaml",
        {
            "incident_id": "INC-1",
            "detected_at": "2026-06-24T09:00:00",
            "severity": "alto",
            "description": "Acesso indevido.",
            "dados_pessoais_envolvidos": True,
            "significance": {"afeta_outras_entidades": True, "suspeita_ato_ilicito": True},
        },
    )
    out_dir = tmp_path / "inc"
    assert main(["incident", str(entity), str(incident), "-o", str(out_dir)]) == 0
    triage = (out_dir / "triagem_significancia.md").read_text(encoding="utf-8")
    assert "SIGNIFICATIVO" in triage
    assert "CNPD" in triage


def test_cli_portfolio_aggregates_history(tmp_path):
    entity = _energia(tmp_path)
    scaffold = tmp_path / "answers.yaml"
    assert main(["scaffold", str(entity), "-o", str(scaffold)]) == 0
    history_dir = tmp_path / "hist"
    assert main(["assess", str(entity), str(scaffold), "-o", str(tmp_path / "out"), "--history-dir", str(history_dir)]) == 0
    out = tmp_path / "portfolio.md"
    assert main(["portfolio", "--history-dir", str(history_dir), "-o", str(out)]) == 0
    assert "Carteira de Clientes" in out.read_text(encoding="utf-8")
