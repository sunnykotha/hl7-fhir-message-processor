from hl7_fhir_processor.processor import HL7Processor, TransientDownstreamError

raw_message = "\r".join([
    "MSH|^~\\&|TESTHOSP|ADT|FHIR|EHR|202610281230||ADT^A01|RETRYTEST001|P|2.5",
    "PID|1||RETRYPAT001^^^TESTHOSP^MR||RETRY^TEST||19800115|U",
    "|".join(["PV1", "1", "I"] + [""] * 16 + ["RETRYVISIT001"]),
])

processor = HL7Processor()
attempts = []
delays = []

def flaky_downstream(resources):
    attempts.append(len(resources))
    if len(attempts) <= 3:
        raise TransientDownstreamError("Simulated temporary service failure")
    return {"status": "success"}

result = processor.process_with_downstream(
    raw_message,
    flaky_downstream,
    sleep_fn=delays.append,
)

assert result.accepted, "Message should succeed after retries"
assert len(attempts) == 4, f"Expected 4 attempts, got {len(attempts)}"
assert delays == [2, 4, 8], f"Unexpected retry delays: {delays}"
print("PASS: Message succeeded after three transient failures.")
print("PASS: Total attempts =", len(attempts))
print("PASS: Retry delays =", delays)
print("PASS: Final ACK returned =", result.ack is not None)
