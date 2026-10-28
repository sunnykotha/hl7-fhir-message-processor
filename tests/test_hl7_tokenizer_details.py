import pytest

from hl7_fhir_processor.hl7_message import HL7Message, HL7ParseError


def test_extracts_components_and_preserves_empty_components():
    message = HL7Message.parse(
        "MSH|^~\\&|SENDER|RECEIVER\r"
        "PID|1||PAT123||DOE^JANE^^"
    )
    pid = message.first_segment("PID")

    assert pid.components(5) == ("DOE", "JANE", "", "")


def test_extracts_repetitions():
    message = HL7Message.parse(
        "MSH|^~\\&|SENDER|RECEIVER\r"
        "OBX|1|ST|TEST||FIRST~SECOND~THIRD"
    )
    obx = message.first_segment("OBX")

    assert obx.repetitions(5) == ("FIRST", "SECOND", "THIRD")
    assert obx.components(5, repetition_number=2) == ("SECOND",)


def test_extracts_subcomponents():
    message = HL7Message.parse(
        "MSH|^~\\&|SENDER|RECEIVER\r"
        "PID|1||PAT123^^^HOSPITAL&REGION^MR"
    )
    pid = message.first_segment("PID")

    assert pid.subcomponents(3, component_number=4) == (
        "HOSPITAL", "REGION"
    )


def test_decodes_hl7_delimiter_escapes():
    message = HL7Message.parse(
        "MSH|^~\\&|SENDER|RECEIVER\r"
        r"PID|1||A\F\B\S\C\R\D\T\\E\Z"
    )
    pid = message.first_segment("PID")

    assert pid.decoded_field(3) == "A|B^C~D&\\Z"


def test_decodes_formatting_line_break():
    message = HL7Message.parse(
        "MSH|^~\\&|SENDER|RECEIVER\r"
        r"OBX|1|TX|NOTE||FIRST\.br\SECOND"
    )
    obx = message.first_segment("OBX")

    assert obx.decoded_field(5) == "FIRST\nSECOND"


def test_preserves_unsupported_escape_sequences():
    message = HL7Message.parse(
        "MSH|^~\\&|SENDER|RECEIVER\r"
        r"OBX|1|ST|TEST||A\X0D\B"
    )
    obx = message.first_segment("OBX")

    assert obx.decoded_field(5) == r"A\X0D\B"


def test_rejects_out_of_range_component_or_repetition():
    message = HL7Message.parse(
        "MSH|^~\\&|SENDER|RECEIVER\r"
        "PID|1||PAT123"
    )
    pid = message.first_segment("PID")

    with pytest.raises(ValueError):
        pid.components(3, repetition_number=2)

    with pytest.raises(ValueError):
        pid.subcomponents(3, component_number=2)


def test_rejects_duplicate_encoding_characters():
    with pytest.raises(HL7ParseError):
        HL7Message.parse("MSH|^^^^|SENDER|RECEIVER")
