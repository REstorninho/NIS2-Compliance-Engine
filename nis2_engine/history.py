from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .models import AssessmentResult


@dataclass
class AssessmentSnapshot:
    """Fotografia serializável de um AssessmentResult num dado momento —
    permite comparar a evolução da maturidade de uma entidade ao longo do
    tempo sem depender dos objetos completos (Entity/Control)."""

    entity_name: str
    sector: str
    target_level: str
    generated_at: str  # ISO 8601
    score_pct: float
    maturity_score_pct: float
    maturity_by_function: dict[str, float] = field(default_factory=dict)
    # control_id -> {"implemented": bool, "maturity": int, "priority": str}
    control_status: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "entity_name": self.entity_name,
            "sector": self.sector,
            "target_level": self.target_level,
            "generated_at": self.generated_at,
            "score_pct": self.score_pct,
            "maturity_score_pct": self.maturity_score_pct,
            "maturity_by_function": self.maturity_by_function,
            "control_status": self.control_status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AssessmentSnapshot":
        return cls(**data)


@dataclass
class ProgressDelta:
    entity_name: str
    from_date: str
    to_date: str
    score_delta: float
    maturity_delta: float
    maturity_by_function_delta: dict[str, float] = field(default_factory=dict)
    newly_implemented: list[str] = field(default_factory=list)
    regressed: list[str] = field(default_factory=list)


def build_snapshot(result: AssessmentResult, generated_at: str | None = None) -> AssessmentSnapshot:
    generated_at = generated_at or datetime.now().isoformat(timespec="microseconds")
    control_status = {
        gap.control.id: {
            "implemented": gap.implemented,
            "maturity": gap.maturity,
            "priority": gap.priority,
        }
        for gap in result.gaps
    }
    return AssessmentSnapshot(
        entity_name=result.entity.name,
        sector=result.entity.sector,
        target_level=result.target_level.value,
        generated_at=generated_at,
        score_pct=result.score_pct,
        maturity_score_pct=result.maturity_score_pct,
        maturity_by_function=dict(result.maturity_by_function),
        control_status=control_status,
    )


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def save_snapshot(snapshot: AssessmentSnapshot, history_dir: Path) -> Path:
    history_dir.mkdir(parents=True, exist_ok=True)
    timestamp = re.sub(r"[^0-9]", "", snapshot.generated_at)
    path = history_dir / f"{_slug(snapshot.entity_name)}_{timestamp}.json"
    path.write_text(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_snapshots(history_dir: Path, entity_name: str) -> list[AssessmentSnapshot]:
    if not history_dir.exists():
        return []
    prefix = _slug(entity_name)
    snapshots = []
    for path in sorted(history_dir.glob(f"{prefix}_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        snapshot = AssessmentSnapshot.from_dict(data)
        # O slug é só para o nome do ficheiro — dois nomes distintos podem
        # colidir no mesmo slug (ex. "Município A" vs "Municipio-A"). Filtra
        # pelo nome exato gravado no snapshot para evitar misturar entidades.
        if snapshot.entity_name == entity_name:
            snapshots.append(snapshot)
    return sorted(snapshots, key=lambda s: s.generated_at)


@dataclass
class PortfolioEntry:
    """Linha da carteira de clientes: estado mais recente de uma entidade,
    com a tendência face ao assessment anterior."""

    entity_name: str
    sector: str
    target_level: str
    latest_date: str
    score_pct: float
    maturity_score_pct: float
    assessments_count: int
    trend: str  # "↑" / "↓" / "→"


def _all_snapshots(history_dir: Path) -> list[AssessmentSnapshot]:
    snapshots = []
    for path in sorted(history_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        snapshots.append(AssessmentSnapshot.from_dict(data))
    return snapshots


def build_portfolio(history_dir: Path) -> list[PortfolioEntry]:
    """Constrói a carteira de clientes a partir de todos os snapshots gravados:
    uma linha por entidade (pelo nome exato), com o estado mais recente e a
    tendência de score face ao assessment imediatamente anterior."""
    if not history_dir.exists():
        return []

    by_entity: dict[str, list[AssessmentSnapshot]] = {}
    for snap in _all_snapshots(history_dir):
        by_entity.setdefault(snap.entity_name, []).append(snap)

    entries: list[PortfolioEntry] = []
    for name, snaps in by_entity.items():
        snaps = sorted(snaps, key=lambda s: s.generated_at)
        latest = snaps[-1]
        if len(snaps) >= 2:
            prev = snaps[-2]
            if latest.score_pct > prev.score_pct:
                trend = "↑"
            elif latest.score_pct < prev.score_pct:
                trend = "↓"
            else:
                trend = "→"
        else:
            trend = "→"
        entries.append(
            PortfolioEntry(
                entity_name=name,
                sector=latest.sector,
                target_level=latest.target_level,
                latest_date=latest.generated_at,
                score_pct=latest.score_pct,
                maturity_score_pct=latest.maturity_score_pct,
                assessments_count=len(snaps),
                trend=trend,
            )
        )
    return sorted(entries, key=lambda e: e.score_pct)


def compare_snapshots(old: AssessmentSnapshot, new: AssessmentSnapshot) -> ProgressDelta:
    """Compara dois snapshots da mesma entidade e devolve a evolução: score,
    maturidade por função, e que controlos passaram a/deixaram de estar
    implementados entre as duas datas."""
    maturity_by_function_delta = {
        function: round(new.maturity_by_function.get(function, 0.0) - old.maturity_by_function.get(function, 0.0), 2)
        for function in set(old.maturity_by_function) | set(new.maturity_by_function)
    }

    newly_implemented = [
        control_id
        for control_id, status in new.control_status.items()
        if status["implemented"] and not old.control_status.get(control_id, {}).get("implemented", False)
    ]
    regressed = [
        control_id
        for control_id, status in new.control_status.items()
        if not status["implemented"] and old.control_status.get(control_id, {}).get("implemented", False)
    ]

    return ProgressDelta(
        entity_name=new.entity_name,
        from_date=old.generated_at,
        to_date=new.generated_at,
        score_delta=round(new.score_pct - old.score_pct, 1),
        maturity_delta=round(new.maturity_score_pct - old.maturity_score_pct, 1),
        maturity_by_function_delta=maturity_by_function_delta,
        newly_implemented=sorted(newly_implemented),
        regressed=sorted(regressed),
    )
