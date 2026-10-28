import pytest

from hl7_fhir_processor.hl7_message import HL7Message
from hl7_fhir_processor.mapping import FHIRMappingError, map_adt_a01


ADT = (
    "MSH|^~\\&|HOSPITAL|ADT|FHIR|EHR|202610271500||ADT^A01|ADT001|P|2.5\r"
    "PID|1||PAT001^^^HOSPITAL^MR||DOE^JANE||19800115|F\r"
    "PV1|1|I"
)


def resources():
    return map_adt_a01(HL7Message.parse(ADT))


def test_maps_adt_to_patient_and_encounter():
    result = resources()

    assert [resource["resourceType"] for resource in result] == [
        "Patient", "Encounter"
    ]


def test_maps_patient_identifier_and_name():
    patient = resources()[0]

    assert patient["identifier"][0]["value"] == "PAT001"
    assert patient["identifier"][0]["type"]["coding"][0]["code"] == "MR"
    assert patient["name"] == [{"family": "DOE", "given": ["JANE"]}]


def test_maps_patient_gender_and_birth_date():
    patient = resources()[0]

    assert patient["gender"] == "female"
    assert patient["birthDate"] == "1980-01-15"


def test_maps_inpatient_encounter_and_patient_reference():
    encounter = resources()[1]

    assert encounter["status"] == "in-progress"
    assert encounter["class"]["code"] == "IMP"
    assert encounter["subject"]["reference"] == "Patient/PAT001"


def test_encounter_id_uses_message_control_id():
    encounter = resources()[1]

    assert encounter["id"] == "ADT001"


def test_rejects_non_adt_message():
    message = HL7Message.parse(
        ADT.replace("ADT^A01", "ORU^R01")
    )

    with pytest.raises(FHIRMappingError):
        map_adt_a01(message)


def test_rejects_unsupported_patient_class():
    message = HL7Message.parse(
        ADT.replace("PV1|1|I", "PV1|1|Z")
    )

    with pytest.raises(FHIRMappingError):
        map_adt_a01(message)


def test_maps_admission_datetime_when_available():
    message = HL7Message.parse(
        ADT.replace("PV1|1|I", "PV1|1|I" + "|" * 42 + "20261027153000")
    )

    encounter = map_adt_a01(message)[1]

    assert encounter["period"]["start"] == "2026-10-27T15:30:00"

def test_encounter_id_uses_visit_number_when_available():
    message = HL7Message.parse(
        ADT.replace("PV1|1|I", "PV1|1|I" + "|" * 17 + "VISIT123")
    )

    encounter = map_adt_a01(message)[1]

    assert encounter["id"] == "VISIT123"

