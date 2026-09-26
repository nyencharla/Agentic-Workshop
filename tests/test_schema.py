import json

import pytest

from triage.schema import TriageDecision, TriageValidationError, validate_decision

VALID = {
    "category": "billing",
    "priority": "P2",
    "route": "billing-team",
    "rationale": "A double charge is money at stake for one customer.",
}


def test_accepts_a_valid_decision_as_dict_or_json():
    assert validate_decision(VALID) == TriageDecision(**VALID)
    assert validate_decision(json.dumps(VALID)).priority == "P2"


@pytest.mark.parametrize(
    "change, field",
    [
        ({"category": "sales"}, "category"),
        ({"priority": "P5"}, "priority"),
        ({"route": "finance-team"}, "route"),
        ({"rationale": "   "}, "rationale"),
        ({"rationale": "First sentence. Second sentence."}, "rationale"),
        ({"extra": "field"}, "extra"),
    ],
)
def test_rejects_bad_fields_naming_the_field(change, field):
    with pytest.raises(TriageValidationError, match=field):
        validate_decision({**VALID, **change})


@pytest.mark.parametrize("field", ["category", "priority", "route", "rationale"])
def test_rejects_a_missing_field(field):
    payload = {key: value for key, value in VALID.items() if key != field}
    with pytest.raises(TriageValidationError, match=field):
        validate_decision(payload)


@pytest.mark.parametrize("payload", ["not json", b"\x80\x81", "[1, 2]", "42"])
def test_rejects_non_objects(payload):
    with pytest.raises(TriageValidationError):
        validate_decision(payload)


@pytest.mark.parametrize(
    "change, field",
    [
        ({"category": "Billing"}, "category"),
        ({"priority": " P2"}, "priority"),
        ({"route": "Billing-Team"}, "route"),
    ],
)
def test_rejects_near_miss_casing_and_whitespace(change, field):
    """Guards against a model's raw output being close but not exact."""
    with pytest.raises(TriageValidationError, match=field):
        validate_decision({**VALID, **change})


@pytest.mark.parametrize(
    "rationale",
    [
        "e.g. this is a refund request that qualifies.",
        "Escalate per rule 3, since it is Enterprise and P1.",
    ],
)
def test_accepts_a_single_sentence_containing_a_period_and_lowercase_continuation(rationale):
    """A '.' followed by a lowercase word (an abbreviation, an inline rule number)
    is not a second sentence and must not be rejected."""
    assert validate_decision({**VALID, "rationale": rationale}).rationale == rationale


def test_route_and_category_are_validated_independently():
    """Story 1 does not enforce TRIAGE_POLICY.md's category-to-route pairing;
    each field is checked only against its own allowed set. A mismatched pair
    is accepted here — Epic 2's agent, not this schema, is responsible for
    choosing a route that matches its category."""
    mismatched = {**VALID, "category": "bug", "route": "billing-team"}
    assert validate_decision(mismatched).route == "billing-team"


def test_decisions_are_immutable():
    decision = validate_decision(VALID)
    with pytest.raises(Exception, match="frozen"):
        decision.priority = "P1"
