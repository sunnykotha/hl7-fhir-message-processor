from dataclasses import dataclass
import time
from collections.abc import Callable

from hl7_fhir_processor.retry import RetryPolicy

from hl7_fhir_processor.ack import create_ack
from hl7_fhir_processor.dead_letter import DeadLetterQueue
from hl7_fhir_processor.hl7_message import HL7Message, HL7ParseError
from hl7_fhir_processor.idempotency import IdempotencyTracker
from hl7_fhir_processor.mapping import (
    FHIRMappingError,
    map_adt_a01,
    map_adt_a08,
    map_adt_a40,
    map_oru_r01,
)
from hl7_fhir_processor.validation import validate_message


@dataclass(frozen=True)
class ProcessingResult:
    accepted: bool
    ack: str | None
    resources: tuple[dict, ...]
    error: str | None = None
    duplicate: bool = False
    dead_lettered: bool = False




class TransientDownstreamError(RuntimeError):
    """Indicates a downstream failure that may succeed on retry."""

class HL7Processor:
    """Process supported HL7 messages into FHIR resources."""

    def __init__(
        self,
        idempotency_tracker: IdempotencyTracker | None = None,
        dead_letter_queue: DeadLetterQueue | None = None,
    ) -> None:
        self.idempotency_tracker = (
            idempotency_tracker or IdempotencyTracker()
        )
        self.dead_letter_queue = dead_letter_queue or DeadLetterQueue()

    def process(self, raw_message: str) -> ProcessingResult:
        try:
            message = HL7Message.parse(raw_message)
        except (HL7ParseError, TypeError, ValueError) as exc:
            return ProcessingResult(
                accepted=False,
                ack=None,
                resources=(),
                error=str(exc),
            )

        issues = validate_message(message)
        if issues:
            reason = "; ".join(issue.message for issue in issues)
            return self._reject(message, raw_message, reason)

        try:
            message_type = message.first_segment("MSH").field(9)
            message_type = message_type.strip()

            if message_type.startswith("ADT^A01"):
                resources = map_adt_a01(message)
            elif message_type.startswith("ADT^A08"):
                resources = map_adt_a08(message)
            elif message_type.startswith("ADT^A40"):
                resources = map_adt_a40(message)
            elif message_type.startswith("ORU^R01"):
                resources = map_oru_r01(message)
            else:
                return self._reject(
                    message,
                    raw_message,
                    f"Unsupported message type: {message_type}",
                )
        except (FHIRMappingError, ValueError, TypeError) as exc:
            return self._reject(message, raw_message, str(exc))

        try:
            duplicate = self.idempotency_tracker.is_duplicate(message)
        except ValueError as exc:
            return self._reject(message, raw_message, str(exc))

        if duplicate:
            return ProcessingResult(
                accepted=True,
                ack=create_ack(message, accepted=True),
                resources=(),
                duplicate=True,
            )

        return ProcessingResult(
            accepted=True,
            ack=create_ack(message, accepted=True),
            resources=tuple(resources),
        )

    def process_with_downstream(
        self,
        raw_message: str,
        downstream: Callable[[tuple[dict, ...]], object],
        retry_policy: RetryPolicy | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> ProcessingResult:
        """Process a message and deliver its resources with bounded retries."""
        result = self.process(raw_message)

        if not result.accepted or result.duplicate:
            return result

        policy = retry_policy or RetryPolicy()
        wait = sleep_fn or time.sleep
        message = HL7Message.parse(raw_message)

        for attempts_made in range(1, policy.max_attempts + 1):
            try:
                downstream(result.resources)
                self.idempotency_tracker.mark_processed(message)
                return result
            except TransientDownstreamError as exc:
                reason = str(exc) or "Transient downstream failure"

                if policy.can_retry(attempts_made):
                    wait(policy.delay_before_retry(attempts_made))
                    continue

                return self._downstream_failure(
                    message, raw_message, reason
                )
            except Exception as exc:
                reason = str(exc) or type(exc).__name__
                return self._downstream_failure(
                    message, raw_message, reason
                )

        raise RuntimeError("Retry loop ended unexpectedly")

    def _downstream_failure(
        self,
        message: HL7Message,
        raw_message: str,
        reason: str,
    ) -> ProcessingResult:
        self.idempotency_tracker.unmark_processed(message)
        self.dead_letter_queue.add(raw_message, reason)

        return ProcessingResult(
            accepted=False,
            ack=create_ack(
                message,
                accepted=False,
                error_message=reason,
            ),
            resources=(),
            error=reason,
            dead_lettered=True,
        )
    def _reject(
        self,
        message: HL7Message,
        raw_message: str,
        reason: str,
    ) -> ProcessingResult:
        dead_lettered = False
        try:
            self.dead_letter_queue.add(raw_message, reason)
            dead_lettered = True
        except (ValueError, TypeError):
            pass

        msh = message.first_segment("MSH")
        control_id = msh.field(10).strip() if msh is not None else ""

        ack = None
        if control_id:
            ack = create_ack(
                message,
                accepted=False,
                error_message=reason,
            )

        return ProcessingResult(
            accepted=False,
            ack=ack,
            resources=(),
            error=reason,
            dead_lettered=dead_lettered,
        )
