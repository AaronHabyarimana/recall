"""Dünner Wrapper um die Gemini-API.

Modellname kommt aus config.toml, der API-Key aus .env (GEMINI_API_KEY).
"""

import time
import tomllib
from functools import cache
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.toml"


@cache
def _client() -> genai.Client:
    load_dotenv()
    return genai.Client()  # liest GEMINI_API_KEY aus der Umgebung


@cache
def _model_name() -> str:
    with CONFIG_PATH.open("rb") as f:
        return tomllib.load(f)["llm"]["model"]


# Free-Tier-Limit: 5 Anfragen/Minute -> bei 429 warten und erneut versuchen
_RETRY_DELAY_SECONDS = 15
_MAX_ATTEMPTS = 5


def complete(prompt: str) -> str:
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = _client().models.generate_content(model=_model_name(), contents=prompt)
        except errors.ClientError as e:
            if e.code != 429 or attempt == _MAX_ATTEMPTS:
                raise
            time.sleep(_RETRY_DELAY_SECONDS)
            continue
        return response.text or ""
    raise RuntimeError("unreachable")


if __name__ == "__main__":
    print(complete("Antworte mit genau einem Wort: Was ist die Hauptstadt von Deutschland?"))
