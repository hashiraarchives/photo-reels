"""
AAP - Actress Actor and Pinups
Wikimedia Commons Description Scraper

Fetches factual metadata from Wikimedia Commons pages to generate
accurate, informative descriptions for each image.
"""

import requests
from bs4 import BeautifulSoup
import time
import re
import json
from typing import Optional, Dict, List
import config


def get_wikimedia_description(file_page_url: str) -> Dict[str, Optional[str]]:
    """
    Scrape metadata from a Wikimedia Commons file page.

    Returns dict with:
        - title: The file title/subject
        - description: Full description text
        - date: Date of the photograph
        - author: Photographer/creator
        - generated_caption: AI-friendly 10-20 word caption
    """
    headers = {
        "User-Agent": "VintageArchiveBot/1.0 (https://github.com/hashiraarchives; public-domain photo compilations) python-requests"
    }

    result = {
        "title": None,
        "description": None,
        "date": None,
        "author": None,
        "generated_caption": None
    }

    for attempt in range(config.MAX_RETRIES):
        try:
            response = requests.get(file_page_url, headers=headers, timeout=10)
            response.raise_for_status()
            break
        except requests.RequestException as e:
            if attempt < config.MAX_RETRIES - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            print(f"Failed to fetch {file_page_url}: {e}")
            return result

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract file title from page
    title_elem = soup.find('h1', {'id': 'firstHeading'})
    if title_elem:
        title = title_elem.get_text().replace('File:', '').strip()
        # Clean up filename to get subject
        title = re.sub(r'\.(jpg|jpeg|png|gif|tif|tiff)$', '', title, flags=re.IGNORECASE)
        title = title.replace('_', ' ')
        result["title"] = title

    # Find the file description section
    description_table = soup.find('table', {'class': 'fileinfotpl-type-information'})
    if not description_table:
        description_table = soup.find('table', {'class': 'wikitable'})

    if description_table:
        # Look for Description row
        for row in description_table.find_all('tr'):
            header = row.find('th') or row.find('td', {'class': 'fileinfo-paramfield'})
            if header:
                header_text = header.get_text().strip().lower()
                value_cell = row.find('td', {'class': 'fileinfo-paramvalue'}) or row.find_all('td')[-1] if row.find_all('td') else None

                if value_cell:
                    value = value_cell.get_text().strip()

                    if 'description' in header_text:
                        result["description"] = clean_text(value)
                    elif 'date' in header_text:
                        result["date"] = clean_text(value)
                    elif 'author' in header_text or 'source' in header_text:
                        result["author"] = clean_text(value)

    # Also check for description in commons metadata
    desc_div = soup.find('div', {'class': 'description'})
    if desc_div and not result["description"]:
        result["description"] = clean_text(desc_div.get_text())

    # Try to extract from structured data
    sd_table = soup.find('table', {'class': 'commons-file-information-table'})
    if sd_table:
        for row in sd_table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) >= 2:
                label = cells[0].get_text().strip().lower()
                value = cells[1].get_text().strip()

                if 'description' in label and not result["description"]:
                    result["description"] = clean_text(value)
                elif 'date' in label and not result["date"]:
                    result["date"] = clean_text(value)
                elif 'author' in label and not result["author"]:
                    result["author"] = clean_text(value)

    # Generate a caption from available data
    result["generated_caption"] = generate_caption(result)

    return result


def clean_text(text: str) -> str:
    """Clean up scraped text by removing extra whitespace and newlines."""
    if not text:
        return ""
    # Remove multiple spaces/newlines
    text = re.sub(r'\s+', ' ', text)
    # Remove Wikipedia citation brackets
    text = re.sub(r'\[\d+\]', '', text)
    # Remove "English:" or language prefixes
    text = re.sub(r'^(English|Deutsch|Fran[cç]ais|Espa[nñ]ol):\s*', '', text, flags=re.IGNORECASE)
    return text.strip()


