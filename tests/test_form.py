import json
import re

from nis2_engine import build_classifier_config, render_classifier_form
from nis2_engine.classification import SETORES_ESSENCIAIS, SETORES_IMPORTANTES
from nis2_engine.models import SIZE_THRESHOLD_EMPLOYEES, SIZE_THRESHOLD_TURNOVER_EUR


def test_config_matches_engine_source_of_truth():
    config = build_classifier_config()
    assert set(config["essenciais"]) == SETORES_ESSENCIAIS
    assert set(config["importantes"]) == SETORES_IMPORTANTES
    assert config["size_employees"] == SIZE_THRESHOLD_EMPLOYEES
    assert config["size_turnover"] == SIZE_THRESHOLD_TURNOVER_EUR
    assert config["level_mapping"]["essencial"] == "elevado"
    assert config["level_mapping"]["importante"] == "substancial"
    assert config["level_mapping"]["entidade_publica_relevante"] == "elevado"


def test_config_includes_full_control_corpus_for_assessment():
    from nis2_engine import load_controls

    config = build_classifier_config()
    assert len(config["controls"]) == len(load_controls())
    sample = config["controls"][0]
    assert set(sample.keys()) == {"id", "title", "fn", "levels"}
    assert set(sample["levels"].keys()) == {"basico", "substancial", "elevado"}
    assert config["maturity_threshold"] == 3
    assert config["maturity_labels"]["3"] == "Definido"
    # As fases do roadmap vêm da fonte de verdade (roadmap.py).
    assert [p["priority"] for p in config["phases"]] == ["alta", "media", "baixa"]


def test_form_is_self_contained_html_with_embedded_config():
    html = render_classifier_form(brand="Acme")
    assert html.startswith("<!DOCTYPE html>")
    assert "Acme" in html
    # Sem recursos externos (CSS/JS) — tudo embebido.
    assert "<link" not in html
    assert "src=" not in html
    # A config injetada tem de ser JSON válido e refletir o motor.
    match = re.search(r'<script id="nis2-config" type="application/json">(.*?)</script>', html, re.S)
    assert match
    config = json.loads(match.group(1))
    assert "energia" in config["essenciais"]
    assert config["size_employees"] == SIZE_THRESHOLD_EMPLOYEES


def test_form_default_brand_is_regente():
    html = render_classifier_form()
    assert "REGENTE" in html


def test_form_includes_maturity_questionnaire_and_results():
    html = render_classifier_form()
    # Secções da autoavaliação de maturidade no browser.
    assert "Autoavaliação de maturidade" in html
    assert 'id="questionnaire"' in html
    assert "Roadmap de remediação" in html
    # O corpus de controlos tem de estar embebido na config para o questionário.
    match = re.search(r'<script id="nis2-config" type="application/json">(.*?)</script>', html, re.S)
    config = json.loads(match.group(1))
    assert len(config["controls"]) >= 30


def test_form_includes_report_export_and_radar_data():
    html = render_classifier_form(brand="Acme")
    # Botão e construtor do relatório HTML no browser.
    assert 'id="btn-report"' in html
    assert "buildReportHtml" in html
    assert "function radarSvg" in html
    match = re.search(r'<script id="nis2-config" type="application/json">(.*?)</script>', html, re.S)
    config = json.loads(match.group(1))
    # A ordem canónica do radar e a marca têm de estar disponíveis para o JS.
    assert config["radar_order"][0] == "Governar"
    assert config["brand"] == "Acme"
