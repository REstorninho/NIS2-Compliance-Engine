from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import AssessmentResult, GapItem

# Os 4 temas da ISO/IEC 27002:2022 (substituem os 14 domínios da versão de
# 2013). Derivados do prefixo do identificador Annex A já presente no
# crosswalk de cada controlo (`A.5.x`→Organizacionais, `A.6.x`→Pessoas,
# `A.7.x`→Físicos, `A.8.x`→Tecnológicos) — não é um dado novo, é uma leitura
# diferente do crosswalk legal já validado por fonte.
ISO27002_THEME_BY_PREFIX = {
    "A.5": "Organizacionais",
    "A.6": "Pessoas",
    "A.7": "Físicos",
    "A.8": "Tecnológicos",
}
ISO27002_THEME_ORDER = ["Organizacionais", "Pessoas", "Físicos", "Tecnológicos"]

# Domínio de segurança ISO/IEC 27002:2022 por função QNRCS/NIST CSF 2.0 —
# alinhamento direto com a matriz de crosswalk multi-norma do documento de
# referência (NIST CSF↔ISO 27001/27002), não uma atribuição por controlo.
ISO27002_DOMAIN_BY_FUNCTION = {
    "Governar": "Governance_and_Ecosystem",
    "Identificar": "Governance_and_Ecosystem",
    "Proteger": "Protection",
    "Detetar": "Defence",
    "Responder": "Defence",
    "Recuperar": "Resilience",
}

# As 10 medidas mínimas de gestão de risco do Art. 21.º, n.º 2 da Diretiva
# NIS2, com o catálogo ISO/IEC 27002:2022 de referência para cada uma
# (documento de referência técnico-normativo, secção 6.2).
ART21_MEASURES = {
    "a": {
        "descricao": "Políticas de análise de risco e de segurança dos sistemas de informação",
        "iso_refs": ["5.1", "5.7", "6.1.2/6.1.3 (27001)"],
    },
    "b": {
        "descricao": "Gestão de incidentes",
        "iso_refs": ["5.24", "5.25", "5.26", "5.27", "5.28", "série 27035"],
    },
    "c": {
        "descricao": "Continuidade de negócio, backup, recuperação de desastres e gestão de crises",
        "iso_refs": ["5.29", "5.30", "8.13", "8.14", "27031"],
    },
    "d": {
        "descricao": "Segurança da cadeia de fornecimento",
        "iso_refs": ["5.19", "5.20", "5.21", "5.22", "série 27036"],
    },
    "e": {
        "descricao": "Segurança na aquisição, desenvolvimento e manutenção; gestão e divulgação de vulnerabilidades",
        "iso_refs": ["8.8", "8.9", "8.25", "8.26", "8.27", "8.28", "8.29", "8.30", "8.31"],
    },
    "f": {
        "descricao": "Políticas e procedimentos para avaliar a eficácia das medidas",
        "iso_refs": ["9.1 (27001)", "27004"],
    },
    "g": {
        "descricao": "Práticas básicas de higiene cibernética e formação",
        "iso_refs": ["6.3", "8.7", "8.9", "8.23"],
    },
    "h": {
        "descricao": "Políticas de criptografia e cifragem",
        "iso_refs": ["8.24", "8.11"],
    },
    "i": {
        "descricao": "Segurança de recursos humanos, controlo de acessos e gestão de ativos",
        "iso_refs": ["5.9", "5.10", "5.11", "5.12", "5.13", "5.14", "5.15", "5.16", "5.17", "5.18", "6.1", "6.2", "6.4", "6.5", "6.6", "8.2", "8.3", "8.4", "8.5"],
    },
    "j": {
        "descricao": "MFA, comunicações seguras de voz/vídeo/texto e comunicações de emergência",
        "iso_refs": ["8.5", "8.20", "8.21", "8.24"],
    },
}
ART21_MEASURE_ORDER = list(ART21_MEASURES.keys())

_ART21_LETTER_RE = re.compile(r"Art\.\s*21\(2\)\(([a-j])\)")


def iso27002_theme(annex_a_id: str) -> str | None:
    """Tema ISO/IEC 27002:2022 a que pertence um identificador Annex A
    (ex: 'A.8.16' → 'Tecnológicos')."""
    for prefix, theme in ISO27002_THEME_BY_PREFIX.items():
        if annex_a_id.startswith(prefix):
            return theme
    return None


