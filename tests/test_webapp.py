from nis2_engine.webapp import build_app_config, generate_deliverables


def _base_form(**over):
    form = {
        "name": "Câmara de Teste",
        "sector": "administracao_publica",
        "employees": "300",
        "turnover": "25000000",
        "is_public_body": "1",
        "level": "",
        "deliv": ["self_identification", "risk_matrix", "gap_report", "roadmap"],
        "scn_name": ["Ransomware"],
        "scn_actor": ["Cibercrime"],
        "scn_prob": ["4"],
        "scn_impact": ["5"],
    }
    form.update(over)
    return form


def test_build_app_config_has_profiles_controls_and_deliverables():
    cfg = build_app_config()
    assert len(cfg["controls"]) >= 30
    assert any(p["id"] == "camara_municipal" for p in cfg["profiles"])
    assert any(d["id"] == "risk_matrix" for d in cfg["deliverables"])
    # Cada perfil traz cenários para o prefil no browser.
    camara = [p for p in cfg["profiles"] if p["id"] == "camara_municipal"][0]
    assert camara["scenarios"]


def test_generate_without_assessment_writes_self_id_and_risk_matrix(tmp_path):
    res = generate_deliverables(_base_form(), tmp_path)
    assert res.entity_type == "entidade_publica_relevante"
    # Sem autoavaliação: não há score nem gap report.
    assert res.score_pct is None
    assert "self_identification.md" in res.files
    assert "risk_matrix.md" in res.files
    assert "gap_report.md" not in res.files
    # Agregação art. 30.º: matriz básica + tipo elevado -> efetivo elevado.
    assert res.nivel_efetivo == "elevado"
    assert (tmp_path / "risk_matrix.md").exists()


def test_generate_with_assessment_produces_gap_and_score(tmp_path):
    form = _base_form(include_assessment="1")
    # Responde maturidade 5 a todos os controlos.
    for c in build_app_config()["controls"]:
        form[f"mat_{c['id']}"] = "5"
    res = generate_deliverables(form, tmp_path)
    assert res.score_pct is not None
    assert res.score_pct == 100.0
    assert "gap_report.md" in res.files
    assert "roadmap.md" in res.files
    assert (tmp_path / "report.html").exists()


def test_generate_out_of_scope_tourism_falls_back_to_basico(tmp_path):
    form = _base_form(
        name="Hotel X",
        sector="hotelaria",
        is_public_body="",
        employees="120",
        turnover="18000000",
        deliv=["self_identification"],
        scn_name=[""],
        scn_prob=[""],
        scn_impact=[""],
    )
    res = generate_deliverables(form, tmp_path)
    assert res.entity_type == "fora_de_ambito"
    # Sem cenários e sem tipo em âmbito → linha de base voluntária básica.
    assert res.nivel_efetivo == "basico"
    assert "self_identification.md" in res.files
