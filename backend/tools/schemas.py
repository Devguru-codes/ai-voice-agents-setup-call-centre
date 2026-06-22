"""
Tool schemas (Pydantic) and Groq function-calling definitions.

Groq tool calling follows the OpenAI format:
  {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
"""
from pydantic import BaseModel, Field
from typing import Optional


# ── Pydantic schemas (for internal validation) ────────────────────────────────

class BookMeetingArgs(BaseModel):
    summary: str = Field(description="Meeting title/subject")
    date_time_iso: str = Field(description="ISO-8601 datetime, e.g. 2025-01-20T14:00:00")
    duration_minutes: int = Field(default=30, description="Duration of the meeting in minutes")
    attendee_email: Optional[str] = Field(default=None, description="Customer email to invite")


class SendEmailArgs(BaseModel):
    to_email: str = Field(description="Recipient email address")
    subject: str = Field(description="Email subject line")
    body: str = Field(description="Plain-text email body")


class UpdateCRMArgs(BaseModel):
    customer_id: str = Field(description="Customer identifier (phone or ID)")
    name: Optional[str] = Field(default=None)
    company: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    lead_status: Optional[str] = Field(
        default=None,
        description="One of: new, qualified, disqualified, customer"
    )
    notes: Optional[str] = Field(default=None)


class SearchDocsArgs(BaseModel):
    query: str = Field(description="Natural language query to search the knowledge base")


class TransferAgentArgs(BaseModel):
    agent_name: str = Field(
        description="Target agent to transfer to. One of: receptionist, sales, support, scheduling"
    )
    reason: str = Field(description="Brief reason for the transfer")


# ── Groq/OpenAI tool definitions ──────────────────────────────────────────────

BOOK_MEETING_TOOL = {
    "type": "function",
    "function": {
        "name": "book_meeting",
        "description": (
            "Book a calendar meeting with the customer. "
            "Use when the customer agrees to a call or demo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Meeting title/subject"},
                "date_time_iso": {
                    "type": "string",
                    "description": "ISO-8601 datetime string e.g. 2025-01-20T14:00:00"
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Duration in minutes",
                    "default": 30
                },
                "attendee_email": {
                    "type": "string",
                    "description": "Customer email address to invite"
                },
            },
            "required": ["summary", "date_time_iso"],
        },
    },
}

SEND_EMAIL_TOOL = {
    "type": "function",
    "function": {
        "name": "send_email",
        "description": (
            "Send a follow-up email to the customer. "
            "Use for proposals, next steps, or summaries."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "to_email": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to_email", "subject", "body"],
        },
    },
}

UPDATE_CRM_TOOL = {
    "type": "function",
    "function": {
        "name": "update_crm",
        "description": "Update the CRM record for the customer with new information.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "name": {"type": "string"},
                "company": {"type": "string"},
                "email": {"type": "string"},
                "lead_status": {
                    "type": "string",
                    "enum": ["new", "qualified", "disqualified", "customer"],
                },
                "notes": {"type": "string"},
            },
            "required": ["customer_id"],
        },
    },
}

SEARCH_DOCS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_company_docs",
        "description": (
            "Search the company knowledge base for pricing, product details, "
            "FAQs, or policy information."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
    },
}

TRANSFER_AGENT_TOOL = {
    "type": "function",
    "function": {
        "name": "transfer_agent",
        "description": (
            "Transfer the customer to a specialist agent. "
            "Use when the customer's need exceeds your role."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "enum": ["receptionist", "sales", "support", "scheduling"],
                },
                "reason": {"type": "string"},
            },
            "required": ["agent_name", "reason"],
        },
    },
}
