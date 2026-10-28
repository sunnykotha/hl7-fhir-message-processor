import re

from hl7_fhir_processor.hl7_message import HL7Message
from hl7_fhir_processor.validation import validate_message


class FHIRMappingError(ValueError):
    """Raised when an HL7 message cannot be mapped to FHIR resources."""


def _resource_id(value: str) -> str:
    """Create a deterministic FHIR-compatible logical ID."""
    result = re.sub(r"[^A-Za-z0-9.-]", "-", value)
    result = result.strip(".-")
    result = result[:64]
    return result or "unknown"


def _patient_gender(pid) -> str | None:
    value = pid.field(8).strip().upper()
    mapping = {
        "M": "male",
        "F": "female",
        "O": "other",
        "U": "unknown",
        "A": "other",
        "N": "unknown",
    }
    return mapping.get(value)


def _patient_resource(pid) -> dict:
    identifier_components = pid.components(3)
    identifier_value = identifier_components[0].strip()

    if not identifier_value:
        raise FHIRMappingError("PID-3 patient identifier is required")

    identifier = {
        "value": identifier_value,
    }

    # CX-5 identifies the identifier type, such as MR (medical record number).
    if len(identifier_components) >= 5 and identifier_components[4].strip():
        identifier["type"] = {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                "code": identifier_components[4].strip(),
            }]
        }

    resource = {
        "resourceType": "Patient",
        "id": _resource_id(identifier_value),
        "identifier": [identifier],
    }

    # PID-5 is XPN: family name ^ given name ^ middle name ...
    name_components = pid.components(5)
    family = name_components[0].strip() if name_components else ""
    given = name_components[1].strip() if len(name_components) > 1 else ""

    if family or given:
        name = {}
        if family:
            name["family"] = family
        if given:
            name["given"] = [given]
        resource["name"] = [name]

    gender = _patient_gender(pid)
    if gender:
        resource["gender"] = gender

    birth_date = pid.field(7).strip()
    if re.fullmatch(r"\d{8}", birth_date):
        resource["birthDate"] = (
            f"{birth_date[:4]}-{birth_date[4:6]}-{birth_date[6:]}"
        )

    return resource


def _encounter_resource(pv1, patient_id: str, control_id: str) -> dict:
    patient_class = pv1.field(2).strip().upper()

    class_mapping = {
        "I": ("IMP", "inpatient encounter"),
        "O": ("AMB", "ambulatory"),
        "E": ("EMER", "emergency"),
        "P": ("PRENC", "pre-admission"),
        "R": ("REHAB", "rehabilitation"),
        "B": ("IMP", "inpatient encounter"),
        "C": ("AMB", "ambulatory"),
        "N": ("AMB", "ambulatory"),
        "U": ("AMB", "ambulatory"),
    }

    if patient_class not in class_mapping:
        raise FHIRMappingError(
            f"Unsupported PV1-2 patient class: {patient_class!r}"
        )

    class_code, class_display = class_mapping[patient_class]

    resource = {
        "resourceType": "Encounter",
        "id": _resource_id(control_id),
        "status": "in-progress",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": class_code,
            "display": class_display,
        },
        "subject": {
            "reference": f"Patient/{patient_id}",
        },
    }

    # PV1-44 is the visit/admission date-time.
    admit_datetime = pv1.field(44).strip()
    if re.fullmatch(r"\d{14}", admit_datetime):
        resource["period"] = {
            "start": (
                f"{admit_datetime[:4]}-{admit_datetime[4:6]}-"
                f"{admit_datetime[6:8]}T{admit_datetime[8:10]}:"
                f"{admit_datetime[10:12]}:{admit_datetime[12:14]}"
            )
        }
    elif re.fullmatch(r"\d{8}", admit_datetime):
        resource["period"] = {
            "start": (
                f"{admit_datetime[:4]}-{admit_datetime[4:6]}-"
                f"{admit_datetime[6:8]}"
            )
        }

    return resource


def map_adt_a01(message: HL7Message) -> list[dict]:
    """Map a validated ADT^A01 message to Patient and Encounter resources."""
    issues = validate_message(message)
    if issues:
        summary = "; ".join(issue.message for issue in issues)
        raise FHIRMappingError(summary)

    msh = message.first_segment("MSH")
    if msh is None or msh.field(9).split("^")[:2] != ["ADT", "A01"]:
        raise FHIRMappingError("Expected an ADT^A01 message")

    pid = message.first_segment("PID")
    pv1 = message.first_segment("PV1")

    if pid is None or pv1 is None:
        raise FHIRMappingError("PID and PV1 segments are required")

    patient = _patient_resource(pid)
    visit_components = pv1.components(19)
    visit_number = visit_components[0].strip() if visit_components else ""
    encounter_id = visit_number or msh.field(10).strip()

    encounter = _encounter_resource(
        pv1,
        patient["id"],
        encounter_id,
    )

    return [patient, encounter]


def map_adt_a08(message: HL7Message) -> list[dict]:
    """Map an ADT^A08 patient update to a FHIR Patient resource."""
    issues = validate_message(message)
    if issues:
        summary = "; ".join(issue.message for issue in issues)
        raise FHIRMappingError(summary)

    msh = message.first_segment("MSH")
    if msh is None or msh.field(9).split("^")[:2] != ["ADT", "A08"]:
        raise FHIRMappingError("Expected an ADT^A08 message")

    pid = message.first_segment("PID")
    if pid is None:
        raise FHIRMappingError("PID segment is required")

    return [_patient_resource(pid)]

