import pytest
from tools.router import execute_tool
from tools.schemas import BOOK_MEETING_TOOL, TRANSFER_AGENT_TOOL

@pytest.mark.asyncio
async def test_execute_tool_transfer():
    args = '{"agent_name": "support", "reason": "user needs help"}'
    result, is_transfer = await execute_tool("transfer_agent", args, "call-123")
    
    assert is_transfer is True
    assert result == "support"

@pytest.mark.asyncio
async def test_execute_tool_unknown():
    result, is_transfer = await execute_tool("fake_tool", "{}", "call-123")
    assert is_transfer is False
    assert "Unknown tool" in result

def test_tool_schemas_valid():
    # Ensure they have valid JSON schema structure
    assert "name" in BOOK_MEETING_TOOL["function"]
    assert "parameters" in TRANSFER_AGENT_TOOL["function"]
