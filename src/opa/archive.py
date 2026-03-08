"""OPA archive builder — creates .opa (ZIP) files."""

import os
import zipfile
from pathlib import Path, PurePosixPath
from typing import Optional, Union

from opa.manifest import Manifest
from opa.prompt import Prompt
from opa.session import SessionHistory
from opa.data_assets import DataIndex


def _validate_path(entry_path: str) -> None:
    """Reject paths with traversal or absolute components."""
    parts = PurePosixPath(entry_path).parts
    if any(p == ".." for p in parts):
        raise ValueError(f"Path traversal not allowed: {entry_path!r}")
    if entry_path.startswith("/"):
        raise ValueError(f"Absolute paths not allowed: {entry_path!r}")


class OpaArchive:
    """Builder for .opa archive files.

    Minimal usage::

        archive = OpaArchive(
            manifest=Manifest(title="My Task"),
            prompt=Prompt("Summarise the data in `data/report.csv`."),
        )
        archive.add_data_file("data/report.csv", "/local/path/report.csv")
        archive.write("task.opa")
    """

    def __init__(
        self,
        *,
        manifest: Optional[Manifest] = None,
        prompt: Optional[Prompt] = None,
    ):
        self.manifest = manifest or Manifest()
        self.prompt = prompt or Prompt("")
        self.session: Optional[SessionHistory] = None
        self.data_index: Optional[DataIndex] = None
        self._files: dict[str, Union[bytes, str]] = {}

    # --- convenience setters ---

    def set_session(self, session: SessionHistory) -> "OpaArchive":
        self.session = session
        return self

    def set_data_index(self, index: DataIndex) -> "OpaArchive":
        self.data_index = index
        return self

    # --- adding files ---

    def add_data_bytes(self, archive_path: str, data: bytes) -> "OpaArchive":
        """Add raw bytes as a data asset."""
        _validate_path(archive_path)
        self._files[archive_path] = data
        return self

    def add_data_file(self, archive_path: str, local_path: str) -> "OpaArchive":
        """Add a local file as a data asset."""
        _validate_path(archive_path)
        self._files[archive_path] = os.path.abspath(local_path)
        return self

    def add_data_dir(self, local_dir: str, archive_prefix: str = "data/") -> "OpaArchive":
        """Recursively add all files under a local directory."""
        base = Path(local_dir)
        for path in sorted(base.rglob("*")):
            if path.is_file():
                rel = path.relative_to(base)
                archive_path = archive_prefix + str(PurePosixPath(rel))
                self.add_data_file(archive_path, str(path))
        return self

    def add_extension_file(self, archive_path: str, data: bytes) -> "OpaArchive":
        """Add a file under META-INF/extensions/."""
        _validate_path(archive_path)
        full = f"META-INF/extensions/{archive_path}"
        self._files[full] = data
        return self

    # --- writing ---

    def write(self, path: str) -> None:
        """Write the OPA archive to *path*."""
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Manifest (required)
            zf.writestr("META-INF/MANIFEST.MF", self.manifest.to_bytes())

            # Prompt file (required)
            zf.writestr(self.prompt.path, self.prompt.to_bytes())

            # Session history (optional)
            if self.session:
                zf.writestr(
                    self.manifest.session_file, self.session.to_bytes()
                )

            # Data index (optional)
            if self.data_index:
                zf.writestr(
                    self.manifest.data_root + "INDEX.json",
                    self.data_index.to_bytes(),
                )

            # All additional files
            for archive_path, content in self._files.items():
                if isinstance(content, bytes):
                    zf.writestr(archive_path, content)
                else:
                    zf.write(content, archive_path)

    def to_bytes(self) -> bytes:
        """Return the archive as an in-memory bytes object."""
        import io

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("META-INF/MANIFEST.MF", self.manifest.to_bytes())
            zf.writestr(self.prompt.path, self.prompt.to_bytes())
            if self.session:
                zf.writestr(self.manifest.session_file, self.session.to_bytes())
            if self.data_index:
                zf.writestr(
                    self.manifest.data_root + "INDEX.json",
                    self.data_index.to_bytes(),
                )
            for archive_path, content in self._files.items():
                if isinstance(content, bytes):
                    zf.writestr(archive_path, content)
                else:
                    zf.write(content, archive_path)
        return buf.getvalue()
