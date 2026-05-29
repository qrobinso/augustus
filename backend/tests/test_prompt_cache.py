import pytest
from app.services.llm.openrouter import cached_system_message


def test_cached_system_message_structure():
    msg = cached_system_message("big stable prompt")
    assert msg["role"] == "system"
    assert msg["content"][0]["type"] == "text"
    assert msg["content"][0]["text"] == "big stable prompt"
    assert msg["content"][0]["cache_control"] == {"type": "ephemeral"}
