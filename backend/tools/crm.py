"""
CRM tool — reads and updates customer records in PostgreSQL.
"""
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memory.database import Customer, AsyncSessionFactory

logger = logging.getLogger(__name__)

VALID_STATUSES = {"new", "qualified", "disqualified", "customer"}


async def update_crm(
    customer_id: str,
    name: Optional[str] = None,
    company: Optional[str] = None,
    email: Optional[str] = None,
    lead_status: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """
    Upsert a customer record.

    Returns:
        dict with keys: success, customer_id, message
    """
    if lead_status and lead_status not in VALID_STATUSES:
        return {
            "success": False,
            "message": f"Invalid lead_status '{lead_status}'. Must be one of: {VALID_STATUSES}",
        }

    try:
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(Customer).where(Customer.id == customer_id)
            )
            customer = result.scalar_one_or_none()

            if customer is None:
                customer = Customer(id=customer_id)
                session.add(customer)
                action = "created"
            else:
                action = "updated"

            if name is not None:
                customer.name = name
            if company is not None:
                customer.company = company
            if email is not None:
                customer.email = email
            if lead_status is not None:
                customer.lead_status = lead_status
            if notes is not None:
                customer.notes = notes

            await session.commit()

        logger.info(f"📋 CRM {action}: {customer_id}")
        return {
            "success": True,
            "customer_id": customer_id,
            "message": (
                f"✅ Customer record {action}. "
                f"{'Status: ' + lead_status + '.' if lead_status else ''}"
            ),
        }

    except Exception as e:
        msg = f"CRM update failed: {e}"
        logger.error(f"❌ CRM tool error: {msg}")
        return {"success": False, "message": msg}


async def get_customer(customer_id: str) -> Optional[dict]:
    """Fetch a customer record by ID. Returns None if not found."""
    try:
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(Customer).where(Customer.id == customer_id)
            )
            customer = result.scalar_one_or_none()
            if customer is None:
                return None
            return {
                "id": customer.id,
                "name": customer.name,
                "company": customer.company,
                "email": customer.email,
                "phone": customer.phone,
                "lead_status": customer.lead_status,
                "notes": customer.notes,
            }
    except Exception as e:
        logger.error(f"❌ CRM get error: {e}")
        return None
