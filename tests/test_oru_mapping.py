import pytest

from hl7_fhir_processor.hl7_message import HL7Message
from hl7_fhir_processor.mapping import FHIRMappingError, map_oru_r01


ORU = (
    "MSH|^~\\&|HOSPITAL|LAB|FHIR|EHR|202610271500||ORU^R01|ORU001|P|2.5\r"
    "PID|1||PAT001^^^HOSPITAL^MR||DOE^JANE\r"
    "OBR|1|ORDER001|FILL001|2823-3^Potassium^LN\r"
    "OBX|1|NM|2823-3^Potassium^LN||6.8|mmol/L"
)


def resources():
    return map_oru_r01(HL7Message.parse(ORU))


def test_maps_oru_to_observation_and_diagnostic_report():
    result = resources()

    assert [resource["resourceType"] for resource in result] == [
        "Observation", "DiagnosticReport"
    ]


def test_maps_loinc_observation_code():
    observation = resources()[0]

    assert observation["code"]["coding"][0] == {
        "code": "2823-3",
        "display": "Potassium",
        "system": "http://loinc.org",
    }


def test_maps_numeric_result_and_units():
    observation = resources()[0]

    assert observation["valueQuantity"] == {
        "value": 6.8,
        "unit": "mmol/L",
        "code": "mmol/L",
        "system": "http://unitsofmeasure.org",
    }


def test_observation_references_patient():
    observation = resources()[0]

    assert observation["subject"]["reference"] == "Patient/PAT001"


def test_report_references_observation():
    report = resources()[1]

    assert report["resourceType"] == "DiagnosticReport"
    assert report["id"] == "ORU001"
    assert report["result"] == [{"reference": "Observation/ORU001-obx-1"}]


def test_report_maps_order_code():
    report = resources()[1]

    assert report["code"]["coding"][0]["code"] == "2823-3"
    assert report["code"]["coding"][0]["system"] == "http://loinc.org"


def test_maps_multiple_obx_segments():
    extra_obx = "\rOBX|2|NM|2824-1^Sodium^LN||140|mmol/L"
    message = HL7Message.parse(ORU + extra_obx)

    result = map_oru_r01(message)

    observations = [
        item for item in result if item["resourceType"] == "Observation"
    ]
    report = next(
        item for item in result if item["resourceType"] == "DiagnosticReport"
    )

    assert len(observations) == 2
    assert report["result"] == [
        {"reference": "Observation/ORU001-obx-1"},
        {"reference": "Observation/ORU001-obx-2"},
    ]


def test_rejects_non_oru_message():
    message = HL7Message.parse(ORU.replace("ORU^R01", "ADT^A01"))

    with pytest.raises(FHIRMappingError):
        map_oru_r01(message)


def test_rejects_invalid_numeric_result():
    message = HL7Message.parse(ORU.replace("||6.8|", "||high|"))

    with pytest.raises(FHIRMappingError, match="invalid numeric value"):
        map_oru_r01(message)


def test_maps_non_numeric_result_as_string():
    message = HL7Message.parse(
        ORU.replace("OBX|1|NM|", "OBX|1|ST|").replace("||6.8|", "||positive|")
    )

    observation = map_oru_r01(message)[0]

    assert observation["valueString"] == "positive"
    assert "valueQuantity" not in observation

def test_observation_and_report_reference_encounter_from_pv1_visit_number():
    message_text = ORU.replace(
        "OBR|",
        "PV1|1|I" + "|" * 17 + "VISIT123\rOBR|",
        1,
    )
    message = HL7Message.parse(message_text)

    result = map_oru_r01(message)
    observation = result[0]
    report = result[-1]

    assert observation["encounter"] == {"reference": "Encounter/VISIT123"}
    assert report["encounter"] == {"reference": "Encounter/VISIT123"}

def test_oru_without_pv1_does_not_add_encounter_references():
    message = HL7Message.parse(ORU)

    result = map_oru_r01(message)
    observation = result[0]
    report = result[-1]

    assert "encounter" not in observation
    assert "encounter" not in report



