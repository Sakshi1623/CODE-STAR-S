"""Server-Sent Events (SSE) broadcaster with thread-safe fan-out, heartbeats, and bounded queues."""

import asyncio
import json
import logging
import threading
from typing import Any, AsyncGenerator
from fastapi import Request

logger = logging.getLogger(__name__)


class SSEBroadcaster:
    """Manages thread-safe fan-out of telemetry events to multiple SSE client connections.

    Key guarantees:
    - Bounded per-client asyncio.Queue to prevent slow-consumer memory leaks (drops oldest on overflow)
    - Thread-safe event dispatch from worker/background threads via loop.call_soon_threadsafe
    - Periodic heartbeat comments to prevent idle connection dropouts
    - Automatic cleanup of disconnected clients
    """

    def __init__(self, queue_maxsize: int = 100, heartbeat_interval: float = 15.0):
        self.queue_maxsize = queue_maxsize
        self.heartbeat_interval = heartbeat_interval
        self._subscribers: set[asyncio.Queue] = set()
        self._sub_lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def subscriber_count(self) -> int:
        """Number of currently active SSE subscriber connections."""
        with self._sub_lock:
            return len(self._subscribers)

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Assign the active asyncio event loop for thread-safe cross-thread dispatch."""
        self._loop = loop

    def on_shield_event(self, event_name: str, event_data: dict[str, Any]) -> None:
        """Callback to hook into Shield.subscribe(). Dispatches safely to all subscribers."""
        with self._sub_lock:
            if not self._subscribers:
                return

        payload = {
            "event": event_name,
            "data": event_data,
        }

        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if self._loop is not None and not self._loop.is_closed() and self._loop.is_running():
            if current_loop is self._loop:
                # Same loop thread, fan out immediately
                self._fanout_sync(payload)
            else:
                try:
                    self._loop.call_soon_threadsafe(self._fanout_sync, payload)
                except RuntimeError:
                    self._fanout_sync(payload)
        else:
            self._fanout_sync(payload)

    def _fanout_sync(self, payload: dict[str, Any]) -> None:
        """Deliver payload to all subscriber queues, dropping oldest if full (bounded overflow)."""
        with self._sub_lock:
            subs = list(self._subscribers)

        for q in subs:
            try:
                if q.full():
                    try:
                        q.get_nowait()
                    except (asyncio.QueueEmpty, Exception):
                        pass
                q.put_nowait(payload)
            except Exception as e:
                logger.warning(f"Failed to deliver event to SSE subscriber queue: {e}")

    async def connect(self) -> asyncio.Queue:
        """Register a new client connection queue."""
        try:
            loop = asyncio.get_running_loop()
            if self._loop is None or self._loop.is_closed():
                self._loop = loop
        except RuntimeError:
            pass

        q: asyncio.Queue = asyncio.Queue(maxsize=self.queue_maxsize)
        with self._sub_lock:
            self._subscribers.add(q)
        return q

    async def disconnect(self, q: asyncio.Queue) -> None:
        """Unregister a client connection queue and free resources."""
        with self._sub_lock:
            self._subscribers.discard(q)

    async def event_generator(
        self,
        q: asyncio.Queue,
        request: Request | None = None,
        limit: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """Async generator yielding formatted SSE frames and periodic heartbeats."""
        delivered = 0
        try:
            while True:
                if request is not None and await request.is_disconnected():
                    break
                if limit is not None and delivered >= limit:
                    break

                try:
                    item = await asyncio.wait_for(q.get(), timeout=self.heartbeat_interval)
                    delivered += 1
                    event_name = item.get("event", "message")
                    data_json = json.dumps(item.get("data", {}))
                    yield f"event: {event_name}\ndata: {data_json}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    if limit is not None:
                        delivered += 1
        except asyncio.CancelledError:
            pass
        finally:
            await self.disconnect(q)
