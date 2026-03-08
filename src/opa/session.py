"""Session history model for OPA archives."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union


class ContentBlock:
    """A content block within a message (text, image, file, or tool-related)."""

    def __init__(self, block_type: str, **kwargs: Any):
        self.type = block_type
        self.data = kwargs

    @classmethod
    def text(cls, text: str) -> "ContentBlock":
        return cls("text", text=text)

    @classmethod
    def image(cls, path: str, media_type: str = "image/png") -> "ContentBlock":
        return cls("image", path=path, media_type=media_type)

    @classmethod
    def file(cls, path: str, media_type: Optional[str] = None) -> "ContentBlock":
        d = {"path": path}
        if media_type:
            d["media_type"] = media_type
        return cls("file", **d)

    @classmethod
    def tool_use(cls, tool_id: str, name: str, input_data: Any) -> "ContentBlock":
        return cls("tool_use", id=tool_id, name=name, input=input_data)

    @classmethod
    def tool_result(cls, tool_use_id: str, content: str) -> "ContentBlock":
        return cls("tool_result", tool_use_id=tool_use_id, content=content)

    def to_dict(self) -> Dict[str, Any]:
        result = {"type": self.type}
        result.update(self.data)
        return result


class Message:
    """A single message in the session history."""

    def __init__(
        self,
        role: str,
        content: Union[str, List[ContentBlock]],
        *,
        timestamp: Optional[str] = None,
    ):
        if role not in ("user", "assistant", "system", "tool"):
            raise ValueError(f"Invalid role: {role!r}")
        self.role = role
        self.content = content
        self.timestamp = timestamp

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"role": self.role}
        if isinstance(self.content, str):
            d["content"] = self.content
        else:
            d["content"] = [b.to_dict() for b in self.content]
        if self.timestamp:
            d["timestamp"] = self.timestamp
        return d


class SessionHistory:
    """Session history (session/history.json) for an OPA archive."""

    def __init__(
        self,
        messages: Optional[List[Message]] = None,
        *,
        session_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ):
        self.messages = messages or []
        self.session_id = session_id or str(uuid.uuid4())
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    def add_user(self, content: Union[str, List[ContentBlock]], **kwargs: Any) -> None:
        self.messages.append(Message("user", content, **kwargs))

    def add_assistant(self, content: Union[str, List[ContentBlock]], **kwargs: Any) -> None:
        self.messages.append(Message("assistant", content, **kwargs))

    def add_system(self, content: str, **kwargs: Any) -> None:
        self.messages.append(Message("system", content, **kwargs))

    def add_tool(self, content: Union[str, List[ContentBlock]], **kwargs: Any) -> None:
        self.messages.append(Message("tool", content, **kwargs))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": "0.1",
            "session_id": self.session_id,
            "created_at": self.created_at,
            "messages": [m.to_dict() for m in self.messages],
        }

    def to_json(self, **kwargs: Any) -> str:
        kwargs.setdefault("indent", 2)
        kwargs.setdefault("ensure_ascii", False)
        return json.dumps(self.to_dict(), **kwargs)

    def to_bytes(self) -> bytes:
        return self.to_json().encode("utf-8")
