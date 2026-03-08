"""Data assets and INDEX.json support for OPA archives."""

import json
from typing import Any, Dict, List, Optional


class DataEntry:
    """An entry in the data/INDEX.json catalog."""

    def __init__(
        self,
        path: str,
        *,
        description: Optional[str] = None,
        content_type: Optional[str] = None,
    ):
        self.path = path
        self.description = description
        self.content_type = content_type

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"path": self.path}
        if self.description:
            d["description"] = self.description
        if self.content_type:
            d["content_type"] = self.content_type
        return d


class DataIndex:
    """Catalog of data assets (data/INDEX.json)."""

    def __init__(self, entries: Optional[List[DataEntry]] = None):
        self.entries = entries or []

    def add(
        self,
        path: str,
        *,
        description: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> DataEntry:
        entry = DataEntry(path, description=description, content_type=content_type)
        self.entries.append(entry)
        return entry

    def to_list(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.entries]

    def to_json(self, **kwargs: Any) -> str:
        kwargs.setdefault("indent", 2)
        kwargs.setdefault("ensure_ascii", False)
        return json.dumps(self.to_list(), **kwargs)

    def to_bytes(self) -> bytes:
        return self.to_json().encode("utf-8")
