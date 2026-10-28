from hl7_fhir_processor.hl7_message import HL7Message


class IdempotencyTracker:
    def __init__(self) -> None:
        self._processed_ids: set[str] = set()

    def control_id(self, message: HL7Message) -> str:
        msh = message.first_segment("MSH")
        if msh is None:
            raise ValueError("MSH segment is required for idempotency")

        control_id = msh.field(10).strip()
        if not control_id:
            raise ValueError("MSH-10 message control ID is required")
        return control_id

    def is_duplicate(self, message: HL7Message) -> bool:
        """Check and record an ID, preserving the existing tracker contract."""
        control_id = self.control_id(message)
        if control_id in self._processed_ids:
            return True
        self._processed_ids.add(control_id)
        return False

    def has_processed(self, message: HL7Message) -> bool:
        """Check an ID without recording it."""
        return self.control_id(message) in self._processed_ids

    def mark_processed(self, message: HL7Message) -> None:
        """Record an ID after successful downstream delivery."""
        self._processed_ids.add(self.control_id(message))

    def unmark_processed(self, message: HL7Message) -> None:
        """Release an ID after a downstream failure."""
        self._processed_ids.discard(self.control_id(message))
