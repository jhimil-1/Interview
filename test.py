import asyncio
import websockets

async def test_connection():
    async with websockets.connect(
        'wss://api.deepgram.com/v1/listen?encoding=linear16&sample_rate=16000&channels=1',
        extra_headers={'Authorization': f'Token YOUR_API_KEY'}
    ) as ws:
        print("Connected successfully!")

asyncio.run(test_connection())