def map_adt_a40(message: HL7Message) -> list[dict]:
    """Map an ADT^A40 merge to the surviving patient's FHIR resource."""
    issues = validate_message(message)
    if issues:
        summary = "; ".join(issue.message for issue in issues)
        raise FHIRMappingError(summary)

    msh = message.first_segment("MSH")
    if msh is None or msh.field(9).split("^")[:2] != ["ADT", "A40"]:
        raise FHIRMappingError("Expected an ADT^A40 message")

    pid = message.first_segment("PID")
    mrg = message.first_segment("MRG")
    if pid is None or mrg is None:
        raise FHIRMappingError("PID and MRG segments are required")

    prior_identifier = mrg.components(1)[0].strip()
    if not prior_identifier:
        raise FHIRMappingError("MRG-1 prior patient identifier is required")

    patient = _patient_resource(pid)
    patient["link"] = [{
        "other": {
            "reference": f"Patient/{_resource_id(prior_identifier)}",
        },
        "type": "replaces",
    }]
    return [patient]

def _hl7_coding(components: tuple[str, ...]) -> dict:
    """Map an HL7 CE/CWE-style code to a FHIR Coding."""
    code = components[0].strip() if components else ""
    display = components[1].strip() if len(components) > 1 else ""
    code_system = components[2].strip().upper() if len(components) > 2 else ""

    coding = {}
    if code:
        coding["code"] = code
    if display:
        coding["display"] = display
    if code_system in {"LN", "LOINC"}:
        coding["system"] = "http://loinc.org"

    return coding


def map_oru_r01(message: HL7Message) -> list[dict]:
    """Map a validated ORU^R01 message to FHIR Observation and DiagnosticReport resources."""
    issues = validate_message(message)
    if issues:
        summary = "; ".join(issue.message for issue in issues)
        raise FHIRMappingError(summary)

    msh = message.first_segment("MSH")
    if msh is None or msh.field(9).split("^")[:2] != ["ORU", "R01"]:
        raise FHIRMappingError("Expected an ORU^R01 message")

    pid = message.first_segment("PID")
    obr_segments = message.segments_named("OBR")
    obx_segments = message.segments_named("OBX")

    if pid is None or not obr_segments or not obx_segments:
        raise FHIRMappingError("PID, OBR, and OBX segments are required")

    patient_components = pid.components(3)
    patient_identifier = patient_components[0].strip()
    if not patient_identifier:
        raise FHIRMappingError("PID-3 patient identifier is required")

    patient_id = _resource_id(patient_identifier)
    control_id = _resource_id(msh.field(10).strip())

    pv1 = message.first_segment("PV1")
    visit_components = pv1.components(19) if pv1 is not None else ()
    visit_number = visit_components[0].strip() if visit_components else ""
    encounter_reference = (
        f"Encounter/{_resource_id(visit_number)}" if visit_number else None
    )

    observations = []
    observation_ids = []

    for index, obx in enumerate(obx_segments, start=1):
        value_type = obx.field(2).strip().upper()
        code_components = obx.components(3)
        coding = _hl7_coding(code_components)

        if not coding.get("code"):
            raise FHIRMappingError(f"OBX #{index} has no observation code")

        observation_id = _resource_id(f"{control_id}-obx-{index}")
        observation_ids.append(observation_id)

        observation = {
            "resourceType": "Observation",
            "id": observation_id,
            "status": "final",
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                    "code": "laboratory",
                    "display": "Laboratory",
                }]
            }],
            "code": {"coding": [coding]},
            "subject": {"reference": f"Patient/{patient_id}"},
        }

        if encounter_reference:
            observation["encounter"] = {"reference": encounter_reference}

        value = obx.field(5).strip()
        if value_type in {"NM", "SN"}:
            try:
                numeric_value = float(value)
            except ValueError as exc:
                raise FHIRMappingError(
                    f"OBX #{index} contains an invalid numeric value"
                ) from exc

            quantity = {"value": numeric_value}
            unit_components = obx.components(6) if obx.field(6) else ()
            unit = unit_components[0].strip() if unit_components else ""
            unit_display = (
                unit_components[1].strip()
                if len(unit_components) > 1
                else unit
            )

            if unit:
                quantity["unit"] = unit_display or unit
                quantity["code"] = unit
                quantity["system"] = "http://unitsofmeasure.org"

            observation["valueQuantity"] = quantity
        else:
            observation["valueString"] = value

        # OBX-14 is the observation date/time.
        observation_datetime = obx.field(14).strip()
        if len(observation_datetime) == 14 and observation_datetime.isdigit():
            observation["effectiveDateTime"] = (
                f"{observation_datetime[:4]}-{observation_datetime[4:6]}-"
                f"{observation_datetime[6:8]}T{observation_datetime[8:10]}:"
                f"{observation_datetime[10:12]}:{observation_datetime[12:14]}"
            )
        elif len(observation_datetime) == 8 and observation_datetime.isdigit():
            observation["effectiveDateTime"] = (
                f"{observation_datetime[:4]}-{observation_datetime[4:6]}-"
                f"{observation_datetime[6:8]}"
            )

        observations.append(observation)

    # Use the first OBR as the report header; all OBX results are linked below.
    report_code = _hl7_coding(obr_segments[0].components(4))
    if not report_code.get("code"):
        raise FHIRMappingError("OBR-4 service identifier is required")

    report = {
        "resourceType": "DiagnosticReport",
        "id": control_id,
        "status": "final",
        "code": {"coding": [report_code]},
        "subject": {"reference": f"Patient/{patient_id}"},
        "result": [
            {"reference": f"Observation/{observation_id}"}
            for observation_id in observation_ids
        ],
    }

    if encounter_reference:
        report["encounter"] = {"reference": encounter_reference}

    return [*observations, report]

