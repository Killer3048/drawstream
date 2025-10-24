"""Shared domain models for donations and render tasks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .canvas_dsl import CanvasDocument


class DonationEvent(BaseModel):
    """Normalized donation payload."""

    id: str = Field(..., description="Donation identifier supplied by Donation Alerts")
    donor: Optional[str] = Field(default=None, description="Display name of the donor")
    message: str = Field(default="", description="Raw donor message")
    amount: Decimal = Field(..., description="Donation amount")
    currency: str = Field(..., description="Currency code (ISO 4217)")
    timestamp: datetime = Field(..., description="Donation creation timestamp (UTC)")


class RenderTaskType(str, Enum):
    """Render task variants."""

    PLAN = "plan"
    TEXT = "text"


@dataclass(slots=True)
class RenderTask:
    """Task handed to the renderer worker."""

    event: DonationEvent
    content_type: RenderTaskType
    plan: Optional[CanvasDocument] = None
    fallback_text: Optional[str] = None
    nsfw_flag: bool = False
    hold_duration_sec: Optional[int] = None

    def require_plan(self) -> CanvasDocument:
        """Return the validated plan or raise if missing."""

        if self.plan is None:
            raise ValueError("RenderTask does not contain a Canvas plan")
        return self.plan
