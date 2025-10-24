import asyncio
import json

import httpx
import pytest

from draw_stream.llm import LLMOrchestrator, LLMPlanError
from draw_stream.models import DonationEvent

from .utils import make_settings


def make_event(message: str = "Draw a flower") -> DonationEvent:
    return DonationEvent(
        id="don-1",
        donor="Tester",
        message=message,
        amount="3.0",
        currency="USD",
        timestamp="2024-01-01T00:00:00+00:00",
    )


@pytest.mark.asyncio
async def test_llm_orchestrator_success() -> None:
    settings = make_settings()

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "version": "1.0",
                                "canvas": {"w": 96, "h": 96, "bg": "#202020"},
                                "caption": "All for you",
                                "steps": [
                                    {
                                        "op": "pixels",
                                        "points": [[10, 10]],
                                        "color": "#FFFFFF",
                                    }
                                ],
                            }
                        )
                    }
                }
            ]
        }
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        orchestrator = LLMOrchestrator(settings=settings, client=client)
        plan = await orchestrator.generate_plan(make_event())

    assert plan.caption == "All for you"
    assert plan.steps and plan.steps[0].op == "pixels"


@pytest.mark.asyncio
async def test_llm_orchestrator_failure_after_retries() -> None:
    settings = make_settings(LLM_RETRY_ATTEMPTS=1)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "backend unavailable"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        orchestrator = LLMOrchestrator(settings=settings, client=client)
        with pytest.raises(LLMPlanError):
            await orchestrator.generate_plan(make_event())

