"""
TITAN POS - Rate Limiting Middleware

Protects the Gateway from overload by limiting request rates per IP/terminal.
"""

import threading
import time
from typing import Dict, Tuple, Optional
from datetime import datetime
from collections import defaultdict

try:
    from fastapi import Request, HTTPException
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse
except ImportError:
    BaseHTTPMiddleware = object
    Request = None

class RateLimiter:
    """
    Simple in-memory rate limiter using sliding window.
    
    Features:
    - Per-IP rate limiting
    - Per-terminal rate limiting
    - Configurable limits per endpoint type
    - Automatic cleanup of old entries
    """
    
    def __init__(self, 
                 requests_per_minute: int = 60,
                 burst_limit: int = 20,
                 cleanup_interval: int = 300):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Max requests per minute per IP
            burst_limit: Max requests in 5 second window
            cleanup_interval: Seconds between cleanup of old entries
        """
        self.rpm_limit = requests_per_minute
        self.burst_limit = burst_limit
        self.cleanup_interval = cleanup_interval

        # Store: {key: [(timestamp, count), ...]} - thread-safe
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = threading.Lock()
        self._last_cleanup = time.time()

        # Endpoint-specific limits
        self._endpoint_limits = {
            "/api/v1/heartbeat": 120,      # Heartbeats allowed more frequently
            "/api/v1/logs": 30,            # Logs less frequently
            "/api/sync": 60,               # Sync normal rate
            "/health": 300,                # Health checks very permissive
        }
    
    def _cleanup(self):
        """Remove old entries to prevent memory growth."""
        now = time.time()
        if now - self._last_cleanup < self.cleanup_interval:
            return

        cutoff = now - 60  # Remove entries older than 1 minute
        with self._lock:
            for key in list(self._requests.keys()):
                self._requests[key] = [
                    (ts, count) for ts, count in self._requests[key]
                    if ts > cutoff
                ]
                if not self._requests[key]:
                    del self._requests[key]

            self._last_cleanup = now
    
    def _get_limit(self, path: str) -> int:
        """Get rate limit for specific endpoint."""
        for endpoint, limit in self._endpoint_limits.items():
            if path.startswith(endpoint):
                return limit
        return self.rpm_limit
    
    def is_allowed(self, key: str, path: str = "") -> Tuple[bool, Optional[int]]:
        """
        Check if request is allowed.

        Args:
            key: Identifier (IP address or terminal ID)
            path: Request path for endpoint-specific limits

        Returns:
            Tuple of (allowed: bool, retry_after: Optional[int])
        """
        self._cleanup()

        now = time.time()
        limit = self._get_limit(path)

        with self._lock:
            # Get requests in last minute
            recent = [ts for ts, _ in self._requests[key] if ts > now - 60]

            # Check burst (last 5 seconds)
            burst = len([ts for ts in recent if ts > now - 5])
            if burst >= self.burst_limit:
                return False, 5

            # Check rate limit
            if len(recent) >= limit:
                oldest = min(recent) if recent else now
                retry_after = int(60 - (now - oldest)) + 1
                return False, max(1, retry_after)

            # Record this request
            self._requests[key].append((now, 1))

        return True, None
    
    def get_stats(self) -> Dict:
        """Get rate limiter statistics."""
        with self._lock:
            return {
                "tracked_keys": len(self._requests),
                "total_entries": sum(len(v) for v in self._requests.values()),
                "last_cleanup": datetime.fromtimestamp(self._last_cleanup).isoformat()
            }

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.
    
    Usage:
        app.add_middleware(RateLimitMiddleware, limiter=RateLimiter())
    """
    
    def __init__(self, app, limiter: RateLimiter = None, enabled: bool = True):
        super().__init__(app)
        self.limiter = limiter or RateLimiter()
        self.enabled = enabled
        
        # Paths to skip rate limiting
        self._skip_paths = {"/health", "/", "/docs", "/openapi.json", "/favicon.ico"}
    
    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)
        
        path = request.url.path
        
        # Skip certain paths
        if path in self._skip_paths:
            return await call_next(request)
        
        # Get client identifier
        client_ip = request.client.host if request.client else "unknown"
        
        # Also check terminal ID from header if present
        terminal_key = request.headers.get("X-Terminal-ID", client_ip)
        
        # Check rate limit
        allowed, retry_after = self.limiter.is_allowed(terminal_key, path)
        
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": "Rate limit exceeded. Please slow down.",
                    "retry_after": retry_after
                },
                headers={"Retry-After": str(retry_after)}
            )
        
        return await call_next(request)

def create_rate_limiter(config: dict = None) -> RateLimiter:
    """Factory function to create rate limiter from config."""
    config = config or {}
    return RateLimiter(
        requests_per_minute=config.get("rate_limit_rpm", 60),
        burst_limit=config.get("rate_limit_burst", 20),
        cleanup_interval=config.get("rate_limit_cleanup", 300)
    )
