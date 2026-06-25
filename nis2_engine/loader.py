from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import validate

from .models import Control, Crosswalk

_DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
_SCHEMA_PATH = _DATA_ROOT / "schema" / "control.schema.json"
_CONTROLS_DIR = _DATA_ROOT / "controls"


def _load_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def load_controls(controls_dir: Path | None = None) -> list[Control]:
    """Carrega e valida todos os controlos YAML em controls_dir contra o schema."""
    controls_dir = controls_dir or _CONTROLS_DIR
    schema = _load_schema()
    controls: list[Control] = []

    for path in sorted(controls_dir.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        validate(instance=raw, schema=schema)

        crosswalk_raw = raw.get("crosswalk", {})
        controls.append(
            Control(
                id=raw["id"],
                title=raw["title"],
                qnrcs_function=raw["qnrcs_function"],
                levels=raw["levels"],
                evidence_type=raw["evidence_type"],
                description=raw.get("description", ""),
                crosswalk=Crosswalk(**crosswalk_raw),
                evidence_contract=raw.get("evidence_contract"),
                estado_validacao=raw.get("estado_validacao", "por_validar"),
                fonte=raw.get("fonte", ""),
            )
        )

    _assert_unique_ids(controls)
    return controls


def _assert_unique_ids(controls: list[Control]) -> None:
    seen: set[str] = set()
    for control in controls:
        if control.id in seen:
            raise ValueError(f"ID de controlo duplicado: {control.id}")
        seen.add(control.id)
