"""Command-line client for interacting with a running Draw Stream server."""

from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal, InvalidOperation
from typing import Any, Dict

import httpx

DEFAULT_HOST = os.environ.get("DRAWSTREAM_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("DRAWSTREAM_PORT", "8080"))
DEFAULT_TIMEOUT = float(os.environ.get("DRAWSTREAM_TIMEOUT", "10.0"))


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    base_url = _resolve_base_url(args.host, args.port)
    timeout = args.timeout

    if args.command in {"da", "donate"}:
        mode = "da" if args.command == "da" else "manual"
        try:
            payload = _build_donation_payload(
                mode=mode,
                amount_raw=args.amount,
                message_parts=args.message,
                donor=args.donor,
                currency=args.currency,
            )
        except ValueError as exc:
            parser.error(str(exc))
        return _post_json(
            f"{base_url}/commands/donate",
            payload,
            timeout,
            success_message="Donation enqueued.",
        )

    if args.command == "stop":
        return _post_json(
            f"{base_url}/control/shutdown",
            {},
            timeout,
            success_message="Shutdown requested.",
        )

    if args.command == "queue":
        return _show_queue(base_url, timeout)

    parser.error("Unknown command")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="drawstream",
        description="Control the Draw Stream server from any terminal.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Control API host (default: %(default)s)")
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Control API port (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="HTTP timeout in seconds (default: %(default)s)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    donate_parser = subparsers.add_parser("donate", help="Queue a manual donation")
    donate_parser.add_argument("amount", help="Donation amount (number)")
    donate_parser.add_argument("message", nargs=argparse.REMAINDER, help="Donation message")
    donate_parser.add_argument("--donor", help="Override donor display name (default: random)")
    donate_parser.add_argument("--currency", help="Override currency code")

    da_parser = subparsers.add_parser("da", help="Simulate DonationAlerts donation")
    da_parser.add_argument("amount", help="Donation amount (number)")
    da_parser.add_argument("message", nargs=argparse.REMAINDER, help="Donation message")
    da_parser.add_argument("--donor", help="Explicit donor name (default: random)")
    da_parser.add_argument("--currency", help="Override currency code")

    subparsers.add_parser("stop", help="Request graceful shutdown")
    subparsers.add_parser("queue", help="Print current queue snapshot")

    return parser


def _resolve_base_url(host: str, port: int) -> str:
    if host.startswith("http://") or host.startswith("https://"):
        return host.rstrip("/")
    return f"http://{host}:{port}"


def _build_donation_payload(
    *,
    mode: str,
    amount_raw: str,
    message_parts: list[str],
    donor: str | None,
    currency: str | None,
) -> Dict[str, Any]:
    try:
        amount = Decimal(amount_raw)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid amount '{amount_raw}': {exc}") from exc
    if amount <= 0:
        raise ValueError("Amount must be positive")
    message = " ".join(part for part in message_parts).strip()
    if not message:
        raise ValueError("Message cannot be empty")

    payload: Dict[str, Any] = {
        "mode": mode,
        "amount": str(amount),
        "message": message,
    }
    if donor:
        payload["donor"] = donor
    if currency:
        payload["currency"] = currency
    return payload


def _post_json(url: str, payload: Dict[str, Any], timeout: float, success_message: str) -> int:
    try:
        response = httpx.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
    except httpx.RequestError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        print(f"Server responded with error {exc.response.status_code}: {detail}", file=sys.stderr)
        return 1

    print(success_message)
    return 0


def _show_queue(base_url: str, timeout: float) -> int:
    try:
        response = httpx.get(f"{base_url}/queue", timeout=timeout)
        response.raise_for_status()
    except httpx.RequestError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1
    except httpx.HTTPStatusError as exc:
        print(f"Server responded with error {exc.response.status_code}: {exc.response.text}", file=sys.stderr)
        return 1

    payload = response.json()
    if not isinstance(payload, dict):
        print("Unexpected response payload", file=sys.stderr)
        return 1

    active = payload.get("active")
    queue_size = payload.get("queue_size")
    preview = payload.get("preview", [])

    print("Active task:")
    if active:
        print(f"  Donor: {active.get('donor')}")
        print(f"  Amount: {active.get('amount')} {active.get('currency')}")
        print(f"  Message: {active.get('message')}")
    else:
        print("  None")

    print(f"\nQueue size: {queue_size}")
    if preview:
        print("Preview:")
        for idx, task in enumerate(preview, start=1):
            donor = task.get("donor")
            amount = task.get("amount")
            currency = task.get("currency")
            message = task.get("message")
            print(f"  {idx}. {donor} – {amount} {currency}")
            if message:
                print(f"     {message}")
    else:
        print("Preview: empty")

    return 0


if __name__ == "__main__":
    sys.exit(main())
