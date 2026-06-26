"""Web app local do motor NIS2 — uma alternativa ao YAML/CLI para introduzir
dados por formulário, escolher os deliverables e exportar em Markdown e PDF.

Princípios:
- **Reutiliza o motor real** (`nis2_engine`): o servidor corre `classify_entity`,
  `build_risk_matrix`, `run_assessment`, etc. — nada de duplicar lógica em JS.
- **Zero dependências novas**: usa `http.server` da biblioteca padrão e Jinja2
  (que já é dependência do projeto) para os templates.
- A geração de deliverables (`generate_deliverables`) é independente do HTTP e
  testável isoladamente; o handler HTTP é fino.

Arranca com `nis2 serve`.
"""

from __future__ import annotations

import json
import tempfile
import zipfile
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .assessment import run_assessment
from .classification import classify_entity, required_compliance_level
from .dossier import build_dossier_html, collect_sections, render_pdf
from .iso27001 import build_iso27001_crosswalk
from .loader import load_controls
from .models import AssessmentAnswer, ComplianceLevel, Entity, EntityType
from .profiles import get_profile, load_profiles
from .reporting import (
    build_classifier_config,
    render_evidence_plan,
    render_gap_report,
    render_html_report,
    render_iso27001_crosswalk,
    render_iso27001_document_checklist,
    render_maturity_radar,
    render_risk_matrix,
    render_roadmap,
    render_self_identification,
    render_soa,
)
from .risk_matrix import RiskScenario, build_risk_matrix
from .roadmap import build_remediation_roadmap
from .soa import build_statement_of_applicability

# Deliverables que o utilizador pode escolher gerar. `assessment` indica os que
# dependem da autoavaliação de maturidade (questionário).
DELIVERABLES = [
    {"id": "self_identification", "file": "self_identification.md", "label": "Autoidentificação (MyCiber)", "assessment": False},
    {"id": "risk_matrix", "file": "risk_matrix.md", "label": "Matriz de Risco (Anexo II)", "assessment": False},
    {"id": "gap_report", "file": "gap_report.md", "label": "Gap Analysis", "assessment": True},
    {"id": "roadmap", "file": "roadmap.md", "label": "Roadmap de Remediação", "assessment": True},
    {"id": "soa", "file": "statement_of_applicability.md", "label": "Declaração de Aplicabilidade (SoA)", "assessment": True},
    {"id": "evidence_plan", "file": "evidence_plan.md", "label": "Plano de Recolha de Evidência", "assessment": True},
    {"id": "iso27001_crosswalk", "file": "iso27001_crosswalk.md", "label": "Crosswalk ISO 27001/27002", "assessment": True},
    {"id": "iso27001_document_checklist", "file": "iso27001_document_checklist.md", "label": "Checklist de Documentos do SGSI", "assessment": True},
]
_ASSESSMENT_IDS = {d["id"] for d in DELIVERABLES if d["assessment"]}


@dataclass
class GenerationResult:
    entity_name: str
    entity_type: str
    nivel_referencia: str
    nivel_efetivo: str
    score_pct: float | None
    maturity_pct: float | None
    open_gaps: int | None
    files: list[str]
    avisos: list[str]


def _entity_from_form(form: dict) -> Entity:
    return Entity(
        name=(form.get("name") or "Entidade sem nome").strip(),
        sector=(form.get("sector") or "outro").strip(),
        employees=int(form.get("employees") or 0),
        annual_turnover_eur=float(form.get("turnover") or 0),
        is_public_body=bool(form.get("is_public_body")),
    )


def _scenarios_from_form(form: dict) -> list[RiskScenario]:
    names = form.get("scn_name", [])
    actors = form.get("scn_actor", [])
    probs = form.get("scn_prob", [])
    impacts = form.get("scn_impact", [])
    scenarios: list[RiskScenario] = []
    for i, name in enumerate(names):
        name = (name or "").strip()
        if not name:
            continue
        try:
            prob = int(probs[i])
            impacto = int(impacts[i])
        except (ValueError, IndexError):
            continue
        scenarios.append(
            RiskScenario(
                name=name,
                probabilidade=prob,
                impacto=impacto,
                threat_actor=(actors[i] if i < len(actors) else "").strip(),
            )
        )
    return scenarios


def _answers_from_form(form: dict, controls) -> list[AssessmentAnswer]:
    answers: list[AssessmentAnswer] = []
    for c in controls:
        raw = form.get(f"mat_{c.id}")
        maturity = int(raw) if raw not in (None, "") else 0
        answers.append(AssessmentAnswer(control_id=c.id, implemented=maturity >= 3, maturity=maturity))
    return answers


