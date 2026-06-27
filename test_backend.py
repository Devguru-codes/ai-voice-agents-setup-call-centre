import asyncio
import httpx
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestSuite")

async def test_backend():
    base_url = "http://localhost:8000"
    
    logger.info("🧪 Testing /health...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{base_url}/health")
            if resp.status_code == 200:
                logger.info(f"✅ /health OK: {resp.json()}")
            else:
                logger.error(f"❌ /health Failed: {resp.status_code}")
                return
    except Exception as e:
        logger.error(f"❌ Could not connect to backend: {e}")
        return

    logger.info("\n🧪 Testing /api/settings...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{base_url}/api/settings")
            if resp.status_code == 200:
                logger.info(f"✅ /api/settings OK: {resp.json()}")
            else:
                logger.warning(f"⚠️ /api/settings returned {resp.status_code}. (Expected if DB is totally empty, wait for migrations)")
    except Exception as e:
        logger.error(f"❌ /api/settings Failed: {e}")

    logger.info("\n🧪 Testing /api/analytics/summary...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{base_url}/api/analytics/summary")
            if resp.status_code == 200:
                logger.info(f"✅ /api/analytics/summary OK: {resp.json()}")
            else:
                logger.warning(f"⚠️ /api/analytics/summary returned {resp.status_code}.")
    except Exception as e:
        logger.error(f"❌ /api/analytics/summary Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_backend())
