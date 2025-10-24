import pytest

from draw_stream.gatekeeper import Gatekeeper
from draw_stream.models import DonationEvent


def make_event(message: str) -> DonationEvent:
    return DonationEvent(
        id="1",
        donor="Tester",
        message=message,
        amount="5.00",
        currency="USD",
        timestamp="2024-01-01T00:00:00+00:00",
    )


def test_gatekeeper_blocks_nsfw_message() -> None:
    gatekeeper = Gatekeeper()
    event = make_event("please draw nsfw scene")
    decision = gatekeeper.evaluate(event)
    assert decision.nsfw is True


def test_gatekeeper_allows_wholesome_message() -> None:
    gatekeeper = Gatekeeper()
    event = make_event("Draw a happy cat, please")
    decision = gatekeeper.evaluate(event)
    assert decision.nsfw is False

