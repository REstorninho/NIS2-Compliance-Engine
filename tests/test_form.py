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
