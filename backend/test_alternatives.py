import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import asyncio
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup

async def test_anilist():
    """Test AniList GraphQL API"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/json',
    }
    
    query = 'query { Media(search: "Douluo Dalu", type: MANGA) { id title { romaji english native } description genres status coverImage { large } } }'
    
    async with AsyncSession() as client:
        resp = await client.post(
            'https://graphql.anilist.co',
            json={'query': query},
            headers=headers,
            timeout=10.0
        )
        print(f'AniList Status: {resp.status_code}')
        if resp.status_code == 200:
            data = resp.json()
            media = data.get('data', {}).get('Media', {})
            print(f'Title (Romaji): {media.get("title", {}).get("romaji")}')
            print(f'Title (English): {media.get("title", {}).get("english")}')
            print(f'Genres: {media.get("genres")}')
            print(f'Status: {media.get("status")}')
            desc = media.get('description', '') or ''
            print(f'Description: {desc[:200]}')

async def test_novelfull():
    """Test NovelFull scraping"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    # Search for a novel
    query = 'Battle Through the Heavens'
    url = f'https://novelfull.com/search?keyword={query}'
    
    async with AsyncSession() as client:
        resp = await client.get(url, headers=headers, impersonate='chrome120', timeout=10.0)
        print(f'\nNovelFull Status: {resp.status_code}')
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            # Find search results
            results = soup.select('.truyen-title a')
            for r in results[:3]:
                print(f'  Title: {r.text.strip()}')
                href = r.get('href', '')
                print(f'  URL: https://novelfull.com{href}')

async def test_wuxiaworld():
    """Test Wuxiaworld API"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    
    # Wuxiaworld has an API
    url = 'https://www.wuxiaworld.com/api/novels/search?query=Battle'
    
    async with AsyncSession() as client:
        resp = await client.get(url, headers=headers, impersonate='chrome120', timeout=10.0)
        print(f'\nWuxiaworld API Status: {resp.status_code}')
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                for item in data[:3]:
                    print(f'  Title: {item.get("name", "N/A")}')

async def main():
    print("=== Testing Alternative Novel Metadata Sources ===\n")
    
    await test_anilist()
    await test_novelfull()
    await test_wuxiaworld()

asyncio.run(main())
