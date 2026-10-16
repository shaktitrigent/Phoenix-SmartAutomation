"""Circuit Breaker - Failure detection and automatic recovery.

Implements the circuit breaker pattern to prevent cascading failures
and provide automatic recovery with configurable thresholds.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation, requests pass through
    OPEN = "open"            # Circuit is open, requests are blocked
    HALF_OPEN = "half_open"  # Trial mode, some requests allowed through


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5  # Number of failures to open circuit
    success_threshold: int = 2  # Number of successes to close circuit
    timeout_ms: int = 60000  # How long to stay in OPEN state
    half_open_max_calls: int = 3  # Max calls allowed in HALF_OPEN state


@dataclass
class CircuitEvent:
    """Record of a circuit breaker event."""
    timestamp: float
    state: CircuitState
    failure_count: int
    success_count: int
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


class CircuitBreaker:
    """Circuit breaker implementation for Phoenix automation.
    
    Features:
    - Automatic failure counting
    - Circuit opening on threshold breach
    - Automatic recovery with timeout
    - Half-open mode for trial recovery
    - Comprehensive event logging
    - Metrics tracking
    """
    
    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_success_time: Optional[float] = None
        self.half_open_calls = 0
        
        self.events: List[CircuitEvent] = []
        self._lock = threading.Lock()
        
        logger.info(
            "Circuit Breaker initialized: failure_threshold=%d, success_threshold=%d, "
            "timeout=%dms, half_open_max_calls=%d",
            self.config.failure_threshold, self.config.success_threshold,
            self.config.timeout_ms, self.config.half_open_max_calls
        )
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result if allowed, raises exception if circuit is open
            
        Raises:
            CircuitOpenError: If circuit is open and blocking requests
        """
        with self._lock:
            # Check if circuit is open and timeout has elapsed
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    error_msg = (
                        f"Circuit breaker is OPEN blocking request. "
                        f"Failures: {self.failure_count}, Timeout: {self.config.timeout_ms}ms"
                    )
                    logger.error(error_msg)
                    raise CircuitOpenError(error_msg)
            
            # Check if in half-open mode and limit reached
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.config.half_open_max_calls:
                    self._transition_to_open()
                    error_msg = (
                        f"Circuit breaker opened after half-open limit "
                        f"(calls: {self.half_open_calls}, max: {self.config.half_open_max_calls})"
                    )
                    logger.error(error_msg)
                    raise CircuitOpenError(error_msg)
        
        # Execute the function
        try:
            result = func(*args, **kwargs)
            
            # Success - update metrics
            with self._lock:
                self._record_success()
            
            return result
            
        except Exception as e:
            # Failure - update metrics
            with self._lock:
                self._record_failure(str(e))
            
            # Re-raise the exception
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt reset from OPEN to HALF_OPEN."""
        if self.last_failure_time is None:
            return False
        
        elapsed_ms = (time.time() - self.last_failure_time) * 1000
        return elapsed_ms >= self.config.timeout_ms
    
    def _transition_to_half_open(self) -> None:
        """Transition circuit from OPEN to HALF_OPEN."""
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        self.success_count = 0
        
        event = CircuitEvent(
            timestamp=time.time(),
            state=self.state,
            failure_count=self.failure_count,
            success_count=self.success_count,
            message="Circuit breaker transitioned to HALF_OPEN",
            details={"timeout_elapsed_ms": (time.time() - self.last_failure_time) * 1000}
        )
        self.events.append(event)
        
        logger.info(
            "Circuit Breaker: OPEN -> HALF_OPEN (failures: %d, timeout elapsed: %.0fms)",
            self.failure_count, (time.time() - self.last_failure_time) * 1000
        )
    
    def _transition_to_open(self) -> None:
        """Transition circuit to OPEN state."""
        self.state = CircuitState.OPEN
        self.last_failure_time = time.time()
        
        event = CircuitEvent(
            timestamp=time.time(),
            state=self.state,
            failure_count=self.failure_count,
            success_count=self.success_count,
            message="Circuit breaker transitioned to OPEN",
            details={"half_open_calls": self.half_open_calls}
        )
        self.events.append(event)
        
        logger.error(
            "Circuit Breaker: HALF_OPEN -> OPEN (failures: %d, half_open_calls: %d)",
            self.failure_count, self.half_open_calls
        )
    
    def _transition_to_closed(self) -> None:
        """Transition circuit to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        
        event = CircuitEvent(
            timestamp=time.time(),
            state=self.state,
            failure_count=self.failure_count,
            success_count=self.success_count,
            message="Circuit breaker transitioned to CLOSED",
            details={}
        )
        self.events.append(event)
        
        logger.info("Circuit Breaker: OPEN/HALF_OPEN -> CLOSED (circuit fully recovered)")
    
    def _record_success(self) -> None:
        """Record a successful operation."""
        self.success_count += 1
        self.last_success_time = time.time()
        
        # In half-open mode, successes count toward closing the circuit
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1
            
            if self.success_count >= self.config.success_threshold:
                self._transition_to_closed()
        
        # Reset failure count on success
        if self.state == CircuitState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)
        
        logger.debug(
            "Circuit Breaker: Success recorded (state: %s, failures: %d, successes: %d)",
            self.state.value, self.failure_count, self.success_count
        )
    
    def _record_failure(self, error_message: str) -> None:
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        # Check if threshold reached
        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self._transition_to_open()
        elif self.state == CircuitState.HALF_OPEN:
            self._transition_to_open()
        
        event = CircuitEvent(
            timestamp=time.time(),
            state=self.state,
            failure_count=self.failure_count,
            success_count=self.success_count,
            message=f"Failure recorded: {error_message}",
            details={"error_message": error_message}
        )
        self.events.append(event)
        
        logger.warning(
            "Circuit Breaker: Failure recorded (state: %s, failures: %d, error: %s)",
            self.state.value, self.failure_count, error_message
        )
    
    def get_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        with self._lock:
            return self.state
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics."""
        with self._lock:
            return {
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "half_open_calls": self.half_open_calls,
                "last_failure_time": self.last_failure_time,
                "last_success_time": self.last_success_time,
                "total_events": len(self.events),
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "success_threshold": self.config.success_threshold,
                    "timeout_ms": self.config.timeout_ms,
                    "half_open_max_calls": self.config.half_open_max_calls,
                }
            }
    
    def get_events(self) -> List[CircuitEvent]:
        """Get circuit breaker event history."""
        with self._lock:
            return self.events.copy()
    
    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        with self._lock:
            self._transition_to_closed()
            logger.info("Circuit Breaker: Manual reset performed")


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open and blocking requests."""
    pass