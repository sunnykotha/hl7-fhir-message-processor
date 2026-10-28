import pytest

from hl7_fhir_processor.hl7_message import HL7Message, HL7ParseError


SAMPLE = (
    "MSH|^~\\&|HOSPITAL|LAB|FHIR|EHR|202610271500||ADT^A01|MSG001|P|2.5\r"
    "PID|1||PAT001^^^HOSPITAL^MR||DOE^JANE\r"
    "PV1|1|I\r"
)


def test_parses_segments_in_message_order():
    message = HL7Message.parse(SAMPLE)

    assert [segment.name for segment in message.segments] == [
        "MSH", "PID", "PV1"
    ]


def test_extracts_msh_fields_using_hl7_field_numbers():
    message = HL7Message.parse(SAMPLE)
    msh = message.first_segment("MSH")

    assert msh is not None
    assert msh.field(1) == "|"
    assert msh.field(2) == "^~\\&"
    assert msh.field(3) == "HOSPITAL"
    assert msh.field(9) == "ADT^A01"
    assert msh.field(10) == "MSG001"


def test_extracts_regular_segment_fields_and_preserves_empty_fields():
    message = HL7Message.parse(SAMPLE)
    pid = message.first_segment("PID")

    assert pid is not None
    assert pid.field(1) == "1"
    assert pid.field(2) == ""
    assert pid.field(3) == "PAT001^^^HOSPITAL^MR"
    assert pid.field(5) == "DOE^JANE"


def test_supports_custom_field_separator():
    message = HL7Message.parse(
        "MSH*^~\\&*SENDER*RECEIVER**202610271500**ADT^A01*CTRL1*P*2.5\n"
        "PID*1**PAT123"
    )

    assert message.field_separator == "*"
    assert message.first_segment("MSH").field(3) == "SENDER"
    assert message.first_segment("PID").field(3) == "PAT123"


def test_supports_lf_and_crlf_line_endings():
    lf_message = HL7Message.parse(SAMPLE.replace("\r", "\n"))
    crlf_message = HL7Message.parse(SAMPLE.replace("\r", "\r\n"))

    assert len(lf_message.segments) == 3
    assert len(crlf_message.segments) == 3


def test_returns_all_segments_of_a_given_type():
    message = HL7Message.parse(SAMPLE + "OBX|1|NM|2823-3||6.8|mmol/L\n")

    assert len(message.segments_named("OBX")) == 1
    assert message.segments_named("OBR") == ()


def test_rejects_empty_messages():
    with pytest.raises(HL7ParseError):
        HL7Message.parse("")


def test_rejects_messages_without_msh_first():
    with pytest.raises(HL7ParseError):
        HL7Message.parse("PID|1||PAT001\nMSH|^~\\&")


def test_rejects_invalid_encoding_characters():
    with pytest.raises(HL7ParseError):
        HL7Message.parse("MSH|^~|SENDER|RECEIVER")


def test_preserves_custom_z_segments_in_message_order():
    message = HL7Message.parse(
        "MSH|^~\\&|SENDER|RECEIVER\r"
        "ZXY|custom|value\r"
        "PID|1||PATIENT-123\r"
    )

    assert [segment.name for segment in message.segments] == [
        "MSH",
        "ZXY",
        "PID",
    ]
    custom_segment = message.first_segment("ZXY")
    assert custom_segment is not None
    assert custom_segment.field(1) == "custom"
    assert custom_segment.field(2) == "value"

def test_parses_utf8_encoded_message_bytes():
    message_text = SAMPLE.replace("DOE^JANE", "GARC?A^JANE")
    message = HL7Message.parse(message_text.encode("utf-8"))

    assert message.first_segment("PID").field(5) == "GARC?A^JANE"


def test_rejects_bytes_that_cannot_be_decoded():
    with pytest.raises(HL7ParseError, match="cannot be decoded"):
        HL7Message.parse(bytes([255]), encoding="utf-8")



def test_rejects_unknown_character_encoding():
    with pytest.raises(HL7ParseError, match="cannot be decoded"):
        HL7Message.parse(SAMPLE.encode("utf-8"), encoding="not-a-real-encoding")


def test_parses_message_bytes_using_explicit_windows_1252_encoding():
    message_text = (
        "MSH|^~\\&|HOSPITAL|LAB|FHIR|EHR|202610271500||ADT^A01|MSG002|P|2.5\r"
        "PID|1||PAT002^^^HOSPITAL^MR||GARCÍA^JANE\r"
    )
    encoded_message = message_text.encode("cp1252")

    message = HL7Message.parse(encoded_message, encoding="cp1252")

    pid = message.first_segment("PID")
    assert pid is not None
    assert pid.field(5) == "GARCÍA^JANE"
