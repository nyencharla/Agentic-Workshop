"""The triage decision schema (Epic 1, story 1).

Every decision the agent (Epic 2) produces, and every decision the eval (Epic 3)
checks, must match `TriageDecision`. Values come straight from `TRIAGE_POLICY.md`.
"""

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

Category = Literal["billing", "bug", "access", "performance", "how-to"]
Priority = Literal["P1", "P2", "P3", "P4"]
Route = Literal["billing-team", "bug-team", "access-team", "performance-team", "how-to-team"]

# A sentence break: end punctuation, whitespace, then a new sentence starting
# with a capital letter. Requiring the capital avoids flagging abbreviations
# ("e.g. this...") or a lowercase continuation ("rule 3. it applies...") as
# a second sentence.
_MULTIPLE_SENTENCES = re.compile(r"[.!?]\s+[A-Z]")


class TriageDecision(BaseModel):
    """Where a ticket goes, how urgent it is, and why."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: Category = Field(description="The ticket's category, per the triage policy.")
    priority: Priority = Field(description="P1 is the most urgent, P4 the least.")
    route: Route = Field(description="The team that owns this category.")
    rationale: str = Field(description="One sentence naming the policy rule that was applied.")

    @field_validator("rationale")
    @classmethod
    def _single_sentence(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("rationale must not be empty")
        if _MULTIPLE_SENTENCES.search(text):
            raise ValueError("rationale must be a single sentence")
        return text


class TriageValidationError(ValueError):
    """A decision does not match the schema. The message names every offending field."""


def validate_decision(payload: str | bytes | dict) -> TriageDecision:
    """Parse and validate a decision from a dict or JSON text.

    Raises TriageValidationError, naming each offending field, if the payload
    is not valid JSON, is not an object, or fails the schema.
    """
    if isinstance(payload, (str, bytes)):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise TriageValidationError(f"Decision is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise TriageValidationError(f"Decision must be a JSON object, got {type(payload).__name__}")
    try:
        return TriageDecision.model_validate(payload)
    except ValidationError as error:
        problems = "; ".join(f"{'.'.join(str(loc) for loc in e['loc']) or 'decision'}: {e['msg']}" for e in error.errors())
        raise TriageValidationError(f"Invalid triage decision: {problems}") from error
