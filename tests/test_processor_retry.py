from hl7_fhir_processor.processor import (
    HL7Processor,
    TransientDownstreamError,
)
from hl7_fhir_processor.retry import RetryPolicy


ADT_MESSAGE = (
    "MSH|^~\\&|SENDER|FAC|RECEIVER|FAC|20250101120000||"
    "ADT^A01|RETRY-CTRL-1|P|2.5\r"
    "PID|1||12345^^^HOSP^MR||Doe^Jane||19800101|F\r"
    "PV1|1|I\r"
)


def test_downstream_success_does_not_retry():
    processor = HL7Processor()
    calls = []
    delays = []

    def downstream(resources):
        calls.append(resources)

    result = processor.process_with_downstream(
        ADT_MESSAGE, downstream, sleep_fn=delays.append
    )

    assert result.accepted is True
    assert len(calls) == 1
    assert delays == []
    assert len(processor.dead_letter_queue) == 0


def test_transient_failure_retries_then_succeeds():
    processor = HL7Processor()
    calls = []
    delays = []

    def downstream(resources):
        calls.append(resources)
        if len(calls) < 3:
            raise TransientDownstreamError("HTTP 503")

    result = processor.process_with_downstream(
        ADT_MESSAGE, downstream, sleep_fn=delays.append
    )

    assert result.accepted is True
    assert len(calls) == 3
    assert delays == [2.0, 4.0]
    assert len(processor.dead_letter_queue) == 0


def test_exhausted_transient_failures_go_to_dead_letter_queue():
    processor = HL7Processor()
    calls = []
    delays = []

    def downstream(resources):
        calls.append(resources)
        raise TransientDownstreamError("HTTP 503")

    result = processor.process_with_downstream(
        ADT_MESSAGE,
        downstream,
        retry_policy=RetryPolicy(),
        sleep_fn=delays.append,
    )

    assert result.accepted is False
    assert len(calls) == 4
    assert delays == [2.0, 4.0, 8.0]
    assert result.dead_lettered is True
    assert result.ack is not None
    assert len(processor.dead_letter_queue) == 1
    assert processor.dead_letter_queue.all_records()[0].reason == "HTTP 503"


def test_non_transient_downstream_failure_is_not_retried():
    processor = HL7Processor()
    calls = []
    delays = []

    def downstream(resources):
        calls.append(resources)
        raise ValueError("Invalid downstream payload")

    result = processor.process_with_downstream(
        ADT_MESSAGE, downstream, sleep_fn=delays.append
    )

    assert result.accepted is False
    assert len(calls) == 1
    assert delays == []
    assert result.dead_lettered is True
    assert len(processor.dead_letter_queue) == 1


def test_rejected_message_is_not_sent_downstream():
    processor = HL7Processor()
    calls = []

    result = processor.process_with_downstream(
        "not an HL7 message",
        lambda resources: calls.append(resources),
        sleep_fn=lambda seconds: None,
    )

    assert result.accepted is False
    assert calls == []


def test_message_can_be_retried_after_downstream_failure():
    processor = HL7Processor()

    failed = processor.process_with_downstream(
        ADT_MESSAGE,
        lambda resources: (_ for _ in ()).throw(
            ValueError('Temporary test failure')
        ),
        sleep_fn=lambda seconds: None,
    )

    assert failed.accepted is False
    assert failed.dead_lettered is True

    delivered = []
    retried = processor.process_with_downstream(
        ADT_MESSAGE,
        lambda resources: delivered.append(resources),
        sleep_fn=lambda seconds: None,
    )

    assert retried.accepted is True
    assert retried.duplicate is False
    assert len(delivered) == 1
