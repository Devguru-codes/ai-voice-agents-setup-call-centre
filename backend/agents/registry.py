"""
Multi-agent registry — defines personas, system prompts, and available tools
for each specialized agent.
"""
from tools.schemas import (
    BOOK_MEETING_TOOL,
    SEND_EMAIL_TOOL,
    UPDATE_CRM_TOOL,
    SEARCH_DOCS_TOOL,
    TRANSFER_AGENT_TOOL,
)

# ── Agent definitions ─────────────────────────────────────────────────────────

AGENTS: dict[str, dict] = {

    "receptionist": {
        "name": "Receptionist",
        "system_prompt": (
            "You are a professional AI receptionist. Your job is to greet callers warmly, "
            "understand what they need, and transfer them to the right specialist. "
            "Be concise — no long monologues. Speak in short, natural sentences suitable for voice. "
            "If the caller has a sales question, transfer them to sales. "
            "If they have a technical or support issue, transfer them to support. "
            "If they want to schedule something directly, transfer them to scheduling."
        ),
        "tools": [TRANSFER_AGENT_TOOL, UPDATE_CRM_TOOL],
        "voice": "en-US-JennyNeural",
    },

    "sales": {
        "name": "Sales Agent",
        "system_prompt": (
            "You are an expert AI sales agent. Your goal is to qualify leads and book meetings. "
            "Be friendly, consultative, and enthusiastic — but not pushy. "
            "Ask discovery questions: budget, timeline, company size, pain points. "
            "If the customer is interested, book a demo call. "
            "If they leave contact info, update the CRM. "
            "Always speak in short, natural sentences suitable for voice."
        ),
        "tools": [BOOK_MEETING_TOOL, UPDATE_CRM_TOOL, SEND_EMAIL_TOOL, TRANSFER_AGENT_TOOL],
        "voice": "en-US-GuyNeural",
    },

    "support": {
        "name": "Support Agent",
        "system_prompt": (
            "You are a knowledgeable AI support agent. Your goal is to solve customer problems. "
            "Search the company knowledge base before answering technical questions. "
            "If you cannot solve the problem, offer to escalate via email or book a call. "
            "Be empathetic and patient. Speak in short, natural sentences suitable for voice."
        ),
        "tools": [SEARCH_DOCS_TOOL, SEND_EMAIL_TOOL, TRANSFER_AGENT_TOOL],
        "voice": "en-US-AriaNeural",
    },

    "scheduling": {
        "name": "Scheduling Agent",
        "system_prompt": (
            "You are an AI scheduling assistant. Your only job is to book meetings. "
            "Confirm the date, time, duration, and purpose. "
            "Book the calendar event and send a confirmation email if they provide their email. "
            "Speak in short, natural sentences suitable for voice."
        ),
        "tools": [BOOK_MEETING_TOOL, SEND_EMAIL_TOOL, TRANSFER_AGENT_TOOL],
        "voice": "en-GB-SoniaNeural",
    },
}


def get_agent(name: str) -> dict:
    """
    Return the agent definition by name.
    Defaults to 'receptionist' if name is not found.
    """
    return AGENTS.get(name.lower(), AGENTS["receptionist"])


def get_system_prompt(name: str, customer_context: dict | None = None) -> str:
    """
    Build the full system prompt for an agent, injecting customer history if available.
    """
    agent = get_agent(name)
    prompt = agent["system_prompt"]

    if customer_context:
        lines = ["\n\n--- CUSTOMER CONTEXT ---"]
        if customer_context.get("name"):
            lines.append(f"Name: {customer_context['name']}")
        if customer_context.get("company"):
            lines.append(f"Company: {customer_context['company']}")
        if customer_context.get("lead_status"):
            lines.append(f"Lead Status: {customer_context['lead_status']}")
        if customer_context.get("notes"):
            lines.append(f"Notes: {customer_context['notes']}")
        prompt += "\n".join(lines)

    return prompt


def get_tools(name: str) -> list[dict]:
    """Return the tool definitions for an agent."""
    return get_agent(name).get("tools", [])

def get_agent_voice(name: str) -> str | None:
    """Return the edge-tts voice ID for an agent."""
    return get_agent(name).get("voice")
