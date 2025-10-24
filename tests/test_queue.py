import asyncio

import pytest

from draw_stream.models import DonationEvent, RenderTask, RenderTaskType
from draw_stream.queue import QueueManager


def _make_task(idx: int) -> RenderTask:
    event = DonationEvent(
        id=str(idx),
        donor=f"Donor {idx}",
        message=f"Message {idx}",
        amount="1.0",
        currency="USD",
        timestamp="2024-01-01T00:00:00+00:00",
    )
    return RenderTask(event=event, content_type=RenderTaskType.TEXT, fallback_text="Test")


@pytest.mark.asyncio
async def test_queue_preserves_order() -> None:
    queue = QueueManager(max_size=10)
    tasks = [_make_task(i) for i in range(3)]
    for task in tasks:
        await queue.enqueue(task)

    out1 = await queue.dequeue()
    out2 = await queue.dequeue()
    assert out1.event.id == "0"
    assert out2.event.id == "1"
    queue.task_done()
    queue.task_done()


@pytest.mark.asyncio
async def test_queue_preview() -> None:
    queue = QueueManager(max_size=10)
    for i in range(5):
        await queue.enqueue(_make_task(i))

    preview = await queue.preview(limit=3)
    assert [task.event.id for task in preview] == ["0", "1", "2"]

    await queue.dequeue()
    queue.task_done()
    preview = await queue.preview(limit=2)
    assert [task.event.id for task in preview] == ["1", "2"]

