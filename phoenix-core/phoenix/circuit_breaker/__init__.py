"""Circuit Breaker - Failure detection and automatic recovery."""

from .breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState, CircuitEvent, CircuitOpenError

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "CircuitEvent",
    "CircuitOpenError",
]