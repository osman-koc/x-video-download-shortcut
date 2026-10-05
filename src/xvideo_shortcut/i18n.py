"""Translation tables bundled with the shortcut.

Shortcuts has no built-in localization, so every language is embedded in the
shortcut as JSON and the right one is picked at runtime (see flow.py).
English is the fallback and the reference for required keys.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

TRANSLATIONS_DIR = Path(__file__).parent / "translations"
DEFAULT_LANGUAGE = "en"
MARKER_KEY = "_era_markers"


def load_translations() -> Dict[str, Dict[str, object]]:
    tables: Dict[str, Dict[str, object]] = {}
    for path in sorted(TRANSLATIONS_DIR.glob("*.json")):
        tables[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    if DEFAULT_LANGUAGE not in tables:
        raise RuntimeError("The English translation table is required.")
    return tables


def string_keys(tables: Dict[str, Dict[str, object]]) -> List[str]:
    return [k for k in tables[DEFAULT_LANGUAGE] if k != MARKER_KEY]


def era_markers(table: Dict[str, object]) -> List[str]:
    return list(table.get(MARKER_KEY, []))  # type: ignore[arg-type]
