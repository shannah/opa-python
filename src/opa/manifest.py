"""Manifest builder for OPA archives (META-INF/MANIFEST.MF)."""

from enum import Enum
from typing import Dict, List, Optional


class ExecutionMode(Enum):
    INTERACTIVE = "interactive"
    BATCH = "batch"
    AUTONOMOUS = "autonomous"


class Manifest:
    """Builds a JAR-style MANIFEST.MF for an OPA archive.

    Required fields: Manifest-Version (always 1.0), OPA-Version (always 0.1).
    """

    _MAX_LINE = 72

    def __init__(
        self,
        *,
        prompt_file: str = "prompt.md",
        title: Optional[str] = None,
        description: Optional[str] = None,
        agent_hint: Optional[str] = None,
        execution_mode: ExecutionMode = ExecutionMode.INTERACTIVE,
        data_root: str = "data/",
        session_file: str = "session/history.json",
        schema_extensions: Optional[List[str]] = None,
        extra: Optional[Dict[str, str]] = None,
    ):
        self.prompt_file = prompt_file
        self.title = title
        self.description = description
        self.agent_hint = agent_hint
        self.execution_mode = execution_mode
        self.data_root = data_root
        self.session_file = session_file
        self.schema_extensions = schema_extensions or []
        self.extra = extra or {}

    def _wrap_line(self, line: str) -> str:
        """Wrap a manifest line to the 72-byte limit with continuation."""
        encoded = line.encode("utf-8")
        if len(encoded) <= self._MAX_LINE:
            return line

        parts: list[str] = []
        first_chunk = line[:self._MAX_LINE]
        parts.append(first_chunk)
        remaining = line[self._MAX_LINE:]

        while remaining:
            # Continuation lines: space + up to 71 bytes of content
            chunk = remaining[: self._MAX_LINE - 1]
            parts.append(" " + chunk)
            remaining = remaining[self._MAX_LINE - 1:]

        return "\r\n".join(parts)

    def _add_field(self, lines: list, name: str, value: str) -> None:
        lines.append(self._wrap_line(f"{name}: {value}"))

    def serialize(self) -> str:
        """Serialize the manifest to MANIFEST.MF format."""
        lines: list[str] = []
        self._add_field(lines, "Manifest-Version", "1.0")
        self._add_field(lines, "OPA-Version", "0.1")
        self._add_field(lines, "Prompt-File", self.prompt_file)

        if self.title:
            self._add_field(lines, "Title", self.title)
        if self.description:
            self._add_field(lines, "Description", self.description)
        if self.agent_hint:
            self._add_field(lines, "Agent-Hint", self.agent_hint)

        if self.execution_mode != ExecutionMode.INTERACTIVE:
            self._add_field(lines, "Execution-Mode", self.execution_mode.value)

        if self.data_root != "data/":
            self._add_field(lines, "Data-Root", self.data_root)
        if self.session_file != "session/history.json":
            self._add_field(lines, "Session-File", self.session_file)

        if self.schema_extensions:
            self._add_field(
                lines, "Schema-Extensions", " ".join(self.schema_extensions)
            )

        for key, value in self.extra.items():
            self._add_field(lines, key, value)

        return "\r\n".join(lines) + "\r\n"

    def to_bytes(self) -> bytes:
        """Serialize to UTF-8 bytes."""
        return self.serialize().encode("utf-8")
