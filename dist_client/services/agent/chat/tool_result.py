from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from html import escape
from typing import Any, Optional

from services.agent.chat.tool_policy import ToolEffect


class ToolResultStatus(str, Enum):
    OK = "ok"
    NEEDS_REVIEW = "needs_review"
    UNKNOWN = "unknown"
    ERROR = "error"


@dataclass
class ToolResult:
    tool: str
    status: ToolResultStatus
    message: str
    source: str
    data: dict[str, Any] = field(default_factory=dict)
    next_action: str = ""
    effect: Optional[ToolEffect] = None
    confirmation_required: bool = False
    operation_id: str = ""

    @property
    def can_llm_infer(self) -> bool:
        return self.status == ToolResultStatus.OK

    @classmethod
    def ok(cls, tool: str, message: str, source: str, **data: Any) -> "ToolResult":
        return cls(tool=tool, status=ToolResultStatus.OK, message=message, source=source, data=data)

    @classmethod
    def needs_review(cls, tool: str, message: str, source: str, **data: Any) -> "ToolResult":
        return cls(tool=tool, status=ToolResultStatus.NEEDS_REVIEW, message=message, source=source, data=data)

    @classmethod
    def unknown(cls, tool: str, message: str, source: str, **data: Any) -> "ToolResult":
        return cls(tool=tool, status=ToolResultStatus.UNKNOWN, message=message, source=source, data=data)

    @classmethod
    def error(cls, tool: str, message: str, source: str, **data: Any) -> "ToolResult":
        return cls(tool=tool, status=ToolResultStatus.ERROR, message=message, source=source, data=data)


def render_tool_result_html(result: ToolResult) -> str:
    icon = {
        ToolResultStatus.OK: "✅",
        ToolResultStatus.NEEDS_REVIEW: "⚠️",
        ToolResultStatus.UNKNOWN: "ℹ️",
        ToolResultStatus.ERROR: "❌",
    }[result.status]
    parts = [
        f"{icon} <b>{escape(result.message)}</b>",
        f"<br><small>Izvor: {escape(result.source)} | status: {escape(result.status.value)}</small>",
    ]
    if result.next_action:
        parts.append(f"<br><small>Sljedeće: {escape(result.next_action)}</small>")
    return "".join(parts)


TOOL_RESULT_PROMPT_RULE = (
    "Ako dobiješ strukturisani TOOL_RESULT, smiješ samo formatirati njegove podatke. "
    "Ne mijenjaj status, izvor, tarifni broj, porijeklo, povlasticu ni zaključak. "
    "Ako je status unknown ili needs_review, jasno reci da servis nema potvrđen podatak "
    "i nemoj dodavati pretpostavke."
)
