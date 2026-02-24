"""
TITAN POS - Redis Event Bridge

Bridges the in-process EnhancedEventBus with Redis Streams for
inter-service event communication (Phase 4).

Usage:
    from modules.shared.redis_events import RedisEventBridge

    bridge = RedisEventBridge(redis_url="redis://localhost:6379/0")
    await bridge.connect()
    await bridge.publish(domain_event)
    await bridge.subscribe("sale.completed", handler)
"""

import os
import json
import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STREAM_PREFIX = "titan:events:"
CONSUMER_GROUP = "titan-pos"


class RedisEventBridge:
    """Bridges domain events between services via Redis Streams."""

    def __init__(self, redis_url: Optional[str] = None, service_name: str = "monolith"):
        self._redis_url = redis_url or REDIS_URL
        self._service_name = service_name
        self._redis = None
        self._handlers: Dict[str, List[Callable]] = {}
        self._consumer_tasks: List[asyncio.Task] = []
        self._running = False

    async def connect(self):
        """Connect to Redis."""
        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
            )
            await self._redis.ping()
            logger.info(f"Redis event bridge connected ({self._service_name})")
        except ImportError:
            logger.warning("redis package not installed — Redis event bridge disabled")
            self._redis = None
        except Exception as e:
            logger.warning(f"Redis connection failed: {e} — event bridge disabled")
            self._redis = None

    async def disconnect(self):
        """Disconnect from Redis and stop consumers."""
        self._running = False
        for task in self._consumer_tasks:
            task.cancel()
        self._consumer_tasks.clear()
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def publish(self, event) -> bool:
        """
        Publish a DomainEvent to a Redis Stream.

        Stream name: titan:events:{event_type}
        Example: titan:events:sale.completed
        """
        if not self._redis:
            return False

        stream_name = f"{STREAM_PREFIX}{event.event_type}"
        try:
            data = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "aggregate_type": event.aggregate_type,
                "aggregate_id": event.aggregate_id or "",
                "source_module": event.source_module,
                "timestamp": event.timestamp.isoformat(),
                "data": json.dumps(event.data, default=str),
            }
            if hasattr(event, "metadata") and event.metadata:
                data["metadata"] = json.dumps(event.metadata, default=str)

            msg_id = await self._redis.xadd(stream_name, data, maxlen=10000)
            logger.debug(f"Published {event.event_type} to {stream_name}: {msg_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish event to Redis: {e}")
            return False

    def subscribe(self, event_type: str, handler: Callable):
        """Register a handler for an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def start_consuming(self):
        """Start consuming events from Redis Streams for all subscribed event types."""
        if not self._redis or not self._handlers:
            return

        self._running = True

        for event_type in self._handlers:
            stream_name = f"{STREAM_PREFIX}{event_type}"
            consumer_name = f"{self._service_name}-{id(self)}"

            # Ensure consumer group exists
            try:
                await self._redis.xgroup_create(
                    stream_name, CONSUMER_GROUP, id="0", mkstream=True
                )
            except Exception:
                pass  # Group already exists

            task = asyncio.create_task(
                self._consume_stream(stream_name, event_type, consumer_name)
            )
            self._consumer_tasks.append(task)

        logger.info(
            f"Redis consumer started for {len(self._handlers)} event types "
            f"({self._service_name})"
        )

    async def _consume_stream(
        self, stream_name: str, event_type: str, consumer_name: str
    ):
        """Consume messages from a single Redis Stream."""
        while self._running:
            try:
                messages = await self._redis.xreadgroup(
                    groupname=CONSUMER_GROUP,
                    consumername=consumer_name,
                    streams={stream_name: ">"},
                    count=10,
                    block=5000,  # 5 second block
                )

                if not messages:
                    continue

                for stream, entries in messages:
                    for msg_id, data in entries:
                        await self._process_message(event_type, msg_id, data)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error consuming {stream_name}: {e}")
                await asyncio.sleep(1)

    async def _process_message(self, event_type: str, msg_id: str, data: dict):
        """Process a single message and acknowledge it."""
        handlers = self._handlers.get(event_type, [])
        event_data = json.loads(data.get("data", "{}"))

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event_data)
                else:
                    handler(event_data)
            except Exception as e:
                logger.error(
                    f"Handler error for {event_type} (msg {msg_id}): {e}"
                )

        # Acknowledge message
        stream_name = f"{STREAM_PREFIX}{event_type}"
        try:
            await self._redis.xack(stream_name, CONSUMER_GROUP, msg_id)
        except Exception as e:
            logger.error(f"Failed to ACK {msg_id}: {e}")


class RedisCache:
    """Simple async Redis cache wrapper (replaces SimpleCache for distributed use)."""

    def __init__(self, redis_url: Optional[str] = None, prefix: str = "titan:cache:"):
        self._redis_url = redis_url or REDIS_URL
        self._prefix = prefix
        self._redis = None

    async def connect(self):
        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
            await self._redis.ping()
        except Exception as e:
            logger.warning(f"Redis cache connection failed: {e}")
            self._redis = None

    async def get(self, key: str) -> Optional[Any]:
        if not self._redis:
            return None
        try:
            val = await self._redis.get(f"{self._prefix}{key}")
            return json.loads(val) if val else None
        except Exception:
            return None

    async def set(self, key: str, value: Any, ttl: int = 300):
        if not self._redis:
            return
        try:
            await self._redis.setex(
                f"{self._prefix}{key}", ttl, json.dumps(value, default=str)
            )
        except Exception as e:
            logger.warning(f"Redis cache set failed: {e}")

    async def delete(self, key: str):
        if not self._redis:
            return
        try:
            await self._redis.delete(f"{self._prefix}{key}")
        except Exception:
            pass

    async def disconnect(self):
        if self._redis:
            await self._redis.close()
