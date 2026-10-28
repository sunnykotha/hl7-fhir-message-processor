from hl7_fhir_processor.hl7_message import HL7Message


def create_ack(
    message: HL7Message,
    accepted: bool,
    error_message: str | None = None,
    sending_application: str = "FHIR",
    sending_facility: str = "PROCESSOR",
) -> str:
    """Create an HL7 v2 ACK (AA) or negative acknowledgment (AE)."""
    msh = message.first_segment("MSH")
    if msh is None:
        raise ValueError("MSH segment is required to create an acknowledgment")

    control_id = msh.field(10).strip()
    if not control_id:
        raise ValueError("MSH-10 message control ID is required")

    field_sep = message.field_separator
    component_sep = message.encoding_characters[0]
    sending_datetime = __import__("datetime").datetime.now().strftime("%Y%m%d%H%M%S")

    original_sending_application = msh.field(3).strip() or "UNKNOWN"
    original_sending_facility = msh.field(4).strip() or "UNKNOWN"
    original_receiving_application = msh.field(5).strip() or "UNKNOWN"
    original_receiving_facility = msh.field(6).strip() or "UNKNOWN"
    version = msh.field(12).strip() or "2.5"

    ack_control_id = f"ACK-{control_id}"

    response_msh = field_sep.join([
        "MSH",
        message.encoding_characters,
        sending_application,
        sending_facility,
        original_sending_application,
        original_sending_facility,
        sending_datetime,
        "",
        f"ACK{component_sep}{msh.field(9).split(component_sep)[0]}",
        ack_control_id,
        "P",
        version,
    ])

    acknowledgment_code = "AA" if accepted else "AE"
    response_msa = field_sep.join([
        "MSA",
        acknowledgment_code,
        control_id,
    ])

    segments = [response_msh, response_msa]

    if not accepted and error_message:
        safe_error = error_message.replace(field_sep, " ").replace("\r", " ").replace("\n", " ")
        response_err = field_sep.join([
            "ERR",
            "",
            "",
            "",
            f"207{component_sep}Application internal error{component_sep}HL70357",
            "",
            "",
            safe_error,
        ])
        segments.append(response_err)

    return "\r".join(segments) + "\r"
