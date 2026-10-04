"""What one ``opencode run`` session did."""

from __future__ import annotations

from dataclasses import dataclass, field

from .tool_call import ToolCall


@dataclass
class Transcript:
    """What one ``opencode run`` session did."""

    exit_code: int
    timed_out: bool
    seconds: float
    tool_calls: list[ToolCall] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    cost: float = 0.0
    tokens: dict[str, int] = field(default_factory=dict)
    steps: int = 0
    errors: list[str] = field(default_factory=list)
    stderr: str = ""

    @property
    def reply(self) -> str:
        """Return the agent's final text reply.

        Returns
        -------
        str
            The last text entry, or an empty string if no texts were recorded.
        """
        return self.texts[-1] if self.texts else ""
