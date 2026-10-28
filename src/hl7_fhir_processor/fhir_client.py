import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from hl7_fhir_processor.processor import TransientDownstreamError


class FHIRClient:
    """Minimal HTTP client for a FHIR server."""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def create(self, resource: dict) -> dict:
        """Create a resource using POST and return the server response."""
        resource_type = self._resource_type(resource)
        return self._send(
            f"{self.base_url}/{resource_type}", resource, "POST"
        )

    def upsert(self, resource: dict) -> dict:
        """Create or update a resource at its explicit FHIR ID using PUT."""
        resource_type = self._resource_type(resource)
        resource_id = resource.get("id")
        if not isinstance(resource_id, str) or not resource_id.strip():
            raise ValueError("FHIR resource ID is required for upsert")
        return self._send(
            f"{self.base_url}/{resource_type}/{resource_id}", resource, "PUT"
        )

    @staticmethod
    def _resource_type(resource: dict) -> str:
        if not isinstance(resource, dict):
            raise ValueError("FHIR resource must be a dictionary")
        resource_type = resource.get("resourceType")
        if not isinstance(resource_type, str) or not resource_type.strip():
            raise ValueError("FHIR resource resourceType is required")
        return resource_type

    def _send(self, url: str, resource: dict, method: str) -> dict:
        body = json.dumps(resource).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/fhir+json",
                "Accept": "application/fhir+json",
            },
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            message = f"FHIR server returned HTTP {exc.code}: {detail}"
            if exc.code >= 500:
                raise TransientDownstreamError(message) from exc
            raise RuntimeError(message) from exc
        except (URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise TransientDownstreamError(
                f"FHIR server connection failed: {exc}"
            ) from exc
