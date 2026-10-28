import json
import uuid
from urllib.request import Request, urlopen

from hl7_fhir_processor.fhir_client import FHIRClient
from hl7_fhir_processor.processor import HL7Processor

BASE_URL = "https://hapi.fhir.org/baseR4"
patient_identifier = "LIVEf5b1a35082fa"
visit_identifier = "VISITf5b1a35082fa"
control_id = "ORU" + uuid.uuid4().hex[:12]
order_id = "ORDER" + uuid.uuid4().hex[:12]

raw_message = "\r".join([
    "MSH|^~\\&|TESTLAB|LAB|FHIR|EHR|202610281210||ORU^R01|" + control_id + "|P|2.5",
    "PID|1||" + patient_identifier + "^^^TESTHOSP^MR||LIVE^TEST||19800115|U",
    "|".join(["PV1", "1", "I"] + [""] * 16 + [visit_identifier]),
    "OBR|1|" + order_id + "|" + order_id + "|2823-3^Potassium^LN",
    "OBX|1|NM|2823-3^Potassium^LN||6.8|mmol/L|||||F",
])

client = FHIRClient(BASE_URL)
processor = HL7Processor()

def deliver(resources):
    for resource in resources:
        saved = client.upsert(resource)
        print(f"Upserted {saved.get('resourceType')}/{saved.get('id')}")

result = processor.process_with_downstream(raw_message, deliver)
if not result.accepted:
    raise RuntimeError(f"ORU processing or delivery failed: {result.error}")

observations = [r for r in result.resources if r["resourceType"] == "Observation"]
reports = [r for r in result.resources if r["resourceType"] == "DiagnosticReport"]
if not observations or not reports:
    raise RuntimeError("Expected Observation and DiagnosticReport resources were not mapped")

def get_resource(resource_type, resource_id):
    request = Request(
        f"{BASE_URL}/{resource_type}/{resource_id}",
        headers={"Accept": "application/fhir+json"},
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))

observation = get_resource("Observation", observations[0]["id"])
report = get_resource("DiagnosticReport", reports[0]["id"])
expected_patient = "Patient/" + patient_identifier
expected_encounter = "Encounter/" + visit_identifier

if observation.get("subject", {}).get("reference") != expected_patient:
    raise RuntimeError("Observation Patient reference does not match")
if observation.get("encounter", {}).get("reference") != expected_encounter:
    raise RuntimeError("Observation Encounter reference does not match")
quantity = observation.get("valueQuantity", {})
if quantity.get("value") != 6.8:
    raise RuntimeError(f"Unexpected potassium value: {quantity}")
if quantity.get("unit") != "mmol/L":
    raise RuntimeError(f"Unexpected potassium unit: {quantity}")

report_patient = report.get("subject", {}).get("reference")
if report_patient != expected_patient:
    raise RuntimeError(f"DiagnosticReport Patient reference mismatch: {report_patient}")

print("HL7 processing accepted:", result.accepted)
print("ACK returned:", result.ack is not None)
print("PASS: Observation saved and read back.")
print("PASS: Potassium value is 6.8 mmol/L.")
print("PASS: Observation references the correct Patient and Encounter.")
print("PASS: DiagnosticReport references the correct Patient.")

