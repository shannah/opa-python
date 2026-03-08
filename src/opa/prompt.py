"""Prompt file handling for OPA archives."""

import re
from typing import Dict, Optional


# Reserved template variables
RESERVED_VARIABLES = frozenset({
    "archive_name",
    "extracted_path",
    "timestamp",
    "agent",
})


class Prompt:
    """Represents the prompt.md file in an OPA archive.

    Supports Markdown content with {{variable_name}} template variables.
    """

    _TEMPLATE_RE = re.compile(r"\{\{(\w+)\}\}")

    def __init__(self, content: str, *, path: str = "prompt.md"):
        self.content = content
        self.path = path

    @classmethod
    def from_file(cls, filepath: str, *, archive_path: str = "prompt.md") -> "Prompt":
        """Load prompt content from a local file."""
        with open(filepath, "r", encoding="utf-8") as f:
            return cls(f.read(), path=archive_path)

    def variables(self) -> set:
        """Return all template variable names found in the content."""
        return set(self._TEMPLATE_RE.findall(self.content))

    def render(self, variables: Optional[Dict[str, str]] = None) -> str:
        """Render the prompt with the given template variables.

        Unresolved variables are left as-is.
        """
        if not variables:
            return self.content

        def replacer(match: re.Match) -> str:
            name = match.group(1)
            return variables.get(name, match.group(0))

        return self._TEMPLATE_RE.sub(replacer, self.content)

    def to_bytes(self) -> bytes:
        """Return UTF-8 encoded content."""
        return self.content.encode("utf-8")
