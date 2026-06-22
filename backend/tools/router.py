"""
Tool execution router — dispatches Groq tool_call results to the right handler.
"""
import json
import logging
from typing import Any

from tools.calendar import book_meeting
from tools.email_tool import send_email
from tools.crm import update_crm
from rag.retriever import search_docs

logger = logging.getLogger(__name__)


async def execute_tool(
    tool_name: str,
    arguments_json: str,
    call_id: str = "",
) -> tuple[str, bool]:
    """
    Parse arguments and dispatch to the correct tool.

    Args:
        tool_name:       Name of the tool (from Groq function call).
        arguments_json:  JSON string of tool arguments.
        call_id:         The active call ID (for CRM context).

    Returns:
        Tuple of (result_string_for_llm, is_agent_transfer).
        If is_agent_transfer is True, result_string contains the agent name.
    """
    try:
        args: dict = json.loads(arguments_json)
    except json.JSONDecodeError as e:
        logger.error(f"❌ Tool router: failed to parse arguments for {tool_name}: {e}")
        return f"Error: Could not parse tool arguments — {e}", False

    logger.info(f"🔧 Executing tool: {tool_name} | args: {args}")

    try:
        if tool_name == "book_meeting":
            result = await book_meeting(
                summary=args["summary"],
                date_time_iso=args["date_time_iso"],
                duration_minutes=args.get("duration_minutes", 30),
                attendee_email=args.get("attendee_email"),
            )
            return result["message"], False

        elif tool_name == "send_email":
            result = await send_email(
                to_email=args["to_email"],
                subject=args["subject"],
                body=args["body"],
            )
            return result["message"], False

        elif tool_name == "update_crm":
            result = await update_crm(
                customer_id=args.get("customer_id", call_id),
                name=args.get("name"),
                company=args.get("company"),
                email=args.get("email"),
                lead_status=args.get("lead_status"),
                notes=args.get("notes"),
            )
            return result["message"], False

        elif tool_name == "search_company_docs":
            docs = await search_docs(args["query"])
            if docs:
                context = "\n\n".join(
                    f"[Source: {d['source']}]\n{d['text']}" for d in docs
                )
                return f"Knowledge base results:\n\n{context}", False
            return "No relevant information found in the knowledge base.", False

        elif tool_name == "transfer_agent":
            agent_name = args.get("agent_name", "receptionist")
            reason = args.get("reason", "")
            logger.info(f"🔀 Agent transfer requested: {agent_name} ({reason})")
            return agent_name, True  # Signal: this is a transfer

        else:
            msg = f"Unknown tool: {tool_name}"
            logger.warning(f"⚠️ {msg}")
            return msg, False

    except Exception as e:
        msg = f"Tool '{tool_name}' execution failed: {e}"
        logger.error(f"❌ {msg}")
        return msg, False
