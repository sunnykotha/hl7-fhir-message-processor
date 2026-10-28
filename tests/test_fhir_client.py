import json
from email.message import Message
from io import BytesIO
from urllib.error import HTTPError
from unittest.mock import patch

import pytest

from hl7_fhir_processor.fhir_client import FHIRClient
from hl7_fhir_processor.processor import TransientDownstreamError


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_upsert_uses_put_and_explicit_resource_id():
    resource = {"resourceType": "Patient", "id": "synthetic-patient"}
    response_data = {"resourceType": "Patient", "id": "synthetic-patient"}
    with patch("hl7_fhir_processor.fhir_client.urlopen", return_value=FakeResponse(response_data)) as mocked:
        result = FHIRClient("https://example.test/fhir").upsert(resource)
    request = mocked.call_args.args[0]
    assert request.full_url == "https://example.test/fhir/Patient/synthetic-patient"
    assert request.get_method() == "PUT"
    assert json.loads(request.data.decode("utf-8")) == resource
    assert result["id"] == "synthetic-patient"


def test_create_uses_post():
    resource = {"resourceType": "Patient"}
    with patch("hl7_fhir_processor.fhir_client.urlopen", return_value=FakeResponse({"resourceType": "Patient", "id": "server-id"})) as mocked:
        result = FHIRClient("https://example.test/fhir").create(resource)
    request = mocked.call_args.args[0]
    assert request.full_url == "https://example.test/fhir/Patient"
    assert request.get_method() == "POST"
    assert result["id"] == "server-id"


def test_upsert_requires_resource_id():
    with pytest.raises(ValueError, match="resource ID"):
        FHIRClient("https://example.test/fhir").upsert({"resourceType": "Patient"})


def test_server_5xx_is_transient():
    headers = Message()
    error = HTTPError("https://example.test/fhir/Patient", 503, "Unavailable", headers, BytesIO(b"temporary outage"))
    with patch("hl7_fhir_processor.fhir_client.urlopen", side_effect=error):
        with pytest.raises(TransientDownstreamError, match="HTTP 503"):
            FHIRClient("https://example.test/fhir").upsert({"resourceType": "Patient", "id": "p1"})


def test_server_4xx_is_permanent():
    headers = Message()
    error = HTTPError("https://example.test/fhir/Patient", 400, "Bad Request", headers, BytesIO(b"invalid resource"))
    with patch("hl7_fhir_processor.fhir_client.urlopen", side_effect=error):
        with pytest.raises(RuntimeError, match="HTTP 400"):
            FHIRClient("https://example.test/fhir").upsert({"resourceType": "Patient", "id": "p1"})
