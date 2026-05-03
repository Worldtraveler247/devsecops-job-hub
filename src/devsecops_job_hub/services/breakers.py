"""Per-host circuit breakers for outbound HTTP calls.

When a third-party API (Greenhouse, Lever, SEC EDGAR) is genuinely down,
tenacity will retry 3x per company and then give up — wasting time and
connections on every refresh until ops fixes it. A circuit breaker short-
circuits subsequent calls once we've seen N consecutive failures and lets
the service recover unmolested.

State machine
- CLOSED: normal operation. Failures bump the counter; threshold trips us
  to OPEN.
- OPEN: every call short-circuits via CircuitOpenError. After cooldown,
  one trial call is allowed through (HALF-OPEN behavior is implicit — we
  just clear state and the next call proceeds normally; success closes,
  failure re-opens).

Custom rather than `purgatory`/`pybreaker` because the requirements are
small (per-host, async, no metrics/events bus) and the state machine fits
in one screen — keeping the dependency surface tight and the behavior
inspectable.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DEFAULT_FAILURE_THRESHOLD = 3
DEFAULT_OPEN_SECONDS = 300  # 5 minutes


class CircuitOpenError(Exception):
    """Raised when a call is short-circuited by an open breaker."""

    def __init__(self, name: str) -> None:
        super().__init__(f"circuit breaker {name!r} is open")
        self.name = name


@dataclass
class _State:
    failure_count: int = 0
    opened_at: float | None = None  # None = closed; float = open since this monotonic timestamp


class CircuitBreakerRegistry:
    """A registry of named breakers. The default global instance is exposed
    via the module-level `is_open` / `record_success` / `record_failure`
    helpers; tests can instantiate their own to avoid global state."""

    def __init__(
        self,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        open_seconds: int = DEFAULT_OPEN_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._states: dict[str, _State] = {}
        self._threshold = failure_threshold
        self._open_seconds = open_seconds
        self._clock = clock

    def _state(self, name: str) -> _State:
        if name not in self._states:
            self._states[name] = _State()
        return self._states[name]

    def is_open(self, name: str) -> bool:
        s = self._state(name)
        if s.opened_at is None:
            return False
        if self._clock() - s.opened_at >= self._open_seconds:
            # Cooldown elapsed → drop back to closed for the next call.
            logger.info("breaker %s reset after %ds cooldown", name, self._open_seconds)
            s.opened_at = None
            s.failure_count = 0
            return False
        return True

    def record_success(self, name: str) -> None:
        s = self._state(name)
        if s.failure_count > 0 or s.opened_at is not None:
            logger.info("breaker %s recovered (success after failures)", name)
        s.failure_count = 0
        s.opened_at = None

    def record_failure(self, name: str) -> None:
        s = self._state(name)
        s.failure_count += 1
        if s.failure_count >= self._threshold and s.opened_at is None:
            s.opened_at = self._clock()
            logger.warning(
                "breaker %s opened after %d consecutive failures; will skip for %ds",
                name,
                s.failure_count,
                self._open_seconds,
            )

    # Test-only helpers. Production code shouldn't need these.
    def reset(self, name: str | None = None) -> None:
        if name is None:
            self._states.clear()
        else:
            self._states.pop(name, None)


# Process-wide default registry. Adapters import these helpers directly.
_default = CircuitBreakerRegistry()


def is_open(name: str) -> bool:
    return _default.is_open(name)


def record_success(name: str) -> None:
    _default.record_success(name)


def record_failure(name: str) -> None:
    _default.record_failure(name)


def reset_all() -> None:
    _default.reset()
