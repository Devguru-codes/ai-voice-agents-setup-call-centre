import pytest
from agents.registry import get_agent, get_system_prompt, get_tools, get_agent_voice

def test_get_agent_exists():
    agent = get_agent("receptionist")
    assert agent["name"] == "Receptionist"
    assert "receptionist" in agent["system_prompt"].lower()

def test_get_agent_fallback():
    agent = get_agent("unknown_agent")
    assert agent["name"] == "Receptionist"

def test_get_tools():
    tools = get_tools("sales")
    assert len(tools) > 0
    # Check if transfer tool is present
    has_transfer = any(t["function"]["name"] == "transfer_agent" for t in tools)
    assert has_transfer

def test_get_agent_voice():
    voice = get_agent_voice("receptionist")
    assert "Neural" in voice

def test_get_system_prompt_with_context():
    ctx = {"name": "John Doe", "company": "Acme Corp"}
    prompt = get_system_prompt("sales", ctx)
    assert "John Doe" in prompt
    assert "Acme Corp" in prompt
