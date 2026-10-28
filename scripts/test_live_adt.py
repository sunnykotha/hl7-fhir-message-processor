import json
import uuid
from urllib.request import Request, urlopen

from hl7_fhir_processor.fhir_client import FHIRClient
from hl7_fhir_processor.processor import HL7Processor

BASE_URL = "https://hapi.fhir.org/baseR4"
suffix = uuid.uuid4().hex[:12]
patient_identifier = "LIVE" + suffix
visit_identifier = "VISIT" + suffix
control_id = "MSG" + suffix

pv1_fields = ["PV1", "1", "I"] + [""] * 16 + [visit_identifier]
raw_message = "\r".join([
    "MSH|^~\\&|TESTHOSP|ADT|FHIR|EHR|202610281200||ADT^A01|" + control_id + "|P|2.5",
    "PID|1||" + patient_identifier + "^^^TESTHOSP^MR||LIVE^TEST||19800115|U",
    "|".join(pv1_fields),
])

client = FHIRClient(BASE_URL)
processor = HL7Processor()

def deliver(resources):
    for resource in resources:
        saved = client.upsert(resource)
        print(f"Upserted {saved.get('resourceType')}/{saved.get('id')}")

result = processor.process_with_downstream(raw_message, deliver)
if not result.accepted:
    raise RuntimeError(f"Processing or delivery failed: {result.error}")

print("HL7 processing accepted:", result.accepted)
print("ACK returned:", result.ack is not None)

patient_resource = next(r for r in result.resources if r["resourceType"] == "Patient")
encounter_resource = next(r for r in result.resources if r["resourceType"] == "Encounter")
patient_id = patient_resource["id"]
encounter_id = encounter_resource["id"]

def get_resource(resource_type, resource_id):
    request = Request(
        f"{BASE_URL}/{resource_type}/{resource_id}",
        headers={"Accept": "application/fhir+json"},
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))

saved_patient = get_resource("Patient", patient_id)
saved_encounter = get_resource("Encounter", encounter_id)
expected_reference = f"Patient/{patient_id}"
actual_reference = saved_encounter.get("subject", {}).get("reference")

if saved_patient.get("id") != patient_id:
    raise RuntimeError("Patient read-back verification failed")
if actual_reference != expected_reference:
    raise RuntimeError(
        f"Encounter subject mismatch: expected {expected_reference}, got {actual_reference}"
    )

print(f"PASS: Patient/{patient_id} exists on the server.")
print(f"PASS: Encounter/{encounter_id} exists on the server.")
print(f"PASS: Encounter.subject.reference = {actual_reference}")
