# HL7 v2 / FHIR Message Processor

A Python processor that parses HL7 v2 messages, validates them, maps supported messages to FHIR resources, and handles duplicates and processing failures.

## Features

- Parse HL7 segments, fields, components, repetitions, subcomponents, and supported escape sequences.
- Support MSH-declared delimiters, common line endings, and custom Z-segments.
- Parse text messages and encoded bytes.
- Map ADT^A01 to Patient and Encounter resources.
- Map ADT^A08 to Patient updates.
- Map ADT^A40 to Patient merge-related resources.
- Map ORU^R01 to Observation and DiagnosticReport resources.
- Validate required fields and laboratory LOINC codes.
- Detect duplicate message control IDs.
- Generate HL7 acknowledgements.
- Retry transient downstream failures with exponential backoff.
- Store failed messages in an in-memory dead-letter queue.
- Deliver FHIR resources through an HTTP client using POST or ID-preserving PUT.

## Requirements

- Python 3.11 or later.

## Setup

From the project root, activate or use the existing virtual environment:

```powershell
Set-Location "C:\Users\GK\hl7-fhir-message-processor"
& ".\.venv\Scripts\python.exe" -m pip install -e .
```

## Run tests

```powershell
& ".\.venv\Scripts\python.exe" -m pytest -v
```

For a concise summary:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest -q
```

## Processing and downstream delivery

`HL7Processor.process()` parses, validates, maps, and checks messages for duplicates.

`HL7Processor.process_with_downstream()` passes mapped resources to a caller-supplied callback. Transient failures represented by `TransientDownstreamError` are retried according to `RetryPolicy`.

## FHIR HTTP client

`FHIRClient` sends resources to a FHIR server. `create(resource)` uses POST, while `upsert(resource)` uses PUT with an explicit resource ID. HTTP 5xx responses and connection failures are treated as transient; HTTP 4xx responses are treated as permanent errors.

Example server used for live integration checks:

`https://hapi.fhir.org/baseR4`

Use synthetic test data only with public test servers. Do not send real patient information.

## Retry defaults

The default retry policy allows four total attempts, with delays of 2, 4, and 8 seconds between attempts.

## Limitations

- No inbound HL7 transport listener is included; messages must be supplied to the processor by the calling application.
- Idempotency tracking and dead-letter records are held in memory and do not survive process restarts.
- Byte decoding defaults to UTF-8 unless another encoding is explicitly supplied; MSH-18 does not automatically select the decoder.
- The live FHIR HTTP client is a minimal synchronous client, not a complete production FHIR integration.
- Supported message types and mapping rules are limited to those implemented and tested in this project.
