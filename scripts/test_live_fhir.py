import json
import uuid
from urllib.request import Request, urlopen

from hl7_fhir_processor.fhir_client import FHIRClient

BASE_URL = "https://hapi.fhir.org/baseR4"
unique_id = str(uuid.uuid4())

patient = {
    "resourceType": "Patient",
    "active": True,
    "identifier": [{
        "system": "https://example.org/hl7-fhir-processor/test",
        "value": unique_id,
    }],
    "name": [{
        "family": "Test",
        "given": ["LiveServer"],
    }],
    "gender": "unknown",
}

print("Creating synthetic Patient on the public test server...")
created = FHIRClient(BASE_URL).create(patient)
patient_id = created.get("id")

if not patient_id:
    raise RuntimeError(f"Server response did not contain an ID: {created}")

print(f"Created resource type: {created.get('resourceType')}")
print(f"Server-assigned Patient ID: {patient_id}")
print(f"Version ID: {created.get('meta', {}).get('versionId', 'not provided')}")

request = Request(
    f"{BASE_URL}/Patient/{patient_id}",
    headers={"Accept": "application/fhir+json"},
    method="GET",
)
with urlopen(request, timeout=30) as response:
    saved = json.loads(response.read().decode("utf-8"))

if saved.get("id") != patient_id or saved.get("resourceType") != "Patient":
    raise RuntimeError(f"Read-back verification failed: {saved}")

saved_identifiers = saved.get("identifier", [])
if not any(item.get("value") == unique_id for item in saved_identifiers):
    raise RuntimeError("Read-back Patient did not contain the unique test identifier")

print("PASS: Patient was created and read back successfully.")
print("Synthetic identifier verified.")
