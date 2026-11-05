"""Save / load a whole project as JSON (the hosted app keeps nothing server-side)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields as dc_fields

from .bva import MODES
from .combiner import STRATEGIES
from .models import Condition, FieldSpec

PROJECT_VERSION = 1


class ProjectError(ValueError):
    """Raised when a project file cannot be loaded."""


@dataclass
class Project:
    name: str = "My project"
    prefix: str = "TC"
    bva_mode: str = "3-value"
    strategy: str = "vary_one"
    fields: list[FieldSpec] = field(default_factory=list)
    conditions: list[Condition] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    action_map: dict[str, list[str]] = field(default_factory=dict)
    constraints: list[dict[str, str]] = field(default_factory=list)
    version: int = PROJECT_VERSION


def project_to_json(p: Project) -> str:
    return json.dumps(asdict(p), indent=2, ensure_ascii=False, default=str)


def _build(cls, data):
    if not isinstance(data, dict):
        raise ProjectError(f"Expected an object for {cls.__name__}.")
    allowed = {f.name for f in dc_fields(cls)}
    try:
        return cls(**{k: v for k, v in data.items() if k in allowed})
    except TypeError as e:
        raise ProjectError(f"Invalid {cls.__name__}: {e}") from None


def project_from_json(text: str | bytes) -> Project:
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ProjectError("This file is not valid JSON.") from None
    if not isinstance(data, dict):
        raise ProjectError("A project file must contain a JSON object.")
    if int(data.get("version", 1)) > PROJECT_VERSION:
        raise ProjectError("This project was saved by a newer version of the app.")
    p = Project(
        name=str(data.get("name", "My project")),
        prefix=str(data.get("prefix", "TC")),
        bva_mode=data.get("bva_mode") if data.get("bva_mode") in MODES else "3-value",
        strategy=data.get("strategy") if data.get("strategy") in STRATEGIES else "vary_one",
        fields=[_build(FieldSpec, d) for d in data.get("fields", [])],
        conditions=[_build(Condition, d) for d in data.get("conditions", [])],
        actions=[str(a) for a in data.get("actions", [])],
        action_map={str(k): [str(a) for a in v] for k, v in data.get("action_map", {}).items()},
        constraints=[{str(k): str(v) for k, v in c.items()} for c in data.get("constraints", [])],
    )
    return p
