"""Dossier — agrega os deliverables Markdown num único documento HTML com a
marca do consultor, capa e índice, pronto a imprimir/guardar como PDF.

Filosofia: zero dependências novas. O conversor de Markdown cobre apenas o
subconjunto que os templates do projeto produzem (cabeçalhos, **negrito**,
`código`, listas, tabelas, blockquotes, regras horizontais, parágrafos) — não é
um conversor genérico. O HTML é autossuficiente (CSS embebido, `@media print`
com quebras de página) e abre em qualquer browser para "Imprimir → Guardar como
PDF".

A geração direta de PDF (`render_pdf`) é OPORTUNISTA: usa o weasyprint se estiver
instalado, senão o Chromium via Playwright se disponível; caso contrário devolve
False e o chamador fica-se pelo HTML imprimível.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def _inline(text: str) -> str:
    """Converte formatação inline (escapando HTML primeiro): `código` e
    **negrito**."""
    out = html.escape(text)
    out = _INLINE_CODE_RE.sub(r"<code>\1</code>", out)
    out = _BOLD_RE.sub(r"<strong>\1</strong>", out)
    return out


def _table_row(line: str) -> list[str]:
    cells = line.strip().strip("|").split("|")
    return [c.strip() for c in cells]


def _is_table_separator(line: str) -> bool:
    return bool(re.fullmatch(r"\s*\|?[\s:|-]+\|?\s*", line)) and "-" in line


def md_to_html(md: str) -> str:
    """Converte o subconjunto de Markdown produzido pelos templates do projeto
    em HTML. Não é um conversor genérico."""
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            close_list()
            i += 1
            continue

        # Regra horizontal
        if re.fullmatch(r"-{3,}", stripped):
            close_list()
            out.append("<hr/>")
            i += 1
            continue

        # Cabeçalhos
        m = re.match(r"(#{1,6})\s+(.*)", stripped)
        if m:
            close_list()
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # Blockquote
        if stripped.startswith(">"):
            close_list()
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip()[1:].strip())
                i += 1
            out.append(f"<blockquote>{_inline(' '.join(quote_lines))}</blockquote>")
            continue

        # Tabela: linha de cabeçalho seguida de separador
        if stripped.startswith("|") and i + 1 < len(lines) and _is_table_separator(lines[i + 1]):
            close_list()
            header = _table_row(lines[i])
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_table_row(lines[i]))
                i += 1
            out.append("<table>")
            out.append("<thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in header) + "</tr></thead>")
            out.append("<tbody>")
            for row in rows:
                out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>")
            out.append("</tbody></table>")
            continue

        # Item de lista
        if re.match(r"[-*]\s+", stripped):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(stripped[2:].strip())}</li>")
            i += 1
            continue

        # Parágrafo
        close_list()
        out.append(f"<p>{_inline(stripped)}</p>")
        i += 1

    close_list()
    return "\n".join(out)


@dataclass
class DossierSection:
    title: str
    markdown: str


_CSS = """
:root { --accent: #1f4e79; --muted: #666; --border: #d0d0d0; }
* { box-sizing: border-box; }
body { font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: #1a1a1a; line-height: 1.5; margin: 0; padding: 0; }
.page { max-width: 820px; margin: 0 auto; padding: 32px 40px; }
.cover { min-height: 90vh; display: flex; flex-direction: column; justify-content: center;
  border-bottom: 3px solid var(--accent); }
.cover .brand { font-size: 14px; letter-spacing: 2px; text-transform: uppercase; color: var(--accent); font-weight: 700; }
.cover h1 { font-size: 34px; margin: 12px 0 4px; }
.cover .sub { color: var(--muted); font-size: 15px; }
.cover .meta { margin-top: 24px; font-size: 13px; color: var(--muted); }
h1 { font-size: 26px; color: var(--accent); }
h2 { font-size: 20px; color: var(--accent); border-bottom: 1px solid var(--border); padding-bottom: 4px; margin-top: 28px; }
h3 { font-size: 16px; margin-top: 20px; }
h4 { font-size: 14px; margin-top: 16px; }
code { background: #f3f4f6; padding: 1px 5px; border-radius: 4px; font-size: 0.9em; }
blockquote { border-left: 3px solid var(--accent); margin: 12px 0; padding: 6px 14px; background: #f7f9fb; color: #333; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13px; }
th, td { border: 1px solid var(--border); padding: 6px 9px; text-align: left; vertical-align: top; }
th { background: var(--accent); color: #fff; }
tr:nth-child(even) td { background: #f7f9fb; }
hr { border: 0; border-top: 1px solid var(--border); margin: 18px 0; }
.toc { background: #f7f9fb; border: 1px solid var(--border); border-radius: 8px; padding: 16px 22px; }
.toc h2 { border: 0; margin-top: 0; }
.toc ol { margin: 0; padding-left: 22px; }
.section { page-break-inside: auto; }
.section + .section { page-break-before: always; }
footer { color: var(--muted); font-size: 11px; text-align: center; padding: 20px; border-top: 1px solid var(--border); }
@media print {
  .page { max-width: none; padding: 0 12mm; }
  .cover { min-height: 92vh; page-break-after: always; }
  .toc { page-break-after: always; }
  h2 { page-break-after: avoid; }
  table, blockquote { page-break-inside: avoid; }
}
"""


def build_dossier_html(
    title: str,
    sections: list[DossierSection],
    brand: str = "REGENTE",
    subtitle: str = "Dossier de Conformidade NIS2 / QNRCS",
    generated_at: str | None = None,
) -> str:
    """Constrói um documento HTML autossuficiente (CSS embebido) que agrega as
    secções, com capa, índice e quebras de página para impressão/PDF."""
    generated_at = generated_at or datetime.now().strftime("%Y-%m-%d")

    toc_items = "\n".join(
        f'<li><a href="#sec-{idx}">{html.escape(s.title)}</a></li>'
        for idx, s in enumerate(sections)
    )
    body_sections = "\n".join(
        f'<div class="section" id="sec-{idx}">\n<h1>{html.escape(s.title)}</h1>\n{md_to_html(s.markdown)}\n</div>'
        for idx, s in enumerate(sections)
    )

    return f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(title)} — {html.escape(brand)}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="page">
  <div class="cover">
    <div class="brand">{html.escape(brand)}</div>
    <h1>{html.escape(title)}</h1>
    <div class="sub">{html.escape(subtitle)}</div>
    <div class="meta">Gerado em {html.escape(generated_at)}</div>
  </div>

  <div class="toc">
    <h2>Índice</h2>
    <ol>
      {toc_items}
    </ol>
  </div>

  {body_sections}

  <footer>
    {html.escape(brand)} · {html.escape(subtitle)} · {html.escape(generated_at)}<br/>
    Documento de apoio à decisão — não substitui aconselhamento jurídico nem a decisão da autoridade competente.
  </footer>
</div>
</body>
</html>
"""


# Ordem e títulos canónicos dos deliverables Markdown conhecidos, para um
# dossier coerente quando se agrega uma pasta inteira de outputs.
_KNOWN_TITLES = {
    "self_identification.md": "Autoidentificação (MyCiber)",
    "risk_matrix.md": "Matriz de Risco (Anexo II)",
    "gap_report.md": "Gap Analysis",
    "roadmap.md": "Roadmap de Remediação",
    "statement_of_applicability.md": "Declaração de Aplicabilidade (SoA)",
    "iso27001_crosswalk.md": "Crosswalk ISO/IEC 27001/27002",
    "iso27001_document_checklist.md": "Checklist de Documentos do SGSI",
    "evidence_plan.md": "Plano de Recolha de Evidência",
    "deadlines.md": "Calendário de Obrigações",
    "audit_report.md": "Rastreabilidade Jurídica",
    "triagem_significancia.md": "Triagem de Impacto Significativo",
    "alerta_inicial_24h.md": "Alerta Inicial (24h)",
    "relatorio_detalhado_72h.md": "Relatório Detalhado (72h)",
    "fim_impacto_significativo.md": "Fim do Impacto Significativo (Art. 43.º)",
    "relatorio_final.md": "Relatório Final (Art. 44.º)",
    "portfolio.md": "Carteira de Clientes",
}
_ORDER = list(_KNOWN_TITLES.keys())


def _title_for(filename: str) -> str:
    if filename in _KNOWN_TITLES:
        return _KNOWN_TITLES[filename]
    stem = Path(filename).stem.replace("_", " ").replace("-", " ")
    return stem.capitalize()


def collect_sections(md_dir: Path) -> list[DossierSection]:
    """Recolhe os ficheiros .md de uma pasta como secções do dossier, ordenando
    os deliverables conhecidos pela ordem canónica e os restantes a seguir,
    por nome."""
    files = sorted(p.name for p in md_dir.glob("*.md"))
    known = [f for f in _ORDER if f in files]
    others = sorted(f for f in files if f not in _KNOWN_TITLES)
    sections: list[DossierSection] = []
    for filename in known + others:
        text = (md_dir / filename).read_text(encoding="utf-8")
        sections.append(DossierSection(title=_title_for(filename), markdown=text))
    return sections


def render_pdf(html_content: str, out_path: Path) -> bool:
    """Tenta produzir um PDF a partir do HTML. Oportunista: weasyprint →
    Chromium (Playwright). Devolve True se gerou o PDF, False caso contrário
    (cabe ao chamador guardar o HTML imprimível em alternativa)."""
    # 1) weasyprint (se instalado)
    try:
        from weasyprint import HTML as _WeasyHTML  # type: ignore

        _WeasyHTML(string=html_content).write_pdf(str(out_path))
        return True
    except Exception:
        pass

    # 2) Chromium via Playwright (se disponível no ambiente)
    try:
        import tempfile

        from playwright.sync_api import sync_playwright

        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tmp:
            tmp.write(html_content)
            tmp_path = tmp.name
        chromium_path = "/opt/pw-browsers/chromium"
        launch_kwargs = {}
        if Path(chromium_path).exists():
            launch_kwargs["executable_path"] = chromium_path
        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kwargs)
            page = browser.new_page()
            page.goto(f"file://{tmp_path}")
            page.pdf(path=str(out_path), format="A4", print_background=True)
            browser.close()
        return True
    except Exception:
        return False
