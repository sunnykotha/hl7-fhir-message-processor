import pytest

from hl7_fhir_processor.hl7_message import HL7Message
from hl7_fhir_processor.idempotency import IdempotencyTracker


MESSAGE = (
    "MSH|^~\\&|HOSPITAL|ADT|FHIR|EHR|202610271500||ADT^A01|MSG001|P|2.5\r"
    "PID|1||PAT001^^^HOSPITAL^MR||DOE^JANE\r"
    "PV1|1|I"
)


def parse_message(text=MESSAGE):
    return HL7Message.parse(text)


def test_first_message_id_is_not_duplicate():
    tracker = IdempotencyTracker()

    assert tracker.is_duplicate(parse_message()) is False


def test_repeated_message_id_is_duplicate():
    tracker = IdempotencyTracker()
    message = parse_message()

    assert tracker.is_duplicate(message) is False
    assert tracker.is_duplicate(message) is True


def test_different_message_ids_are_not_duplicates():
    tracker = IdempotencyTracker()
    first = parse_message()
    second = parse_message(MESSAGE.replace("|MSG001|", "|MSG002|"))

    assert tracker.is_duplicate(first) is False
    assert tracker.is_duplicate(second) is False


def test_duplicate_detection_is_independent_of_other_fields():
    tracker = IdempotencyTracker()
    first = parse_message()
    changed_patient = parse_message(
        MESSAGE.replace("PAT001", "PAT999")
    )

    assert tracker.is_duplicate(first) is False
    assert tracker.is_duplicate(changed_patient) is True


def test_rejects_missing_control_id():
    tracker = IdempotencyTracker()
    message = parse_message(MESSAGE.replace("|MSG001|", "||"))

    with pytest.raises(ValueError, match="MSH-10"):
        tracker.is_duplicate(message)


def test_tracker_instances_have_independent_state():
    first_tracker = IdempotencyTracker()
    second_tracker = IdempotencyTracker()
    message = parse_message()

    assert first_tracker.is_duplicate(message) is False
    assert first_tracker.is_duplicate(message) is True
    assert second_tracker.is_duplicate(message) is False
