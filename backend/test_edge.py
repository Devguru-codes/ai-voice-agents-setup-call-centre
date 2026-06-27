import edge_tts
import asyncio

async def test():
    communicate = edge_tts.Communicate('Hello', 'en-US-ChristopherNeural')
    chunks = [c async for c in communicate.stream()]
    print([c['type'] for c in chunks])

asyncio.run(test())
