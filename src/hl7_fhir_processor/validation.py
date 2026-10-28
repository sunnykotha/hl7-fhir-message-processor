from dataclasses import dataclass

from hl7_fhir_processor.hl7_message import HL7Message


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    segment: str | None = None


def validate_message(message: HL7Message) -> list[ValidationIssue]:
    """Validate supported message types and their required fields."""
    issues = []

    def add(code: str, detail: str, segment: str | None = None) -> None:
        issues.append(ValidationIssue(code, detail, segment))

    msh = message.first_segment("MSH")
    if msh is None:
        return [ValidationIssue("MSH_REQUIRED", "MSH segment is required")]

    message_type = msh.field(9).split("^")
    if len(message_type) < 2 or not message_type[0] or not message_type[1]:
        add("MESSAGE_TYPE_REQUIRED", "MSH-9 must contain message type and trigger event", "MSH")
        return issues

    event = (message_type[0], message_type[1])

    if not msh.field(10).strip():
        add("CONTROL_ID_REQUIRED", "MSH-10 message control ID is required", "MSH")

    if event not in {("ADT", "A01"), ("ADT", "A08"), ("ADT", "A40"), ("ORU", "R01")}:
        add(
            "UNSUPPORTED_MESSAGE_TYPE",
            f"Unsupported message type: {'^'.join(message_type)}",
            "MSH",
        )
        return issues

    pid = message.first_segment("PID")
    if pid is None:
        add("PID_REQUIRED", "PID segment is required", "PID")
    elif not pid.components(3)[0].strip():
        add("PATIENT_ID_REQUIRED", "PID-3 patient identifier is required", "PID")

    if event == ("ADT", "A01"):
        pv1 = message.first_segment("PV1")
        if pv1 is None:
            add("PV1_REQUIRED", "PV1 segment is required for ADT^A01", "PV1")
        elif not pv1.field(2).strip():
            add("PATIENT_CLASS_REQUIRED", "PV1-2 patient class is required", "PV1")

    if event == ("ORU", "R01"):
        obr_segments = message.segments_named("OBR")
        obx_segments = message.segments_named("OBX")

        if not obr_segments:
            add("OBR_REQUIRED", "At least one OBR segment is required", "OBR")
        else:
            for obr in obr_segments:
                if not obr.field(4).strip():
                    add(
                        "ORDER_CODE_REQUIRED",
                        "OBR-4 service identifier is required",
                        "OBR",
                    )

        if not obx_segments:
            add(
                "OBX_REQUIRED",
                "At least one OBX segment is required",
                "OBX",
            )
        else:
            for index, obx in enumerate(obx_segments, start=1):
                if not obx.field(2).strip():
                    add(
                        "VALUE_TYPE_REQUIRED",
                        f"OBX-2 value type is required (OBX #{index})",
                        "OBX",
                    )
                if not obx.field(3).strip():
                    add(
                        "OBSERVATION_CODE_REQUIRED",
                        f"OBX-3 observation identifier is required (OBX #{index})",
                        "OBX",
                    )
                else:
                    code_components = obx.components(3)
                    code_system = (
                        code_components[2].strip().upper()
                        if len(code_components) > 2
                        else ""
                    )
                    if code_system not in {"LN", "LOINC"}:
                        add(
                            "OBSERVATION_CODE_SYSTEM_REQUIRED",
                            f"OBX-3 must use the LOINC code system (OBX #{index})",
                            "OBX",
                        )
                if not obx.field(5).strip():
                    add(
                        "OBSERVATION_VALUE_REQUIRED",
                        f"OBX-5 observation value is required (OBX #{index})",
                        "OBX",
                    )

    return issues
