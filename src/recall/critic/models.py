from pydantic import BaseModel


class Verdict(BaseModel):
    """Urteil des Critics über eine Karte. Der Critic löscht nicht, er begründet."""

    card_id: str
    keep: bool
    issue: str | None = None  # z. B. "trivia", "kontextabhaengig", "unklar", "duplikat"
    reason: str
