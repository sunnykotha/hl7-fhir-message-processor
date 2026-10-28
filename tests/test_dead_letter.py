from datetime import timezone

import pytest

from hl7_fhir_processor.dead_letter import DeadLetterQueue, DeadLetterRecord


MESSAGE = (
    "MSH|^~\\&|HOSPITAL|ADT|FHIR|EHR|202610271500||ADT^A01|MSG-DLQ-1|P|2.5\r"
    "PID|1||PAT001^^^HOSPITAL^MR||DOE^JANE\r"
    "PV1|1|I"
)


def test_records_permanent_failure():
    queue = DeadLetterQueue()

    record = queue.add(MESSAGE, "Permanent validation failure")

    assert isinstance(record, DeadLetterRecord)
    assert len(queue) == 1
    assert record.control_id == "MSG-DLQ-1"
    assert record.reason == "Permanent validation failure"


def test_preserves_original_message_exactly():
    queue = DeadLetterQueue()
    original = MESSAGE.replace("\r", "\r\n")

    record = queue.add(original, "Rejected message")

    assert record.raw_message == original


def test_record_timestamp_is_utc():
    record = DeadLetterQueue().add(MESSAGE, "Permanent failure")

    assert record.recorded_at.tzinfo is not None
    assert record.recorded_at.utcoffset().total_seconds() == 0
    assert record.recorded_at.tzinfo == timezone.utc


def test_returns_records_in_insertion_order():
    queue = DeadLetterQueue()
    queue.add(MESSAGE, "First failure")
    queue.add(MESSAGE.replace("MSG-DLQ-1", "MSG-DLQ-2"), "Second failure")

    records = queue.all_records()

    assert len(records) == 2
    assert [record.control_id for record in records] == [
        "MSG-DLQ-1", "MSG-DLQ-2"
    ]


def test_finds_records_by_control_id():
    queue = DeadLetterQueue()
    queue.add(MESSAGE, "First failure")
    queue.add(MESSAGE.replace("MSG-DLQ-1", "MSG-DLQ-2"), "Second failure")

    matches = queue.find_by_control_id("MSG-DLQ-2")

    assert len(matches) == 1
    assert matches[0].reason == "Second failure"
    assert queue.find_by_control_id("UNKNOWN") == ()


def test_rejects_empty_message_or_reason():
    queue = DeadLetterQueue()

    with pytest.raises(ValueError, match="message"):
        queue.add("", "Failure")

    with pytest.raises(ValueError, match="reason"):
        queue.add(MESSAGE, "  ")


def test_rejects_message_without_control_id():
    queue = DeadLetterQueue()
    message = MESSAGE.replace("|MSG-DLQ-1|", "||")

    with pytest.raises(ValueError, match="MSH-10"):
        queue.add(message, "Missing control ID")
