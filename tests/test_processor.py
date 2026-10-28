from hl7_fhir_processor.processor import HL7Processor


ADT_MESSAGE = (
    "MSH|^~\\&|SENDER|FAC|RECEIVER|FAC|20250101120000||"
    "ADT^A01|ADT-CTRL-1|P|2.5\r"
    "PID|1||12345^^^HOSP^MR||Doe^Jane||19800101|F\r"
    "PV1|1|I\r"
)

ORU_MESSAGE = (
    "MSH|^~\\&|SENDER|FAC|RECEIVER|FAC|20250101120000||"
    "ORU^R01|ORU-CTRL-1|P|2.5\r"
    "PID|1||12345^^^HOSP^MR||Doe^Jane\r"
    "OBR|1||ORDER-1|2823-3^Potassium^LN\r"
    "OBX|1|NM|2823-3^Potassium^LN||6.8|mmol/L^millimoles per liter^UCUM\r"
)


def test_processes_adt_a01_into_patient_and_encounter():
    result = HL7Processor().process(ADT_MESSAGE)

    assert result.accepted is True
    assert result.error is None
    assert result.ack is not None
    assert [resource["resourceType"] for resource in result.resources] == [
        "Patient",
        "Encounter",
    ]


def test_processes_adt_a08_patient_update():
    message = ADT_MESSAGE.replace("ADT^A01", "ADT^A08").replace(
        "ADT-CTRL-1", "ADT-UPDATE-1"
    ).replace("Doe^Jane", "Smith^Jane")

    result = HL7Processor().process(message)

    assert result.accepted is True
    assert result.error is None
    patient = next(
        resource for resource in result.resources
        if resource["resourceType"] == "Patient"
    )
    assert patient["name"][0]["family"] == "Smith"

def test_processes_oru_r01_into_observation_and_report():
    result = HL7Processor().process(ORU_MESSAGE)

    assert result.accepted is True
    assert result.error is None
    resource_types = [resource["resourceType"] for resource in result.resources]
    assert "Observation" in resource_types
    assert "DiagnosticReport" in resource_types


def test_rejects_invalid_message_and_records_dead_letter():
    message = (
        "MSH|^~\\&|SENDER|FAC|RECEIVER|FAC|20250101120000||"
        "ADT^A01|ADT-INVALID-1|P|2.5\r"
        "PID|1||||Doe^Jane\r"
        "PV1|1|I\r"
    )
    processor = HL7Processor()

    result = processor.process(message)

    assert result.accepted is False
    assert result.ack is not None
    assert result.error is not None
    assert result.dead_lettered is True
    assert len(processor.dead_letter_queue) == 1


def test_duplicate_message_is_acknowledged_without_remapping():
    processor = HL7Processor()

    first = processor.process(ADT_MESSAGE)
    second = processor.process(ADT_MESSAGE)

    assert first.accepted is True
    assert first.duplicate is False
    assert len(first.resources) == 2
    assert second.accepted is True
    assert second.duplicate is True
    assert second.resources == ()


def test_malformed_message_returns_rejection_without_ack():
    result = HL7Processor().process("not an HL7 message")

    assert result.accepted is False
    assert result.ack is None
    assert result.resources == ()
    assert result.error is not None


def test_processes_adt_a40_patient_merge():
    message = (
        "MSH|^~\\&|SENDER|FAC|RECEIVER|FAC|20250101120000||"
        "ADT^A40|ADT-MERGE-1|P|2.5\r"
        "PID|1||SURVIVOR-123^^^HOSP^MR||Smith^Jane||19800101|F\r"
        "MRG|OLD-456^^^HOSP^MR\r"
    )

    result = HL7Processor().process(message)

    assert result.accepted is True
    assert result.error is None
    patient = next(
        resource for resource in result.resources
        if resource["resourceType"] == "Patient"
    )
    assert patient["id"] == "SURVIVOR-123"
    assert patient["identifier"][0]["value"] == "SURVIVOR-123"
    assert patient["link"] == [{
        "other": {"reference": "Patient/OLD-456"},
        "type": "replaces",
    }]

def test_rejects_adt_a40_without_prior_patient_identifier():
    message = (
        "MSH|^~\\&|SENDER|FAC|RECEIVER|FAC|20250101120000||"
        "ADT^A40|ADT-MERGE-MISSING-1|P|2.5\r"
        "PID|1||SURVIVOR-123^^^HOSP^MR||Smith^Jane||19800101|F\r"
    )

    result = HL7Processor().process(message)

    assert result.accepted is False
    assert result.error is not None
    assert result.dead_lettered is True

def test_adt_a08_before_a01_uses_the_same_patient_id():
    processor = HL7Processor()

    a08_message = (
        "MSH|^~\\&|SENDER|FAC|RECEIVER|FAC|20261027120000||"
        "ADT^A08|A08-BEFORE-A01|P|2.5\r"
        "PID|1||PATIENT-808^^^HOSP^MR||Updated^Patient||19800101|F"
    )
    a01_message = (
        "MSH|^~\\&|SENDER|FAC|RECEIVER|FAC|20261027120100||"
        "ADT^A01|A01-AFTER-A08|P|2.5\r"
        "PID|1||PATIENT-808^^^HOSP^MR||Updated^Patient||19800101|F\r"
        "PV1|1|I"
    )

    a08_result = processor.process(a08_message)
    a01_result = processor.process(a01_message)

    assert a08_result.accepted is True
    assert a01_result.accepted is True

    a08_patient = next(
        resource for resource in a08_result.resources
        if resource["resourceType"] == "Patient"
    )
    a01_patient = next(
        resource for resource in a01_result.resources
        if resource["resourceType"] == "Patient"
    )

    assert a08_patient["id"] == "PATIENT-808"
    assert a01_patient["id"] == a08_patient["id"]