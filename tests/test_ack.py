import pytest

from hl7_fhir_processor.ack import create_ack
from hl7_fhir_processor.hl7_message import HL7Message


MESSAGE = (
    "MSH|^~\\&|HOSPITAL|ADT|FHIR|EHR|202610271500||ADT^A01|MSG001|P|2.5\r"
    "PID|1||PAT001^^^HOSPITAL^MR||DOE^JANE\r"
    "PV1|1|I"
)


def test_creates_positive_ack():
    original = HL7Message.parse(MESSAGE)
    ack = create_ack(original, accepted=True)

    assert ack.startswith("MSH|^~\\&|FHIR|PROCESSOR|HOSPITAL|ADT|")
    assert "\rMSA|AA|MSG001\r" in ack


def test_creates_negative_ack():
    original = HL7Message.parse(MESSAGE)
    ack = create_ack(
        original,
        accepted=False,
        error_message="Missing required field",
    )

    assert "\rMSA|AE|MSG001\r" in ack
    assert "\rERR|" in ack
    assert "Missing required field" in ack


def test_ack_uses_original_control_id():
    original = HL7Message.parse(MESSAGE)
    ack = create_ack(original, accepted=True)

    parsed_ack = HL7Message.parse(ack)
    msa = parsed_ack.first_segment("MSA")

    assert msa is not None
    assert msa.field(1) == "AA"
    assert msa.field(2) == "MSG001"


def test_ack_uses_original_message_version():
    original = HL7Message.parse(MESSAGE)
    ack = create_ack(original, accepted=True)

    parsed_ack = HL7Message.parse(ack)

    assert parsed_ack.first_segment("MSH").field(12) == "2.5"


def test_rejects_missing_control_id():
    original = HL7Message.parse(MESSAGE.replace("|MSG001|", "||"))

    with pytest.raises(ValueError, match="MSH-10"):
        create_ack(original, accepted=True)


def test_rejects_message_without_msh():
    # Construct a valid parsed message first, then verify the normal guard
    # through a minimal object-shaped test double.
    class NoMshMessage:
        def first_segment(self, name):
            return None

    with pytest.raises(ValueError, match="MSH"):
        create_ack(NoMshMessage(), accepted=True)
