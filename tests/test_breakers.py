"""Unit tests for the circuit-breaker registry. Pure-state-machine logic
exercised through a controllable monotonic clock so we don't have to
sleep through the cooldown."""

from __future__ import annotations

from devsecops_job_hub.services.breakers import CircuitBreakerRegistry


class FakeClock:
    def __init__(self, t: float = 0.0) -> None:
        self._t = t

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


def make_registry(
    threshold: int = 3, open_seconds: int = 300
) -> tuple[CircuitBreakerRegistry, FakeClock]:
    clock = FakeClock()
    reg = CircuitBreakerRegistry(
        failure_threshold=threshold, open_seconds=open_seconds, clock=clock
    )
    return reg, clock


class TestCircuitBreakerRegistry:
    def test_starts_closed(self):
        reg, _ = make_registry()
        assert reg.is_open("greenhouse") is False

    def test_one_failure_does_not_open(self):
        reg, _ = make_registry()
        reg.record_failure("greenhouse")
        assert reg.is_open("greenhouse") is False

    def test_threshold_failures_opens_breaker(self):
        reg, _ = make_registry(threshold=3)
        reg.record_failure("greenhouse")
        reg.record_failure("greenhouse")
        reg.record_failure("greenhouse")
        assert reg.is_open("greenhouse") is True

    def test_success_resets_failure_count(self):
        reg, _ = make_registry(threshold=3)
        reg.record_failure("greenhouse")
        reg.record_failure("greenhouse")
        reg.record_success("greenhouse")
        # Counter reset; need 3 more to open again.
        reg.record_failure("greenhouse")
        reg.record_failure("greenhouse")
        assert reg.is_open("greenhouse") is False

    def test_breakers_are_independent_per_name(self):
        reg, _ = make_registry(threshold=2)
        reg.record_failure("greenhouse")
        reg.record_failure("greenhouse")
        assert reg.is_open("greenhouse") is True
        assert reg.is_open("lever") is False

    def test_cooldown_resets_state(self):
        reg, clock = make_registry(threshold=2, open_seconds=300)
        reg.record_failure("edgar")
        reg.record_failure("edgar")
        assert reg.is_open("edgar") is True
        clock.advance(299)
        assert reg.is_open("edgar") is True
        clock.advance(2)  # past 300s
        assert reg.is_open("edgar") is False

    def test_post_cooldown_failures_can_reopen(self):
        reg, clock = make_registry(threshold=2, open_seconds=10)
        reg.record_failure("greenhouse")
        reg.record_failure("greenhouse")
        assert reg.is_open("greenhouse") is True
        clock.advance(11)
        assert reg.is_open("greenhouse") is False
        # Now in fresh-closed state; need 2 fresh failures to reopen.
        reg.record_failure("greenhouse")
        assert reg.is_open("greenhouse") is False
        reg.record_failure("greenhouse")
        assert reg.is_open("greenhouse") is True

    def test_reset_specific_breaker(self):
        reg, _ = make_registry(threshold=2)
        reg.record_failure("greenhouse")
        reg.record_failure("greenhouse")
        reg.reset("greenhouse")
        assert reg.is_open("greenhouse") is False

    def test_reset_all(self):
        reg, _ = make_registry(threshold=2)
        reg.record_failure("greenhouse")
        reg.record_failure("greenhouse")
        reg.record_failure("lever")
        reg.record_failure("lever")
        reg.reset()
        assert reg.is_open("greenhouse") is False
        assert reg.is_open("lever") is False
