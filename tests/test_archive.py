"""Tests for the OPA archive builder."""

import json
import os
import tempfile
import zipfile

from opa.archive import OpaArchive
from opa.manifest import Manifest, ExecutionMode
from opa.prompt import Prompt
from opa.session import SessionHistory
from opa.data_assets import DataIndex


def test_minimal_archive():
    archive = OpaArchive(
        manifest=Manifest(title="Test"),
        prompt=Prompt("Do something."),
    )
    data = archive.to_bytes()

    with zipfile.ZipFile(__import__("io").BytesIO(data)) as zf:
        names = zf.namelist()
        assert "META-INF/MANIFEST.MF" in names
        assert "prompt.md" in names

        manifest_text = zf.read("META-INF/MANIFEST.MF").decode("utf-8")
        assert "OPA-Version: 0.1" in manifest_text

        prompt_text = zf.read("prompt.md").decode("utf-8")
        assert prompt_text == "Do something."


def test_archive_with_session():
    session = SessionHistory(session_id="s1", created_at="2025-01-01T00:00:00Z")
    session.add_user("Hello")
    session.add_assistant("Hi")

    archive = OpaArchive(
        manifest=Manifest(),
        prompt=Prompt("Continue the conversation."),
    )
    archive.set_session(session)
    data = archive.to_bytes()

    with zipfile.ZipFile(__import__("io").BytesIO(data)) as zf:
        assert "session/history.json" in zf.namelist()
        history = json.loads(zf.read("session/history.json"))
        assert len(history["messages"]) == 2


def test_archive_with_data():
    archive = OpaArchive(prompt=Prompt("Analyse data."))
    archive.add_data_bytes("data/sample.csv", b"a,b,c\n1,2,3\n")

    idx = DataIndex()
    idx.add("data/sample.csv", description="Sample CSV", content_type="text/csv")
    archive.set_data_index(idx)

    data = archive.to_bytes()
    with zipfile.ZipFile(__import__("io").BytesIO(data)) as zf:
        assert "data/sample.csv" in zf.namelist()
        assert "data/INDEX.json" in zf.namelist()
        assert zf.read("data/sample.csv") == b"a,b,c\n1,2,3\n"


def test_archive_write_to_file():
    archive = OpaArchive(prompt=Prompt("Test."))
    with tempfile.NamedTemporaryFile(suffix=".opa", delete=False) as f:
        path = f.name
    try:
        archive.write(path)
        assert zipfile.is_zipfile(path)
        with zipfile.ZipFile(path) as zf:
            assert "META-INF/MANIFEST.MF" in zf.namelist()
    finally:
        os.unlink(path)


def test_path_traversal_rejected():
    archive = OpaArchive()
    try:
        archive.add_data_bytes("../etc/passwd", b"bad")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_absolute_path_rejected():
    archive = OpaArchive()
    try:
        archive.add_data_bytes("/etc/passwd", b"bad")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_add_data_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some test files
        os.makedirs(os.path.join(tmpdir, "sub"))
        with open(os.path.join(tmpdir, "a.txt"), "w") as f:
            f.write("aaa")
        with open(os.path.join(tmpdir, "sub", "b.txt"), "w") as f:
            f.write("bbb")

        archive = OpaArchive(prompt=Prompt("Test."))
        archive.add_data_dir(tmpdir, "data/")

        data = archive.to_bytes()
        with zipfile.ZipFile(__import__("io").BytesIO(data)) as zf:
            assert "data/a.txt" in zf.namelist()
            assert "data/sub/b.txt" in zf.namelist()
