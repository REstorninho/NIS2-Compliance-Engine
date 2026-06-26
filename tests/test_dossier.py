from nis2_engine.dossier import (
    DossierSection,
    build_dossier_html,
    collect_sections,
    md_to_html,
)


def test_md_to_html_covers_template_subset():
    md = (
        "# Título\n\n"
        "Parágrafo com **negrito** e `código`.\n\n"
        "## Secção\n\n"
        "- item 1\n"
        "- item 2\n\n"
        "> uma nota\n\n"
        "| A | B |\n"
        "|---|---|\n"
        "| 1 | 2 |\n\n"
        "---\n"
    )
    html = md_to_html(md)
    assert "<h1>Título</h1>" in html
    assert "<h2>Secção</h2>" in html
    assert "<strong>negrito</strong>" in html
    assert "<code>código</code>" in html
    assert "<ul>" in html and "<li>item 1</li>" in html
    assert "<blockquote>uma nota</blockquote>" in html
    assert "<table>" in html and "<th>A</th>" in html and "<td>1</td>" in html
    assert "<hr/>" in html


def test_md_to_html_escapes_html_in_content():
    html = md_to_html("Texto com <script>alert(1)</script> perigoso.")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_build_dossier_html_is_self_contained_with_brand_cover_and_toc():
    sections = [
        DossierSection(title="Matriz de Risco", markdown="# X\n\nconteúdo"),
        DossierSection(title="Gap Analysis", markdown="## Y\n\n- a\n- b"),
    ]
    html = build_dossier_html("Relatório", sections, brand="Acme CyberSec")
    assert html.startswith("<!DOCTYPE html>")
    # Autossuficiente: sem recursos externos.
    assert "<link" not in html
    assert "src=" not in html
    # Marca, capa e índice presentes.
    assert "Acme CyberSec" in html
    assert "Índice" in html
    assert "Matriz de Risco" in html and "Gap Analysis" in html
    # Quebra de página entre secções via CSS de impressão.
    assert "@media print" in html
    assert "page-break" in html


def test_known_titles_match_real_engine_filenames(tmp_path):
    # Os nomes de ficheiro que o motor/web app escrevem têm de bater certo com
    # as chaves de _KNOWN_TITLES, senão os deliverables saem com título genérico
    # e fora da ordem canónica no dossier.
    for filename, expected in (
        ("self_identification.md", "Autoidentificação (MyCiber)"),
        ("statement_of_applicability.md", "Declaração de Aplicabilidade (SoA)"),
    ):
        (tmp_path / filename).write_text(f"# {filename}", encoding="utf-8")
    titles = [s.title for s in collect_sections(tmp_path)]
    assert "Autoidentificação (MyCiber)" in titles
    assert "Declaração de Aplicabilidade (SoA)" in titles


def test_collect_sections_orders_known_deliverables_first(tmp_path):
    (tmp_path / "zzz_outro.md").write_text("# Outro", encoding="utf-8")
    (tmp_path / "gap_report.md").write_text("# Gap", encoding="utf-8")
    (tmp_path / "risk_matrix.md").write_text("# Risco", encoding="utf-8")
    sections = collect_sections(tmp_path)
    titles = [s.title for s in sections]
    # risk_matrix vem antes de gap_report (ordem canónica), e o desconhecido no fim.
    assert titles.index("Matriz de Risco (Anexo II)") < titles.index("Gap Analysis")
    assert titles[-1] == "Zzz outro"