def art21_measure_letters(gap: GapItem) -> list[str]:
    """Extrai as letras das medidas do Art. 21.º/2 (a-j) citadas no crosswalk
    legal do controlo (ex: 'Art. 21(2)(b)' → ['b'])."""
    letters: list[str] = []
    for article in gap.control.crosswalk.nis2_article:
        letters.extend(_ART21_LETTER_RE.findall(article))
    return letters


@dataclass
class ISO27002ThemeGroup:
    theme: str
    gaps: list[GapItem] = field(default_factory=list)

    @property
    def implemented_count(self) -> int:
        return sum(1 for g in self.gaps if g.implemented)

    @property
    def coverage_pct(self) -> float:
        if not self.gaps:
            return 0.0
        return round(self.implemented_count / len(self.gaps) * 100, 1)


@dataclass
class ART21MeasureGroup:
    letter: str
    descricao: str
    iso_refs: list[str]
    gaps: list[GapItem] = field(default_factory=list)

    @property
    def implemented_count(self) -> int:
        return sum(1 for g in self.gaps if g.implemented)

    @property
    def coverage_pct(self) -> float:
        if not self.gaps:
            return 0.0
        return round(self.implemented_count / len(self.gaps) * 100, 1)


@dataclass
class ISO27001Crosswalk:
    """Relatório de crosswalk dual NIS2 ↔ ISO/IEC 27001/27002:2022, gerado a
    partir de um `AssessmentResult` já calculado — sem reavaliar nenhum
    controlo, apenas reagrupando o mesmo gap-analysis por tema ISO27002 e por
    medida do Art. 21.º/2, para suportar uma trajetória de certificação ISO
    27001 sobre o trabalho de conformidade NIS2 já feito."""

    result: AssessmentResult
    by_theme: list[ISO27002ThemeGroup]
    by_measure: list[ART21MeasureGroup]
    uncited_gaps: list[GapItem] = field(default_factory=list)

    @property
    def annex_a_refs_cited(self) -> int:
        return sum(len(g.control.crosswalk.iso27001_annex_a) for g in self.result.gaps)


def build_iso27001_crosswalk(result: AssessmentResult) -> ISO27001Crosswalk:
    by_theme_map: dict[str, ISO27002ThemeGroup] = {
        theme: ISO27002ThemeGroup(theme=theme) for theme in ISO27002_THEME_ORDER
    }
    by_measure_map: dict[str, ART21MeasureGroup] = {
        letter: ART21MeasureGroup(letter=letter, descricao=data["descricao"], iso_refs=data["iso_refs"])
        for letter, data in ART21_MEASURES.items()
    }
    uncited_gaps: list[GapItem] = []

    for gap in result.gaps:
        annex_refs = gap.control.crosswalk.iso27001_annex_a
        themes_for_gap = {iso27002_theme(ref) for ref in annex_refs} - {None}
        for theme in themes_for_gap:
            by_theme_map[theme].gaps.append(gap)
        if not themes_for_gap:
            uncited_gaps.append(gap)

        for letter in art21_measure_letters(gap):
            if letter in by_measure_map:
                by_measure_map[letter].gaps.append(gap)

    return ISO27001Crosswalk(
        result=result,
        by_theme=[by_theme_map[t] for t in ISO27002_THEME_ORDER if by_theme_map[t].gaps],
        by_measure=[by_measure_map[l] for l in ART21_MEASURE_ORDER if by_measure_map[l].gaps],
        uncited_gaps=uncited_gaps,
    )


# Os 11 documentos mínimos exigidos para um SGSI certificável segundo a
# ISO/IEC 27001:2022 (documento de referência técnico-normativo, secção 3.3),
# usados para gerar um checklist complementar à Statement of Applicability já
# produzida pelo motor NIS2.
ISO27001_MANDATORY_DOCUMENTS = [
    {"clausula": "4.3", "documento": "Âmbito do SGSI"},
    {"clausula": "5.2", "documento": "Política de segurança da informação"},
    {"clausula": "6.1.2", "documento": "Processo de apreciação de risco"},
    {"clausula": "6.1.3", "documento": "Processo de tratamento de risco"},
    {"clausula": "6.1.3 d)", "documento": "Declaração de Aplicabilidade (SoA)"},
    {"clausula": "6.2", "documento": "Objetivos de segurança da informação"},
    {"clausula": "7.2", "documento": "Evidências de competência"},
    {"clausula": "9.1", "documento": "Resultados de monitorização e medição"},
    {"clausula": "9.2", "documento": "Programa e resultados de auditoria interna"},
    {"clausula": "9.3", "documento": "Resultados da revisão pela gestão"},
    {"clausula": "10.2", "documento": "Registos de não conformidades e ações corretivas"},
]
