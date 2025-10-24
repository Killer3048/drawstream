"""Queue manager coordinating donation render tasks."""

from __future__ import annotations

import asyncio
from collections import deque
from typing import Deque, Iterable, Optional

from asyncio import QueueEmpty

from .models import RenderTask


class QueueManager:
    """FIFO queue with preview support backed by asyncio primitives."""

    def __init__(self, max_size: int, preview_size: int = 5) -> None:
        self._queue: asyncio.Queue[RenderTask] = asyncio.Queue(max_size)
        self._backing: Deque[RenderTask] = deque()
        self._preview_size = preview_size
        self._lock = asyncio.Lock()

    async def enqueue(self, task: RenderTask) -> None:
        """Put a task into the queue, blocking if at capacity."""

        await self._queue.put(task)
        async with self._lock:
            self._backing.append(task)

    async def dequeue(self) -> RenderTask:
        """Retrieve the next task in FIFO order."""

        task = await self._queue.get()
        async with self._lock:
            try:
                self._backing.remove(task)
            except ValueError:  # pragma: no cover - should not occur
                self._backing.clear()
        return task

    def task_done(self) -> None:
        """Signal completion of the most recently dequeued task."""

        self._queue.task_done()

    async def clear(self) -> None:
        """Drop all queued (non-active) tasks."""

        async with self._lock:
            self._backing.clear()
            while True:
                try:
                    self._queue.get_nowait()
                except QueueEmpty:
                    break
                else:
                    self._queue.task_done()

    async def drain(self) -> Iterable[RenderTask]:
        """Remove and return all queued tasks."""

        drained: list[RenderTask] = []
        async with self._lock:
            while True:
                try:
                    task = self._queue.get_nowait()
                except QueueEmpty:
                    break
                else:
                    drained.append(task)
                    self._queue.task_done()
            self._backing.clear()
        return drained

    async def preview(self, limit: Optional[int] = None) -> list[RenderTask]:
        """Return up to ``limit`` queued tasks (without removing)."""

        limit = limit or self._preview_size
        async with self._lock:
            return list(self._backing)[:limit]

    async def size(self) -> int:
        """Return current queue length."""

        async with self._lock:
            return len(self._backing)