def _clean_wikimedia_title(raw_title: str) -> str:
    """
    Clean a Wikimedia filename into a readable subject line.
    E.g. 'Marlon Brando - The Wild One (1953) publicity still 2' -> 'Marlon Brando'
    """
    title = raw_title.strip()
    # Remove common Wikimedia filename noise
    title = re.sub(r'\s*-\s*restored.*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\(cropped\).*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\(restored\).*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\bpublicity\s*(still|photo|shot)\s*\d*', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\bfilm\s*still\s*\d*', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\bpress\s*photo\s*\d*', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\bportrait\s*\d*', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\bheadshot\s*\d*', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s+\d{1,2}\s*$', '', title)  # trailing numbers like " 2"
    title = re.sub(r'\s+', ' ', title).strip()
    # Remove trailing hyphens/dashes left behind
    title = re.sub(r'\s*[-–—]\s*$', '', title).strip()
    return title


def _extract_year(text: str) -> Optional[str]:
    """Extract a 4-digit year (1900-2030) from text."""
    match = re.search(r'\b(19\d{2}|20[0-2]\d)\b', text)
    return match.group(1) if match else None


def _extract_person_and_context(title: str, description: str) -> dict:
    """
    Parse title and description to extract structured info:
    person name, movie/show title, year, and context.
    """
    info = {'person': None, 'movie': None, 'year': None, 'context': None}

    # Try to find year from title first, then description, then date
    info['year'] = _extract_year(title) or _extract_year(description or '')

    # Remove year from title to avoid duplication
    clean_title = re.sub(r'\s*\(?\b(19\d{2}|20[0-2]\d)\b\)?\s*', ' ', title).strip()
    clean_title = _clean_wikimedia_title(clean_title)

    # Pattern: "Name in Movie Title" or "Name - Movie Title"
    in_match = re.match(r'^(.+?)\s+(?:in|from|for|as\s+\w+\s+in)\s+["\']?(.+?)["\']?\s*$', clean_title, re.IGNORECASE)
    dash_match = re.match(r'^(.+?)\s*[-–—]\s*(.+?)\s*$', clean_title)

    if in_match:
        info['person'] = in_match.group(1).strip()
        info['movie'] = in_match.group(2).strip()
    elif dash_match:
        # "Marlon Brando - The Wild One" pattern
        left, right = dash_match.group(1).strip(), dash_match.group(2).strip()
        # The shorter side with capital words is likely the person
        if re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+', left):
            info['person'] = left
            info['movie'] = right
        else:
            info['person'] = clean_title  # Can't parse, use whole title
    else:
        info['person'] = clean_title

    # Try to extract movie from description if not found in title
    if not info['movie'] and description:
        movie_patterns = [
            r'(?:from|in|for)\s+(?:the\s+)?(?:film|movie|picture|motion picture)\s+["\']?([^"\',.]+)["\']?',
            r'(?:from|in|for)\s+["\']([^"\']+)["\']',
        ]
        for pattern in movie_patterns:
            m = re.search(pattern, description, re.IGNORECASE)
            if m and len(m.group(1).strip()) < 50:
                info['movie'] = m.group(1).strip()
                break

    # Extract year from description if not found yet
    if not info['year'] and description:
        info['year'] = _extract_year(description)

    return info


def generate_caption(metadata: Dict[str, Optional[str]]) -> str:
    """
    Generate a clean, readable caption from Wikimedia metadata.
    Format: "Person Name in 'Movie Title' (Year)" or "Person Name, Year"
    Avoids redundancy, metadata dumps, and truncation artifacts.
    """
    title = metadata.get("title", "") or ""
    description = metadata.get("description", "") or ""
    date_str = metadata.get("date", "") or ""

    # Parse structured info from metadata
    info = _extract_person_and_context(title, description)

    # Also try to get year from the date field
    if not info['year'] and date_str:
        info['year'] = _extract_year(date_str)

    # Build clean caption
    parts = []

    if info['person']:
        parts.append(info['person'])

    if info['movie']:
        # Clean up movie title - remove redundant year if it matches
        movie = info['movie']
        if info['year']:
            movie = re.sub(r'\s*\(?' + re.escape(info['year']) + r'\)?\s*', ' ', movie).strip()
        if movie:
            parts.append(f'in "{movie}"')

    if info['year']:
        parts.append(f"({info['year']})")

    caption = " ".join(parts)

    # If caption is too short or empty, try description-based fallback
    if len(caption.split()) < 3 and description:
        # Use first sentence of description, cleaned up
        first_sentence = re.split(r'[.!]', description)[0].strip()
        if len(first_sentence) > 10 and len(first_sentence) < 80:
            caption = first_sentence

    # Final fallback
    if not caption or len(caption) < 5:
        if title:
            caption = _clean_wikimedia_title(title)
        else:
            caption = ""

    # Ensure reasonable length (max 150 chars — longer detailed captions for 65+ audience)
    if len(caption) > 150:
        truncated = caption[:147]
        last_space = truncated.rfind(' ')
        if last_space > 80:
            caption = truncated[:last_space]
        else:
            caption = truncated

    return caption


def enhance_captions_with_gemini(image_list: List[Dict]) -> List[Dict]:
    """
    Use Gemini to rewrite all captions in one batch call.
    Makes captions engaging and contextual instead of dry metadata.
    Falls back gracefully to the regex-generated captions if Gemini fails.
    """
    try:
        from google import genai
    except ImportError:
        print("  google-genai not installed, skipping caption enhancement")
        return image_list

    api_key = getattr(config, 'GEMINI_API_KEY', None)
    if not api_key:
        print("  No Gemini API key, skipping caption enhancement")
        return image_list

    # Build a compact list of raw metadata for Gemini
    entries = []
    for i, img in enumerate(image_list):
        entry = {
            'i': i,
            'title': (img.get('title') or '')[:120],
            'desc': (img.get('description') or '')[:250],
            'date': (img.get('date') or '')[:30],
            'author': (img.get('author') or '')[:80],
            'current': (img.get('generated_caption') or '')[:120],
        }
        entries.append(entry)

    prompt = f"""Rewrite these {len(entries)} vintage photo captions for a YouTube slideshow.
Audience: classic-Hollywood fans. Each caption is a LARGE on-screen overlay, so it must be
SUCCINCT and CLEAR — the eye reads it in a glance.

RULES:
- SHORT: 4 to 12 words, absolute max ~14. One line ideally; never more than two.
- STRUCTURE: FULL NAME, then ORIGIN (nationality / where they're from, OR the film/role context),
  then the YEAR, plus ONE brief interesting detail only if it still fits.
- ALWAYS include the year when known. Do NOT repeat the year.
- Examples of GOOD succinct captions:
  - "Hedy Lamarr — Austrian-American star & inventor, 1940"
  - "Rita Hayworth in 'Gilda', 1946 — Hollywood's 'Love Goddess'"
  - "Greta Garbo, Swedish-born screen legend, 1932"
  - "James Dean, Indiana-born icon, 1955"
  - "Ava Gardner, North Carolina farm girl turned star, 1951"
- NO filler: never "publicity photo", "film still", "photograph of", "posing", "captured".
- Do NOT invent facts — use only the title/description/date provided. If sparse, just
  "{'{'}Name{'}'}, {'{'}year{'}'}" or "{'{'}Name{'}'}, classic Hollywood star, circa {'{'}year{'}'}".
- Elegant and factual; no clickbait, no ALL CAPS.

INPUT (JSON array):
{json.dumps(entries, ensure_ascii=False)}

OUTPUT: Return ONLY a JSON array of {len(entries)} strings (the rewritten captions), in the same order. No markdown, no explanation."""

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-3-flash-preview',
            contents=prompt,
        )

        text = response.text.strip()
        # Remove markdown code fences
        if text.startswith('```'):
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)

        captions = json.loads(text)

        if isinstance(captions, list) and len(captions) == len(image_list):
            enhanced = 0
            for i, cap in enumerate(captions):
                if isinstance(cap, str) and len(cap) > 3:
                    image_list[i]['generated_caption'] = cap
                    enhanced += 1
            print(f"  Gemini enhanced {enhanced}/{len(image_list)} captions")
        else:
            print(f"  Gemini returned wrong format ({type(captions).__name__}, len={len(captions) if isinstance(captions, list) else 'N/A'}), keeping regex captions")

    except json.JSONDecodeError as e:
        print(f"  Gemini returned invalid JSON: {e}")
    except Exception as e:
        print(f"  Gemini caption enhancement failed: {e}")

    return image_list


