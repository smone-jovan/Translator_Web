import asyncio
import sys
import subprocess
import os
sys.stdout.reconfigure(encoding='utf-8')

from playwright.async_api import async_playwright

# Strategy: Launch Chrome with remote debugging, let user solve CF once,
# then reuse the cookies for all future requests.
# Uses the user's REAL Chrome profile so existing CF cookies work.

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEBUG_PORT = 9222

async def test():
    url = "https://www.novelupdates.com/series/i-am-a-fierce-ghost-how-could-i-possibly-submit-to-living-under-others/"
    
    # Check if Chrome is already running with debug port
    print("Connecting to Chrome via CDP...")
    
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
            print(f"Connected! Contexts: {len(browser.contexts)}")
        except Exception as e:
            print(f"Could not connect to Chrome on port {DEBUG_PORT}.")
            print(f"Error: {e}")
            print()
            print("=== INSTRUCTIONS ===")
            print("Please close ALL Chrome windows first, then run this command:")
            print(f'  "{CHROME_PATH}" --remote-debugging-port={DEBUG_PORT}')
            print()
            print("Or run it via PowerShell:")
            print(f'  Start-Process "{CHROME_PATH}" -ArgumentList "--remote-debugging-port={DEBUG_PORT}"')
            print()
            print("Then run this script again.")
            return
        
        # Get existing context or create new page
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()
        
        print(f"Navigating to {url}...")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # Wait for content — since this is the REAL browser, CF should pass
        print("Waiting for page content...")
        for attempt in range(12):  # 60 seconds max
            title = await page.title()
            print(f"  Attempt {attempt+1}: '{title}'")
            
            if "just a moment" not in title.lower():
                print("SUCCESS! Cloudflare passed!")
                break
            
            await asyncio.sleep(5)
        else:
            print("FAILED: Cloudflare still blocking after 60s")
            await page.close()
            return
        
        # Extract metadata
        print("=" * 50)
        print("EXTRACTION RESULTS:")
        print("=" * 50)
        
        title_el = await page.query_selector("div.seriestitlenu")
        novel_title = await title_el.inner_text() if title_el else "NOT FOUND"
        print(f"Title: {novel_title}")
        
        img_el = await page.query_selector("div.seriesimg img")
        cover_url = await img_el.get_attribute("src") if img_el else "NOT FOUND"
        print(f"Cover URL: {cover_url}")
        
        genre_els = await page.query_selector_all("#seriesgenre a.genre")
        genres = [await g.inner_text() for g in genre_els]
        print(f"Genres: {', '.join(genres)}")
        
        desc_el = await page.query_selector("#editdescription")
        desc = await desc_el.inner_text() if desc_el else "NOT FOUND"
        print(f"Description: {desc[:400]}...")
        
        type_el = await page.query_selector("#showtype a")
        novel_type = await type_el.inner_text() if type_el else "N/A"
        print(f"Type: {novel_type}")

        await page.close()
        # Don't close the browser - it's the user's browser!

if __name__ == "__main__":
    asyncio.run(test())
