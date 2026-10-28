from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    """Configure retry limits and exponential backoff for transient failures."""

    max_attempts: int = 4
    initial_delay_seconds: float = 2.0
    backoff_multiplier: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_delay_seconds < 0:
            raise ValueError("initial_delay_seconds must not be negative")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be at least 1")

    def can_retry(self, attempts_made: int) -> bool:
        """Return whether another attempt is allowed after attempts_made."""
        if attempts_made < 0:
            raise ValueError("attempts_made must not be negative")
        return attempts_made < self.max_attempts

    def delay_before_retry(self, attempts_made: int) -> float:
        """Return the delay before the next attempt after a failed attempt."""
        if attempts_made < 1:
            raise ValueError("attempts_made must be at least 1")
        if not self.can_retry(attempts_made):
            raise ValueError("No retry remains after the maximum attempt count")

        return self.initial_delay_seconds * (
            self.backoff_multiplier ** (attempts_made - 1)
        )
