"""CLI entrypoint for the draw stream application."""

from __future__ import annotations

import asyncio
import signal

from .app import DrawStreamApp


async def main() -> None:
    app = DrawStreamApp()
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:  # pragma: no cover - Windows compatibility
            signal.signal(sig, lambda *_: stop_event.set())

    await app.start()
    try:
        await stop_event.wait()
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())

