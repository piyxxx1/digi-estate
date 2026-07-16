import asyncio
from services.ai.ai_service import GeminiService
from dotenv import load_dotenv

load_dotenv()

async def main():
    service = GeminiService()
    print("Testing stream...")
    try:
        async for chunk in service.generate_response_stream("Hello", []):
            print(f"Chunk: {chunk}")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
