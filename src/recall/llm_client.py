"""Dünner Wrapper um die Gemini-API.

Modellname kommt aus config.toml, der API-Key aus .env (GEMINI_API_KEY).
"""

import tomllib
from functools import cache
from pathlib import Path

from dotenv import load_dotenv
from google import genai

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.toml"


@cache
def _client() -> genai.Client:
    load_dotenv()
    return genai.Client()  # liest GEMINI_API_KEY aus der Umgebung


@cache
def _model_name() -> str:
    with CONFIG_PATH.open("rb") as f:
        return tomllib.load(f)["llm"]["model"]


def complete(prompt: str) -> str:
    response = _client().models.generate_content(model=_model_name(), contents=prompt)
    return response.text or ""


if __name__ == "__main__":
    print(complete("Antworte mit genau einem Wort: Was ist die Hauptstadt von Deutschland?"))
