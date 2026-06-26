from nis2_engine import (
    Entity,
    build_iso27001_crosswalk,
    load_controls,
    render_iso27001_crosswalk,
    render_iso27001_document_checklist,
    run_assessment,
)
from nis2_engine.iso27001 import (
    ART21_MEASURES,
    ISO27001_MANDATORY_DOCUMENTS,
    ISO27002_THEME_ORDER,
    art21_measure_letters,
    iso27002_theme,
)
from nis2_engine.models import AssessmentAnswer, ComplianceLevel


def test_iso27002_theme_derives_from_annex_a_prefix():
    assert iso27002_theme("A.5.1") == "Organizacionais"
    assert iso27002_theme("A.6.3") == "Pessoas"
    assert iso27002_theme("A.7.1") == "Físicos"
    assert iso27002_theme("A.8.16") == "Tecnológicos"
    assert iso27002_theme("X.1.1") is None


def test_art21_measures_table_has_all_ten_letters():
    assert set(ART21_MEASURES.keys()) == set("abcdefghij")
    for letter, data in ART21_MEASURES.items():
        assert data["descricao"]
        assert data["iso_refs"]


def _camara_result():
    controls = load_controls()
    entity = Entity(name="Câmara X", sector="administracao_publica", employees=120, annual_turnover_eur=0)
    target_level = ComplianceLevel.ELEVADO
    required_ids = [c.id for c in controls if c.required_at(target_level)]
    answers = [
        AssessmentAnswer(control_id=cid, implemented=(i % 2 == 0), maturity=5 if i % 2 == 0 else 0)
        for i, cid in enumerate(required_ids)
    ]
    return run_assessment(entity, target_level, controls, answers)


def test_build_iso27001_crosswalk_reuses_assessment_without_recomputing():
    result = _camara_result()
    crosswalk = build_iso27001_crosswalk(result)

    assert crosswalk.result is result
    # Cada controlo com refs Anexo A cai em pelo menos um tema citado.
    total_gaps_in_themes = sum(len(g.gaps) for g in crosswalk.by_theme)
    assert total_gaps_in_themes >= len(result.gaps)
    for group in crosswalk.by_theme:
        assert group.theme in ISO27002_THEME_ORDER
        assert 0.0 <= group.coverage_pct <= 100.0

    for group in crosswalk.by_measure:
        assert group.letter in ART21_MEASURES
        assert 0.0 <= group.coverage_pct <= 100.0


def test_art21_measure_letters_parses_article_citation():
    result = _camara_result()
    gap = next(g for g in result.gaps if "Art. 21(2)(b)" in g.control.crosswalk.nis2_article)
    assert "b" in art21_measure_letters(gap)


def test_mandatory_documents_checklist_has_eleven_items_with_clauses():
    assert len(ISO27001_MANDATORY_DOCUMENTS) == 11
    for doc in ISO27001_MANDATORY_DOCUMENTS:
        assert doc["clausula"]
        assert doc["documento"]


def test_render_iso27001_crosswalk_includes_theme_and_measure_tables():
    result = _camara_result()
    crosswalk = build_iso27001_crosswalk(result)
    md = render_iso27001_crosswalk(crosswalk)
    assert "Cobertura por tema ISO/IEC 27002:2022" in md
    assert "Cobertura por medida mínima (Art. 21.º, n.º 2, NIS2)" in md
    assert "Tecnológicos" in md


def test_render_iso27001_document_checklist_lists_all_documents():
    entity = Entity(name="Câmara X", sector="administracao_publica", employees=120, annual_turnover_eur=0)
    md = render_iso27001_document_checklist(entity, generated_at="2026-06-26")
    assert "Câmara X" in md
    assert "Declaração de Aplicabilidade (SoA)" in md
    assert md.count("☐") == 11
