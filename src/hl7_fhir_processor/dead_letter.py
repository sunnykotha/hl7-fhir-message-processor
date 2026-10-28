from dataclasses import dataclass
from datetime import datetime, timezone

from hl7_fhir_processor.hl7_message import HL7Message


@dataclass(frozen=True)
class DeadLetterRecord:
    """A permanently failed HL7 message retained for investigation."""

    control_id: str
    raw_message: str
    reason: str
    recorded_at: datetime


class DeadLetterQueue:
    """Store and retrieve messages that cannot be processed permanently."""

    def __init__(self) -> None:
        self._records: list[DeadLetterRecord] = []

    def add(self, raw_message: str, reason: str) -> DeadLetterRecord:
        """Validate and record the original message and its failure reason."""
        if not isinstance(raw_message, str) or not raw_message.strip():
            raise ValueError("Original HL7 message is required")

        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Dead-letter reason is required")

        message = HL7Message.parse(raw_message)
        msh = message.first_segment("MSH")
        if msh is None:
            raise ValueError("MSH segment is required")

        control_id = msh.field(10).strip()
        if not control_id:
            raise ValueError("MSH-10 message control ID is required")

        record = DeadLetterRecord(
            control_id=control_id,
            raw_message=raw_message,
            reason=reason.strip(),
            recorded_at=datetime.now(timezone.utc),
        )
        self._records.append(record)
        return record

    def all_records(self) -> tuple[DeadLetterRecord, ...]:
        """Return all recorded failures in insertion order."""
        return tuple(self._records)

    def find_by_control_id(self, control_id: str) -> tuple[DeadLetterRecord, ...]:
        """Return all dead-letter records matching a message control ID."""
        return tuple(
            record
            for record in self._records
            if record.control_id == control_id
        )

    def __len__(self) -> int:
        return len(self._records)
