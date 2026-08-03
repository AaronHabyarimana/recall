"""Gemeinsames Parsen von Modellantworten, die eine JSON-Liste enthalten sollen."""

import json
import re

# Gemini verpackt JSON trotz klarer Anweisung gern in ```json ... ```
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$")


def parse_json_list(response: str) -> list:
    """Parst die Modellantwort zu einer Liste. Wirft ValueError bei unbrauchbarem JSON."""
    stripped = _CODE_FENCE_RE.sub("", response.strip())
    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError as e:
        raise ValueError(f"Antwort ist kein JSON: {response[:120]!r}") from e
    if not isinstance(raw, list):
        raise ValueError(f"Antwort ist keine Liste: {response[:120]!r}")
    return raw
