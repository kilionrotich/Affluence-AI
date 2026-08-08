"""Retry & Fallback Utilities

Provides retry logic with exponential backoff, circuit breaker patterns,
and graceful degradation strategies for API failures.
"""
import time
import functools
import logging
from typing import Callable, Optional, Type, Tuple

logger = logging.getLogger(__name__)


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None,
):
    """Decorator that retries a function with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (including first)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        backoff_factor: Multiplier for each retry
        exceptions: Tuple of exception types to catch
        on_retry: Callback function called on each retry (attempt, exception)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        raise

                    delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    if on_retry:
                        on_retry(attempt, e)

                    time.sleep(delay)

            # Should not reach here
            raise last_exception  # type: ignore
        return wrapper
    return decorator


class CircuitBreaker:
    """Circuit breaker pattern to prevent repeated calls to failing services.

    States: CLOSED (normal) -> OPEN (failing) -> HALF_OPEN (testing)
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_attempts: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_attempts = half_open_max_attempts

        self.failure_count = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = None
        self.half_open_attempts = 0

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == "OPEN":
                if self.last_failure_time and (
                    time.time() - self.last_failure_time >= self.recovery_timeout
                ):
                    self.state = "HALF_OPEN"
                    self.half_open_attempts = 0
                    logger.info(f"Circuit breaker {func.__name__}: OPEN -> HALF_OPEN")
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker is OPEN for {func.__name__}. "
                        f"Retry in {self.recovery_timeout - (time.time() - self.last_failure_time):.0f}s"
                    )

            try:
                result = func(*args, **kwargs)
                # Success - reset
                if self.state in ("HALF_OPEN", "CLOSED"):
                    self.failure_count = 0
                    self.half_open_attempts = 0
                    if self.state == "HALF_OPEN":
                        self.state = "CLOSED"
                        logger.info(f"Circuit breaker {func.__name__}: HALF_OPEN -> CLOSED (recovered)")
                return result
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()

                if self.state == "HALF_OPEN":
                    self.half_open_attempts += 1
                    if self.half_open_attempts >= self.half_open_max_attempts:
                        self.state = "OPEN"
                        logger.warning(f"Circuit breaker {func.__name__}: HALF_OPEN -> OPEN")
                elif self.failure_count >= self.failure_threshold:
                    self.state = "OPEN"
                    logger.warning(f"Circuit breaker {func.__name__}: CLOSED -> OPEN")

                raise e

        return wrapper


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and request cannot be processed."""
    pass


class FallbackStrategy:
    """Provides fallback strategies for graceful degradation."""

    @staticmethod
    def fallback_to_cache(func: Callable, cache_key: str, cache_ttl: int = 300):
        """Fallback to cached result if primary function fails."""
        import pickle

        cache = {}

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                cache[cache_key] = (result, time.time())
                return result
            except Exception as e:
                if cache_key in cache:
                    cached_result, cached_time = cache[cache_key]
                    if time.time() - cached_time < cache_ttl:
                        logger.warning(f"Using cached result for {func.__name__} due to: {e}")
                        return cached_result
                raise
        return wrapper

    @staticmethod
    def fallback_to_default(default_value):
        """Return default value if function fails."""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Using default value for {func.__name__} due to: {e}")
                    return default_value() if callable(default_value) else default_value
            return wrapper
        return decorator


def safe_execute(func: Callable, default_return=None, log_error: bool = True):
    """Safely execute a function, returning default on failure."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if log_error:
                logger.error(f"Safe execute failed for {func.__name__}: {e}")
            return default_return() if callable(default_return) else default_return
    return wrapper

