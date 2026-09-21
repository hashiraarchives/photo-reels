"""
AAP - Actress Actor and Pinups
Browser-Based Image Downloader

Uses Playwright (headless Chrome) to download images from Wikimedia Commons.
Includes retry logic with exponential backoff for 429 rate limits.
"""

import os
import random
import asyncio
from typing import List, Dict, Optional, Tuple
from playwright.async_api import async_playwright, Browser, Page
import config


class BrowserDownloader:
    """Downloads images using a headless browser with rate-limit handling."""

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self._playwright = None
        self._consecutive_429s = 0  # Track consecutive rate limits

    async def start(self):
        """Start the headless browser."""
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        # Create context with realistic browser settings
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
        )

        self.page = await context.new_page()

        # Set extra headers to look more like a real browser
        await self.page.set_extra_http_headers({
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site',
        })

        print("Browser started successfully")

    async def stop(self):
        """Stop the browser."""
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        print("Browser stopped")

    async def download_image(self, url: str, save_path: str, max_retries: int = 4) -> Tuple[bool, int]:
        """
        Download a single image, with retry on 429.

        Uses the browser context's request API rather than page.goto(). Chrome
        treats a direct upload.wikimedia.org image URL as a *download*, not a
        navigation, so page.goto() threw "Download is starting" on essentially
        every file and response.body() raced the inspector cache eviction. Each
        throw then slept 5s x 4 retries, which burned ~45 min of Actions time
        per run and starved every short to "too few photos downloaded".
        request.get() shares the context's cookies, UA and headers but returns
        the bytes directly, with no navigation and no download interception.
        """
        if not self.page:
            print("  Error: Browser not started")
            return False, 0

        for attempt in range(max_retries + 1):
            try:
                response = await self.page.request.get(url, timeout=30000)
                status = response.status

                if response.ok:
                    content = await response.body()
                    if not content:
                        print("  Empty body")
                        return False, status
                    with open(save_path, 'wb') as f:
                        f.write(content)
                    self._consecutive_429s = 0
                    return True, status

                if status == 429:
                    self._consecutive_429s += 1
                    # Exponential backoff: 15s, 30s, 60s, 120s
                    backoff = min(15 * (2 ** attempt), 120)
                    # Add jitter to avoid thundering herd
                    backoff += random.uniform(0, 5)
                    print(f"    Rate limited (429). Waiting {backoff:.0f}s before retry {attempt+1}/{max_retries}...")
                    await asyncio.sleep(backoff)
                    continue

                # 404/403/410 are permanent for this URL - do not sit in a
                # retry sleep for a file that will never exist.
                print(f"  Failed to load: {status}")
                return False, status

            except Exception as e:
                # Playwright error text can carry non-cp1252 characters (e.g. the
                # "->" arrow in its call log). Printing those raw raised
                # UnicodeEncodeError on a Windows console and took down the whole
                # run from inside the *error* handler. Force it ASCII-safe.
                msg = str(e).splitlines()[0].encode('ascii', 'replace').decode('ascii')
                print(f"  Browser download error: {msg}")
                if attempt < max_retries:
                    await asyncio.sleep(2)
                    continue
                return False, 0

        print(f"  All {max_retries} retries exhausted (429)")
        return False, 429


if __name__ == "__main__":
    async def test_download():
        """Test the browser downloader with a few images."""
        test_images = [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/8/85/Affairs_of_Anatol_cast.jpg/1920px-Affairs_of_Anatol_cast.jpg',
            'https://upload.wikimedia.org/wikipedia/commons/b/b3/1919-lon-chaney-miracle-man-still.jpg',
        ]

        downloader = BrowserDownloader()
        await downloader.start()
        for i, url in enumerate(test_images):
            save_path = os.path.join(config.OUTPUT_FOLDER, f'test_{i}.jpg')
            success, status = await downloader.download_image(url, save_path)
            print(f"  {url[:60]}... -> {'OK' if success else f'FAIL ({status})'}")
            await asyncio.sleep(3)
        await downloader.stop()

    print("Testing Browser Downloader...")
    asyncio.run(test_download())
