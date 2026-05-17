import asyncio
import sys
import os

# Adjust sys.path to find backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, Chapter
from services.background_translator import BackgroundTranslator

async def main():
    print("Testing batch execution directly in Python process...")
    try:
        # We will translate chapter 672 (order 2) with overwrite=True and ai_extract=True
        # To see the exact trace output!
        print("Starting _do_translate for chapter 672...")
        await BackgroundTranslator._do_translate(
            chapter_id=672,
            thread_id=5,
            target_lang="English",
            model="qwen/qwen3-4b-2507",
            lm_url="http://localhost:1234",
            force_extract=True,
            force_overwrite=True
        )
        print("Direct execution finished successfully!")
    except Exception as e:
        import traceback
        print("EXCEPTION DETECTED IN DIRECT BATCH TRANSLATION:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