def generate_deliverables(form: dict, out_dir: Path, brand: str = "REGENTE") -> GenerationResult:
    """Corre o motor com os dados do formulário e escreve os deliverables
    selecionados em `out_dir`. Devolve um resumo para a página de resultados.

    `form` aceita valores simples (str) e listas (campos repetidos do
    questionário/cenários), como devolvido por `parse_qs`.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    entity = _entity_from_form(form)
    entity_type = classify_entity(entity)
    nivel_referencia = (
        None if entity_type is EntityType.FORA_DE_AMBITO else required_compliance_level(entity_type)
    )

    scenarios = _scenarios_from_form(form)
    matrix = build_risk_matrix(entity, scenarios, nivel_referencia=nivel_referencia) if scenarios else None

    # Nível-alvo: override explícito > matriz (efetivo) > referência por tipo >
    # básico (linha de base voluntária para entidades fora de âmbito).
    override = form.get("level") or ""
    if override:
        target = ComplianceLevel(override)
    elif matrix is not None:
        target = matrix.nivel_efetivo
    elif nivel_referencia is not None:
        target = nivel_referencia
    else:
        target = ComplianceLevel.BASICO

    selected = set(form.get("deliv", []))
    if isinstance(selected, str):  # defensivo
        selected = {selected}
    include_assessment = bool(form.get("include_assessment")) and bool(selected & _ASSESSMENT_IDS)

    files: list[str] = []
    avisos: list[str] = list(matrix.avisos) if matrix else []

    def _write(name: str, content: str) -> None:
        (out_dir / name).write_text(content, encoding="utf-8")
        files.append(name)

    if "self_identification" in selected:
        _write("self_identification.md", render_self_identification(entity, entity_type, target))
    if matrix is not None and "risk_matrix" in selected:
        _write("risk_matrix.md", render_risk_matrix(matrix))

    score = maturity = None
    open_gaps = None
    if include_assessment:
        controls = load_controls()
        answers = _answers_from_form(form, controls)
        result = run_assessment(entity, target, controls, answers)
        score = result.score_pct
        maturity = result.maturity_score_pct
        open_gaps = sum(1 for g in result.gaps if not g.implemented)
        if "gap_report" in selected:
            _write("gap_report.md", render_gap_report(result))
        if "roadmap" in selected:
            _write("roadmap.md", render_roadmap(build_remediation_roadmap(result)))
        if "soa" in selected:
            _write("statement_of_applicability.md", render_soa(build_statement_of_applicability(result, controls)))
        if "evidence_plan" in selected:
            _write("evidence_plan.md", render_evidence_plan(result))
        if "iso27001_crosswalk" in selected:
            _write("iso27001_crosswalk.md", render_iso27001_crosswalk(build_iso27001_crosswalk(result)))
        if "iso27001_document_checklist" in selected:
            _write("iso27001_document_checklist.md", render_iso27001_document_checklist(entity))
        # Extras visuais sempre úteis com a autoavaliação.
        (out_dir / "report.html").write_text(render_html_report(result, entity_type, brand=brand), encoding="utf-8")
        (out_dir / "maturity_radar.svg").write_text(render_maturity_radar(result), encoding="utf-8")

    return GenerationResult(
        entity_name=entity.name,
        entity_type=entity_type.value,
        nivel_referencia=nivel_referencia.value if nivel_referencia else "—",
        nivel_efetivo=target.value,
        score_pct=score,
        maturity_pct=maturity,
        open_gaps=open_gaps,
        files=files,
        avisos=avisos,
    )


def build_app_config() -> dict:
    """Configuração injetada na página: setores/controlos/níveis (fonte de
    verdade do motor) + perfis setoriais para o prefil no browser."""
    config = build_classifier_config()
    config["profiles"] = [
        {
            "id": p.id,
            "nome": p.nome,
            "setor": p.setor,
            "employees": p.employees,
            "turnover": p.annual_turnover_eur,
            "is_public_body": p.is_public_body,
            "ambito_nota": p.ambito_nota,
            "nivel_sugerido": p.nivel_referencia_sugerido or "",
            "scenarios": [
                {"name": c.name, "actor": c.threat_actor, "prob": c.probabilidade, "impacto": c.impacto}
                for c in p.cenarios
            ],
        }
        for p in load_profiles()
    ]
    config["deliverables"] = DELIVERABLES
    return config


# ---------------------------------------------------------------------------
# Camada HTTP (fina) — usa Jinja2 via reporting._web_env para os templates.
# ---------------------------------------------------------------------------


def _render_template(name: str, **ctx) -> str:
    from .reporting import _web_env  # import tardio: evita ciclo no arranque

    return _web_env().get_template(name).render(**ctx)


_SESSIONS: dict[str, Path] = {}


def _make_handler(brand: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "nis2-webapp/1.0"

        def log_message(self, *args):  # silencia o log por request
            pass

        def _send(self, body: bytes, status: int = 200, content_type: str = "text/html; charset=utf-8", extra=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            if path in ("/", "/index.html"):
                html = _render_template("app_form.html.j2", brand=brand, config_json=json.dumps(build_app_config(), ensure_ascii=False))
                self._send(html.encode("utf-8"))
                return
            if path.startswith("/api/profile/"):
                pid = path.rsplit("/", 1)[-1]
                try:
                    p = get_profile(pid)
                except KeyError:
                    self._send(b'{"error":"not found"}', status=404, content_type="application/json")
                    return
                payload = {
                    "nome": p.nome, "setor": p.setor, "employees": p.employees,
                    "turnover": p.annual_turnover_eur, "is_public_body": p.is_public_body,
                    "ambito_nota": p.ambito_nota, "nivel_sugerido": p.nivel_referencia_sugerido or "",
                    "scenarios": [
                        {"name": c.name, "actor": c.threat_actor, "prob": c.probabilidade, "impacto": c.impacto}
                        for c in p.cenarios
                    ],
                }
                self._send(json.dumps(payload, ensure_ascii=False).encode("utf-8"), content_type="application/json")
                return
            if path.startswith("/download/"):
                self._handle_download(path)
                return
            self._send(b"Not found", status=404, content_type="text/plain; charset=utf-8")

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path != "/generate":
                self._send(b"Not found", status=404, content_type="text/plain; charset=utf-8")
                return
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8")
            parsed_form = parse_qs(raw, keep_blank_values=True)
            # Normaliza: campos de valor único como str, repetidos como lista.
            form: dict = {}
            for k, v in parsed_form.items():
                if k in ("scn_name", "scn_actor", "scn_prob", "scn_impact", "deliv"):
                    form[k] = v
                else:
                    form[k] = v[0]

            session_dir = Path(tempfile.mkdtemp(prefix="nis2web_"))
            sid = session_dir.name
            _SESSIONS[sid] = session_dir
            try:
                result = generate_deliverables(form, session_dir, brand=brand)
            except Exception as exc:  # erro amigável na própria página
                html = _render_template("app_result.html.j2", brand=brand, error=str(exc), result=None, sid=sid)
                self._send(html.encode("utf-8"), status=400)
                return
            html = _render_template("app_result.html.j2", brand=brand, error=None, result=result, sid=sid)
            self._send(html.encode("utf-8"))

        def _handle_download(self, path: str):
            # /download/<sid>/<name>
            parts = path.split("/", 3)
            if len(parts) < 4:
                self._send(b"Not found", status=404, content_type="text/plain; charset=utf-8")
                return
            sid, name = parts[2], parts[3]
            session_dir = _SESSIONS.get(sid)
            if not session_dir:
                self._send("Sessão expirada".encode("utf-8"), status=404, content_type="text/plain; charset=utf-8")
                return

            if name == "_all.zip":
                import io

                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for f in sorted(session_dir.glob("*")):
                        if f.is_file():
                            zf.write(f, f.name)
                self._send(buf.getvalue(), content_type="application/zip", extra={"Content-Disposition": 'attachment; filename="nis2_deliverables.zip"'})
                return

            if name in ("dossier.html", "dossier.pdf"):
                sections = collect_sections(session_dir)
                html_doc = build_dossier_html("Relatório de Conformidade NIS2", sections, brand=brand)
                if name == "dossier.html":
                    self._send(html_doc.encode("utf-8"), extra={"Content-Disposition": 'attachment; filename="dossier.html"'})
                    return
                pdf_path = session_dir / "dossier.pdf"
                if render_pdf(html_doc, pdf_path):
                    self._send(pdf_path.read_bytes(), content_type="application/pdf", extra={"Content-Disposition": 'attachment; filename="dossier.pdf"'})
                else:
                    msg = ("Sem motor de PDF no servidor (weasyprint/Chromium). "
                           "Descarregue o dossier HTML e use Imprimir -> Guardar como PDF.")
                    self._send(msg.encode("utf-8"), status=503, content_type="text/plain; charset=utf-8")
                return

            target = (session_dir / name).resolve()
            if session_dir.resolve() not in target.parents or not target.is_file():
                self._send(b"Not found", status=404, content_type="text/plain; charset=utf-8")
                return
            ctype = "text/markdown; charset=utf-8" if target.suffix == ".md" else "application/octet-stream"
            if target.suffix == ".html":
                ctype = "text/html; charset=utf-8"
            elif target.suffix == ".svg":
                ctype = "image/svg+xml"
            self._send(target.read_bytes(), content_type=ctype)

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8000, brand: str = "REGENTE", open_browser: bool = True) -> None:
    """Arranca a web app local. Bloqueia até Ctrl+C."""
    handler = _make_handler(brand)
    httpd = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{port}/"
    print(f"NIS2 web app a correr em {url}  (Ctrl+C para parar)")
    if open_browser:
        try:
            import webbrowser

            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nA encerrar a web app.")
    finally:
        httpd.server_close()
