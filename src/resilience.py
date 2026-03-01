"""
Resilience Layer for Economic Intelligence Agent
TTL Cache, Rate Limiter, Circuit Breaker, Retry, and ResilientFetcher facade
"""

import time
import random
import hashlib
import logging
import asyncio
import aiohttp
from collections import OrderedDict
from enum import Enum
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── TTL Cache ────────────────────────────────────────────────────────

class TTLCache:
    """LRU cache with per-key TTL, OrderedDict-backed, with stats tracking"""

    def __init__(self, max_size: int = 256, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._store: OrderedDict = OrderedDict()  # key -> (value, expiry)
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            value, expiry = self._store[key]
            if time.time() < expiry:
                self._store.move_to_end(key)
                self.hits += 1
                return value
            else:
                del self._store[key]
        self.misses += 1
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if key in self._store:
            del self._store[key]
        elif len(self._store) >= self.max_size:
            self._evict()
        self._store[key] = (value, time.time() + (ttl or self.default_ttl))

    def _evict(self) -> None:
        """Evict expired entries first, then oldest by insertion order"""
        now = time.time()
        expired = [k for k, (_, exp) in self._store.items() if now >= exp]
        for k in expired:
            del self._store[k]
        # If still full, pop oldest
        while len(self._store) >= self.max_size:
            self._store.popitem(last=False)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    @property
    def stats(self) -> Dict:
        total = self.hits + self.misses
        return {
            "size": len(self._store),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{self.hits / total * 100:.1f}%" if total > 0 else "0%",
        }


# ── Rate Limiter (Token Bucket) ─────────────────────────────────────

class RateLimiter:
    """Token bucket rate limiter with time-based refill

    Avoids TOCTOU by refilling in both canRequest() and consume().
    """

    def __init__(self, max_tokens: int, refill_period: float, name: str = "default"):
        self.max_tokens = max_tokens
        self.refill_period = refill_period  # seconds
        self.name = name
        self.tokens = float(max_tokens)
        self.last_refill = time.time()

    def _refill(self) -> None:
        now = time.time()
        elapsed = now - self.last_refill
        refill_amount = elapsed * (self.max_tokens / self.refill_period)
        self.tokens = min(self.max_tokens, self.tokens + refill_amount)
        self.last_refill = now

    def can_request(self) -> bool:
        self._refill()
        return self.tokens >= 1.0

    def consume(self) -> bool:
        """Try to consume a token. Returns True if allowed."""
        self._refill()
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

    async def wait_for_token(self) -> None:
        """Wait until a token is available"""
        while not self.consume():
            wait_time = self.refill_period / self.max_tokens
            logger.debug(f"Rate limit [{self.name}]: waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)


# ── Circuit Breaker ──────────────────────────────────────────────────

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker with per-API isolation. Only 1 probe in half-open state."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0, name: str = "default"):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self._half_open_probe_active = False

    @property
    def is_available(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self._half_open_probe_active = False
                logger.info(f"Circuit [{self.name}]: OPEN -> HALF_OPEN")
                return True
            return False
        # HALF_OPEN: only allow 1 probe
        if self.state == CircuitState.HALF_OPEN:
            if not self._half_open_probe_active:
                self._half_open_probe_active = True
                return True
            return False
        return False

    def record_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            logger.info(f"Circuit [{self.name}]: HALF_OPEN -> CLOSED (probe success)")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self._half_open_probe_active = False

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self._half_open_probe_active = False
            logger.warning(f"Circuit [{self.name}]: HALF_OPEN -> OPEN (probe failed)")
            return

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit [{self.name}]: CLOSED -> OPEN (failures={self.failure_count})")


# ── Retry with Backoff ───────────────────────────────────────────────

class RetryWithBackoff:
    """Exponential backoff with jitter"""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def execute(self, coro_factory: Callable, *args, **kwargs) -> Any:
        """Execute with retries. coro_factory is an async callable."""
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                return await coro_factory(*args, **kwargs)
            except Exception as e:
                last_exc = e
                if attempt < self.max_retries:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    jitter = random.uniform(0, delay * 0.3)
                    wait = delay + jitter
                    logger.debug(f"Retry {attempt + 1}/{self.max_retries} after {wait:.1f}s: {e}")
                    await asyncio.sleep(wait)
        raise last_exc


# ── Resilient Fetcher (Facade) ───────────────────────────────────────

class ResilientFetcher:
    """Facade combining cache, rate limit, circuit breaker, retry, and HTTP fetch.

    Usage:
        fetcher = ResilientFetcher()
        data = await fetcher.fetch("https://api.example.com/data", cache_ttl=300)
    """

    def __init__(
        self,
        cache: Optional[TTLCache] = None,
        rate_limiters: Optional[Dict[str, RateLimiter]] = None,
        circuit_breakers: Optional[Dict[str, CircuitBreaker]] = None,
        retry: Optional[RetryWithBackoff] = None,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self.cache = cache or TTLCache()
        self.rate_limiters = rate_limiters or {}
        self.circuit_breakers = circuit_breakers or {}
        self.retry = retry or RetryWithBackoff()
        self._session = session
        self._owned_session = False

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owned_session = True
        return self._session

    async def close(self) -> None:
        if self._owned_session and self._session and not self._session.closed:
            await self._session.close()

    def _cache_key(self, url: str, params: Optional[Dict] = None) -> str:
        raw = url + (str(sorted(params.items())) if params else "")
        return hashlib.md5(raw.encode()).hexdigest()

    def _get_domain(self, url: str) -> str:
        """Extract domain for rate limiter / circuit breaker lookup"""
        from urllib.parse import urlparse
        return urlparse(url).netloc

    async def fetch(
        self,
        url: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        cache_ttl: Optional[int] = 300,
        timeout: float = 30.0,
    ) -> Dict:
        """Fetch URL through the full resilience stack."""
        domain = self._get_domain(url)

        # 1. Cache check
        if cache_ttl and cache_ttl > 0:
            cache_key = self._cache_key(url, params)
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache HIT: {url}")
                return cached

        # 2. Rate limit
        limiter = self.rate_limiters.get(domain)
        if limiter:
            await limiter.wait_for_token()

        # 3. Circuit breaker
        breaker = self.circuit_breakers.get(domain)
        if breaker and not breaker.is_available:
            logger.warning(f"Circuit OPEN for {domain}, skipping request")
            return {}

        # 4. Retry + HTTP fetch
        async def _do_fetch():
            session = await self._get_session()
            client_timeout = aiohttp.ClientTimeout(total=timeout)
            async with session.get(url, params=params, headers=headers, timeout=client_timeout) as resp:
                if resp.status == 429:
                    raise Exception(f"Rate limited (429) from {domain}")
                if resp.status >= 500:
                    raise Exception(f"Server error ({resp.status}) from {domain}")
                if resp.status != 200:
                    logger.warning(f"HTTP {resp.status} from {url}")
                    return {}
                data = await resp.json()
                return data

        try:
            result = await self.retry.execute(_do_fetch)
            if breaker:
                breaker.record_success()
            # Cache result
            if cache_ttl and cache_ttl > 0 and result:
                self.cache.set(self._cache_key(url, params), result, ttl=cache_ttl)
            return result
        except Exception as e:
            if breaker:
                breaker.record_failure()
            logger.error(f"Fetch failed after retries: {url} — {e}")
            return {}


# ── Pre-configured rate limiters for known APIs ──────────────────────

def create_default_rate_limiters() -> Dict[str, RateLimiter]:
    """Create rate limiters tuned to free-tier API limits"""
    return {
        "www.alphavantage.co": RateLimiter(max_tokens=25, refill_period=86400, name="alpha_vantage"),  # 25/day
        "finnhub.io": RateLimiter(max_tokens=60, refill_period=60, name="finnhub"),  # 60/min
        "api.coingecko.com": RateLimiter(max_tokens=10, refill_period=60, name="coingecko"),  # ~10/min free
        "api.stlouisfed.org": RateLimiter(max_tokens=120, refill_period=60, name="fred"),  # 120/min
        "newsapi.org": RateLimiter(max_tokens=100, refill_period=86400, name="newsapi"),  # 100/day free
    }


def create_default_circuit_breakers() -> Dict[str, CircuitBreaker]:
    return {
        "www.alphavantage.co": CircuitBreaker(failure_threshold=3, recovery_timeout=120, name="alpha_vantage"),
        "finnhub.io": CircuitBreaker(failure_threshold=5, recovery_timeout=60, name="finnhub"),
        "api.coingecko.com": CircuitBreaker(failure_threshold=5, recovery_timeout=60, name="coingecko"),
        "api.stlouisfed.org": CircuitBreaker(failure_threshold=3, recovery_timeout=120, name="fred"),
        "newsapi.org": CircuitBreaker(failure_threshold=3, recovery_timeout=120, name="newsapi"),
    }
