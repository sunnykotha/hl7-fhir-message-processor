from hl7_fhir_processor.processor import (
    HL7Processor,
    TransientDownstreamError,
)
from hl7_fhir_processor.retry import RetryPolicy


MESSAGE = (
    "MSH|^~\\&|SENDER|FAC|RECEIVER|FAC|20250101120000||"
    "ADT^A01|IDEMPOTENCY-RETRY-1|P|2.5\r"
    "PID|1||12345^^^HOSP^MR||Doe^Jane||19800101|F\r"
    "PV1|1|I\r"
)


def test_failed_downstream_message_can_be_processed_again():
    processor = HL7Processor()

    def failing_downstream(resources):
        raise TransientDownstreamError("HTTP 503")

    failed = processor.process_with_downstream(
        MESSAGE,
        failing_downstream,
        retry_policy=RetryPolicy(max_attempts=1),
        sleep_fn=lambda seconds: None,
    )

    assert failed.accepted is False

    delivered = []

    retry = processor.process_with_downstream(
        MESSAGE,
        lambda resources: delivered.append(resources),
        sleep_fn=lambda seconds: None,
    )

    assert retry.accepted is True
    assert retry.duplicate is False
    assert len(delivered) == 1