def scrape_batch(image_list: List[Dict], enhance: bool = True) -> List[Dict]:
    """
    Scrape descriptions for a batch of images, then optionally
    enhance captions with Gemini AI.

    Args:
        image_list: List of dicts with 'file_page_url' key

    Returns:
        Same list with added metadata fields
    """
    total = len(image_list)

    for i, image in enumerate(image_list):
        url = image.get("file_page_url")
        if not url:
            print(f"[{i+1}/{total}] Skipping - no URL")
            continue

        print(f"[{i+1}/{total}] Scraping: {url[:60]}...")

        metadata = get_wikimedia_description(url)
        image.update(metadata)

        # Rate limiting
        if i < total - 1:
            time.sleep(config.WIKIMEDIA_DELAY)

    # Enhance captions with Gemini AI (single batch call)
    print("\n  Enhancing captions with Gemini AI...")
    # SHORTS pass enhance=False: they show only the star's name, never a
    # per-photo caption, so the Gemini rewrite would be paid for and
    # then thrown away.
    if enhance:
        image_list = enhance_captions_with_gemini(image_list)

    return image_list


def save_descriptions(image_list: List[Dict], output_path: str):
    """Save scraped descriptions to JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(image_list, f, indent=2, ensure_ascii=False)
    print(f"Saved descriptions to {output_path}")


def load_descriptions(input_path: str) -> List[Dict]:
    """Load previously scraped descriptions from JSON file."""
    with open(input_path, 'r', encoding='utf-8') as f:
        return json.load(f)


if __name__ == "__main__":
    # Test with a single image
    test_url = "https://commons.wikimedia.org/wiki/File:1919-lon-chaney-miracle-man-still.jpg"
    print("Testing scraper with:", test_url)
    result = get_wikimedia_description(test_url)
    print("\nResult:")
    for key, value in result.items():
        print(f"  {key}: {value}")
