"""NSFW gatekeeper heuristics for donation messages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Pattern

from .models import DonationEvent


DEFAULT_RULES = (
    r"(?i)\b(?:nsfw|porn|porno|xxx|sex|sexual|nude|naked|strip|fetish)\b",
    r"(?i)\b(?:эроти\w*|секс|порно|голый|голая|голыми|груди|сиськ\w*|член|пенис|вагин\w*|камшот)\b",
    r"(?i)\b(?:18\+|adult only|onlyfans|lewd)\b",
    r"(?i)\b(?:fuck|fucking|cunt|dick|cock|boobs|tits|pussy|vagina|stripper|striptease)\b",
    r"(?i)\b(?:хуй|хуи|пизд\w*|жоп\w*|анальн\w*|оральн\w*|минет|кунилинг\w*|куни|оральный|оральная|орально)\b",
)


@dataclass(slots=True)
class GatekeeperDecision:
    """Result of gatekeeper evaluation."""

    nsfw: bool
    rule: str | None = None


class Gatekeeper:
    """Simple regex-based NSFW detector."""

    def __init__(self, rules: Iterable[str] | None = None) -> None:
        self._patterns: tuple[Pattern[str], ...] = tuple(re.compile(rule) for rule in (rules or DEFAULT_RULES))

    def evaluate(self, event: DonationEvent) -> GatekeeperDecision:
        """Return whether the donation message is considered NSFW."""

        for pattern in self._patterns:
            if pattern.search(event.message):
                return GatekeeperDecision(nsfw=True, rule=pattern.pattern)
        return GatekeeperDecision(nsfw=False)
