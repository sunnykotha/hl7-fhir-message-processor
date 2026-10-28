import pytest

from hl7_fhir_processor.retry import RetryPolicy


def test_default_policy_allows_four_total_attempts():
    policy = RetryPolicy()

    assert policy.max_attempts == 4
    assert [policy.can_retry(n) for n in range(1, 5)] == [
        True, True, True, False
    ]


def test_default_exponential_backoff_delays():
    policy = RetryPolicy()

    assert policy.delay_before_retry(1) == 2
    assert policy.delay_before_retry(2) == 4
    assert policy.delay_before_retry(3) == 8


def test_single_attempt_policy_has_no_retries():
    policy = RetryPolicy(max_attempts=1)

    assert policy.can_retry(1) is False


def test_custom_retry_policy():
    policy = RetryPolicy(
        max_attempts=3,
        initial_delay_seconds=1.5,
        backoff_multiplier=3,
    )

    assert policy.can_retry(1) is True
    assert policy.delay_before_retry(1) == 1.5
    assert policy.delay_before_retry(2) == 4.5
    assert policy.can_retry(3) is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_attempts": 0},
        {"initial_delay_seconds": -1},
        {"backoff_multiplier": 0.5},
    ],
)
def test_rejects_invalid_policy_configuration(kwargs):
    with pytest.raises(ValueError):
        RetryPolicy(**kwargs)


@pytest.mark.parametrize("attempts", [-1])
def test_rejects_negative_attempt_count(attempts):
    with pytest.raises(ValueError):
        RetryPolicy().can_retry(attempts)


@pytest.mark.parametrize("attempts", [0, -1])
def test_rejects_invalid_retry_delay_attempt(attempts):
    with pytest.raises(ValueError):
        RetryPolicy().delay_before_retry(attempts)


def test_rejects_delay_after_maximum_attempt():
    policy = RetryPolicy()

    with pytest.raises(ValueError, match="No retry remains"):
        policy.delay_before_retry(4)
