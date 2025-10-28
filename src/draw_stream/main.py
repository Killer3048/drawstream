"""CLI entrypoint for the draw stream application."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import warnings

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("DIFFUSERS_NO_DEPRECATION_WARNING", "1")

warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API.*",
    category=UserWarning,
)
warnings.filterwarnings(
    "ignore",
    message="No LoRA keys associated.*",
    category=UserWarning,
)
warnings.filterwarnings(
    "ignore",
    message="`torch_dtype` is deprecated.*",
    category=UserWarning,
)
warnings.filterwarnings(
    "ignore",
    message="`torch_dtype` is deprecated.*",
    category=FutureWarning,
)

from .app import DrawStreamApp

warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API.*",
    category=UserWarning,
)
warnings.filterwarnings(
    "ignore",
    message="No LoRA keys associated.*",
    category=UserWarning,
)
warnings.filterwarnings(
    "ignore",
    message="`torch_dtype` is deprecated.*",
    category=UserWarning,
)
logging.getLogger("diffusers.loaders").setLevel(logging.ERROR)
logging.getLogger("diffusers").setLevel(logging.ERROR)


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

    app.register_shutdown_callback(stop_event.set)

    await app.start()
    try:
        await stop_event.wait()
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
