"""CLI entrypoint for the draw stream application."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
import sys
from decimal import Decimal, InvalidOperation
import re
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

    await app.start()
    console_task = asyncio.create_task(_console_loop(app, stop_event), name="console-input")
    try:
        await stop_event.wait()
    finally:
        console_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await console_task
        await app.stop()


async def _console_loop(app: DrawStreamApp, stop_event: asyncio.Event) -> None:
    print(
        "Console commands:\n"
        "  donate <amount> <message>    # enqueue manual test donation\n"
        "  da <amount> <message>         # simulate Donation Alerts event\n"
        "  exit|quit                     # stop the stream\n",
        flush=True,
    )
    while not stop_event.is_set():
        try:
            line = await asyncio.to_thread(sys.stdin.readline)
        except Exception:  # pragma: no cover - defensive
            break
        if not line:
            break
        line = _sanitize_input(line)
        if not line:
            continue
        cmd, remainder = _extract_command(line)
        if not cmd:
            print("Unknown command. Use 'donate <amount> <message>' or 'quit'.", flush=True)
            continue
        if cmd in {"exit", "quit"}:
            stop_event.set()
            break
        da_mode = cmd in {"da", "donate-da"}
        await _handle_donate_command(app, remainder, da_mode=da_mode)


ANSI_PATTERN = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
COMMAND_PATTERN = re.compile(r"^(donate|da|donate-da|exit|quit)\b", re.IGNORECASE)


def _sanitize_input(line: str) -> str:
    cleaned = ANSI_PATTERN.sub("", line)
    return cleaned.replace("\r", "")


def _extract_command(text: str) -> tuple[str | None, str]:
    lines = [seg.strip() for seg in text.split("\n") if seg.strip()]
    if not lines:
        return None, ""
    candidate = lines[-1]
    match = COMMAND_PATTERN.match(candidate)
    if not match:
        return None, candidate
    cmd = match.group(1).lower()
    remainder = candidate[match.end():].strip()
    return cmd, remainder


async def _handle_donate_command(app: DrawStreamApp, remainder: str, da_mode: bool = False) -> None:
    import shlex

    if not remainder:
        print("Usage: donate <amount> <message>", flush=True)
        return
    try:
        parts = shlex.split(remainder)
    except ValueError as exc:
        print(f"Failed to parse command: {exc}", flush=True)
        return
    if len(parts) < 2:
        print("Usage: donate <amount> <message>", flush=True)
        return
    amount_raw, *message_parts = parts
    try:
        amount = Decimal(amount_raw)
    except (InvalidOperation, ValueError):
        print("Amount must be a number", flush=True)
        return
    message = " ".join(message_parts).strip()
    if not message:
        print("Message cannot be empty", flush=True)
        return
    donor = "DonationAlerts(Test)" if da_mode else "Console"
    currency = app._settings.display_currency  # type: ignore[attr-defined]
    await app.enqueue_manual_donation(message=message, amount=amount, donor=donor, currency=currency)
    prefix = "Simulated DA" if da_mode else "Enqueued"
    print(f"{prefix} donation: {amount} {currency} – {message}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
