from hl7_fhir_processor.hl7_message import HL7Message
from hl7_fhir_processor.validation import validate_message


VALID_ADT = (
    "MSH|^~\\&|HOSPITAL|ADT|FHIR|EHR|202610271500||ADT^A01|ADT001|P|2.5\r"
    "PID|1||PAT001^^^HOSPITAL^MR||DOE^JANE\r"
    "PV1|1|I\r"
)

VALID_ORU = (
    "MSH|^~\\&|HOSPITAL|LAB|FHIR|EHR|202610271500||ORU^R01|ORU001|P|2.5\r"
    "PID|1||PAT001^^^HOSPITAL^MR||DOE^JANE\r"
    "OBR|1|ORDER001|FILL001|2823-3^Potassium^LN\r"
    "OBX|1|NM|2823-3^Potassium^LN||6.8|mmol/L"
)


def codes(text):
    return {
        issue.code
        for issue in validate_message(HL7Message.parse(text))
    }


def test_accepts_valid_adt_a01():
    assert codes(VALID_ADT) == set()


def test_accepts_valid_oru_r01():
    assert codes(VALID_ORU) == set()


def test_rejects_missing_control_id():
    message = VALID_ADT.replace("|ADT001|", "||")

    assert "CONTROL_ID_REQUIRED" in codes(message)


def test_rejects_missing_patient_identifier():
    message = VALID_ADT.replace("PID|1||PAT001", "PID|1||")

    assert "PATIENT_ID_REQUIRED" in codes(message)


def test_rejects_missing_pv1_for_adt():
    message = VALID_ADT.replace("PV1|1|I\r", "")

    assert "PV1_REQUIRED" in codes(message)


def test_rejects_missing_patient_class_for_adt():
    message = VALID_ADT.replace("PV1|1|I", "PV1|1|")

    assert "PATIENT_CLASS_REQUIRED" in codes(message)


def test_rejects_missing_obr_in_oru():
    message = VALID_ORU.replace(
        "OBR|1|ORDER001|FILL001|2823-3^Potassium^LN\r", ""
    )

    assert "OBR_REQUIRED" in codes(message)


def test_rejects_missing_observation_code():
    message = VALID_ORU.replace(
        "OBX|1|NM|2823-3^Potassium^LN||6.8|mmol/L",
        "OBX|1|NM|||6.8|mmol/L",
    )

    assert "OBSERVATION_CODE_REQUIRED" in codes(message)


def test_rejects_observation_with_missing_code_system():
    message = VALID_ORU.replace(
        "2823-3^Potassium^LN",
        "2823-3^Potassium",
    )

    assert "OBSERVATION_CODE_SYSTEM_REQUIRED" in codes(message)

def test_rejects_missing_observation_value():
    message = VALID_ORU.replace(
        "OBX|1|NM|2823-3^Potassium^LN||6.8|mmol/L",
        "OBX|1|NM|2823-3^Potassium^LN|||mmol/L",
    )

    assert "OBSERVATION_VALUE_REQUIRED" in codes(message)


def test_rejects_unsupported_message_type():
    message = VALID_ADT.replace("ADT^A01", "ADT^A99")

    assert "UNSUPPORTED_MESSAGE_TYPE" in codes(message)


def test_reports_missing_message_type():
    message = VALID_ADT.replace("ADT^A01", "")

    assert "MESSAGE_TYPE_REQUIRED" in codes(message)

def test_rejects_missing_obx_in_oru():
    message = VALID_ORU.replace(
        "OBX|1|NM|2823-3^Potassium^LN||6.8|mmol/L", ""
    )
    assert "OBX_REQUIRED" in codes(message)


def test_rejects_missing_observation_value_type():
    message = VALID_ORU.replace("OBX|1|NM|", "OBX|1||")
    assert "VALUE_TYPE_REQUIRED" in codes(message)


def test_rejects_missing_order_service_identifier():
    message = VALID_ORU.replace(
        "OBR|1|ORDER001|FILL001|2823-3^Potassium^LN",
        "OBR|1|ORDER001|FILL001|",
    )
    assert "ORDER_CODE_REQUIRED" in codes(message)


def test_rejects_non_loinc_observation_code_system():
    message = VALID_ORU.replace("^LN", "^99LOCAL")
    assert "OBSERVATION_CODE_SYSTEM_REQUIRED" in codes(message)
