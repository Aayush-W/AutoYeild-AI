import sys
import traceback
import asyncio
from fastapi import FastAPI

print("Starting import test...")
try:
    from api.app import app, lifespan
    print("Import successful. Testing lifespan...")
    
    async def test_lifespan():
        try:
            async with lifespan(app):
                print("Lifespan started successfully.")
        except Exception as e:
            print("Lifespan error:", e)
            traceback.print_exc()

    asyncio.run(test_lifespan())

except Exception as e:
    print("Import Error:", e)
    traceback.print_exc()
