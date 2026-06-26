"""Perfis setoriais pré-preenchidos para os verticais típicos do consultor
(autarquias, juntas de freguesia, hotelaria, turismo).

Cada perfil reúne, para um setor, um ponto de partida realista: uma entidade
tipo, cenários de risco habituais (para a Matriz de Risco do Anexo II), ativos
críticos e notas de prioridade — incluindo a nota de âmbito, que é decisiva
para os verticais (turismo/hotelaria) que NÃO constam dos anexos do DL
125/2025 e só entram em âmbito indiretamente (cadeia de abastecimento).

Os perfis são dados (`data/sector_profiles/*.yaml`), não código: acrescentar um
vertical é criar um ficheiro YAML, sem tocar no motor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

PROFILES_DIR = Path(__file__).resolve().parent.parent / "data" / "sector_profiles"


@dataclass
class ProfileScenario:
    """Cenário de risco típico do setor, no formato consumível pela Matriz de
    Risco (probabilidade e impacto em escala 1-5)."""

    name: str
    probabilidade: int
    impacto: int
    threat_actor: str = ""
    description: str = ""


@dataclass
class SectorProfile:
    id: str
    nome: str
    descricao: str
    setor: str
    employees: int
    annual_turnover_eur: float
    is_public_body: bool
    ambito_nota: str
    cenarios: list[ProfileScenario] = field(default_factory=list)
    ativos_criticos: list[str] = field(default_factory=list)
    notas: list[str] = field(default_factory=list)
    # Nível de referência sugerido quando a classificação setorial direta não o
    # determina (ex.: turismo/hotelaria, fora de âmbito por setor mas com uma
    # linha de base voluntária recomendada — tipicamente "basico").
    nivel_referencia_sugerido: str | None = None

    def entity_dict(self) -> dict:
        """Dicionário pronto a escrever como `entity.yaml` e a ser lido pelo
        `load_entity` da CLI."""
        return {
            "name": self.nome,
            "sector": self.setor,
            "employees": self.employees,
            "annual_turnover_eur": self.annual_turnover_eur,
            "is_public_body": self.is_public_body,
        }

    def scenarios_dict(self) -> dict:
        """Dicionário pronto a escrever como `scenarios.yaml` e a ser lido pelo
        `load_risk_scenarios` da CLI."""
        return {
            "scenarios": [
                {
                    "name": c.name,
                    "threat_actor": c.threat_actor,
                    "probabilidade": c.probabilidade,
                    "impacto": c.impacto,
                    "description": c.description,
                }
                for c in self.cenarios
            ]
        }


def _parse_profile(raw: dict) -> SectorProfile:
    entidade = raw.get("entidade", {})
    cenarios = [
        ProfileScenario(
            name=c["name"],
            probabilidade=int(c["probabilidade"]),
            impacto=int(c["impacto"]),
            threat_actor=c.get("threat_actor", ""),
            description=c.get("description", ""),
        )
        for c in raw.get("cenarios", [])
    ]
    return SectorProfile(
        id=raw["id"],
        nome=raw["nome"],
        descricao=raw.get("descricao", "").strip(),
        setor=raw["setor"],
        employees=int(entidade.get("employees", 0)),
        annual_turnover_eur=float(entidade.get("annual_turnover_eur", 0)),
        is_public_body=bool(entidade.get("is_public_body", False)),
        ambito_nota=raw.get("ambito_nota", "").strip(),
        cenarios=cenarios,
        ativos_criticos=list(raw.get("ativos_criticos", [])),
        notas=list(raw.get("notas", [])),
        nivel_referencia_sugerido=raw.get("nivel_referencia_sugerido"),
    )


def load_profiles(profiles_dir: Path = PROFILES_DIR) -> list[SectorProfile]:
    """Carrega todos os perfis setoriais, ordenados por id."""
    profiles: list[SectorProfile] = []
    for path in sorted(profiles_dir.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        profiles.append(_parse_profile(raw))
    return profiles


def get_profile(profile_id: str, profiles_dir: Path = PROFILES_DIR) -> SectorProfile:
    """Devolve o perfil com o id indicado ou levanta KeyError com a lista de
    ids disponíveis."""
    for profile in load_profiles(profiles_dir):
        if profile.id == profile_id:
            return profile
    disponiveis = ", ".join(p.id for p in load_profiles(profiles_dir))
    raise KeyError(f"Perfil '{profile_id}' não encontrado. Disponíveis: {disponiveis}")
