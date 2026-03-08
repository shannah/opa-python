"""Tests for the SessionHistory model."""

import json

from opa.session import SessionHistory, Message, ContentBlock


def test_session_basic():
    s = SessionHistory(session_id="test-id", created_at="2025-01-01T00:00:00Z")
    s.add_user("Hello")
    s.add_assistant("Hi there!")

    data = s.to_dict()
    assert data["version"] == "0.1"
    assert data["session_id"] == "test-id"
    assert len(data["messages"]) == 2
    assert data["messages"][0] == {"role": "user", "content": "Hello"}
    assert data["messages"][1] == {"role": "assistant", "content": "Hi there!"}


def test_session_multimodal():
    s = SessionHistory()
    s.add_user([
        ContentBlock.text("Look at this image"),
        ContentBlock.image("session/attachments/img.png"),
    ])
    data = s.to_dict()
    msg = data["messages"][0]
    assert msg["content"][0] == {"type": "text", "text": "Look at this image"}
    assert msg["content"][1]["type"] == "image"


def test_session_to_json():
    s = SessionHistory(session_id="s1", created_at="2025-01-01T00:00:00Z")
    s.add_user("test")
    text = s.to_json()
    parsed = json.loads(text)
    assert parsed["session_id"] == "s1"


def test_invalid_role():
    try:
        Message("invalid_role", "content")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
