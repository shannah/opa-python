"""Tests for the Prompt handler."""

from opa.prompt import Prompt


def test_prompt_basic():
    p = Prompt("Hello, world!")
    assert p.content == "Hello, world!"
    assert p.path == "prompt.md"


def test_prompt_template_variables():
    p = Prompt("Run in {{extracted_path}} at {{timestamp}}.")
    assert p.variables() == {"extracted_path", "timestamp"}


def test_prompt_render():
    p = Prompt("Archive: {{archive_name}}, Agent: {{agent}}")
    rendered = p.render({"archive_name": "test", "agent": "gpt-4"})
    assert rendered == "Archive: test, Agent: gpt-4"


def test_prompt_render_partial():
    p = Prompt("{{archive_name}} - {{unknown}}")
    rendered = p.render({"archive_name": "demo"})
    assert rendered == "demo - {{unknown}}"


def test_prompt_to_bytes():
    p = Prompt("Test")
    assert p.to_bytes() == b"Test"
