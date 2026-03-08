"""Tests for the Manifest builder."""

from opa.manifest import Manifest, ExecutionMode


def test_minimal_manifest():
    m = Manifest()
    text = m.serialize()
    assert "Manifest-Version: 1.0" in text
    assert "OPA-Version: 0.1" in text
    assert "Prompt-File: prompt.md" in text
    # Defaults should not appear
    assert "Data-Root" not in text
    assert "Execution-Mode" not in text


def test_manifest_with_all_fields():
    m = Manifest(
        title="Test Task",
        description="A test description",
        agent_hint="claude-sonnet-4-6",
        execution_mode=ExecutionMode.BATCH,
        data_root="assets/",
        session_file="history.json",
        schema_extensions=["https://example.com/ext/v1"],
        extra={"Custom-Field": "custom-value"},
    )
    text = m.serialize()
    assert "Title: Test Task" in text
    assert "Description: A test description" in text
    assert "Agent-Hint: claude-sonnet-4-6" in text
    assert "Execution-Mode: batch" in text
    assert "Data-Root: assets/" in text
    assert "Session-File: history.json" in text
    assert "Schema-Extensions: https://example.com/ext/v1" in text
    assert "Custom-Field: custom-value" in text


def test_manifest_line_wrapping():
    m = Manifest(title="A" * 100)
    text = m.serialize()
    for line in text.split("\r\n"):
        assert len(line.encode("utf-8")) <= 72


def test_manifest_to_bytes():
    m = Manifest()
    data = m.to_bytes()
    assert isinstance(data, bytes)
    assert b"Manifest-Version: 1.0" in data
