"""Small Wikimedia Commons audio search used by the sample library."""
from __future__ import annotations

import html
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "https://commons.wikimedia.org/w/api.php"
ALLOWED_LICENSES = {
    "CC0", "CC BY 1.0", "CC BY 2.0", "CC BY 2.5", "CC BY 3.0", "CC BY 4.0",
    "CC BY-SA 1.0", "CC BY-SA 2.0", "CC BY-SA 2.5", "CC BY-SA 3.0", "CC BY-SA 4.0",
}


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", value or ""))).strip()


def normalize_file(page: dict) -> dict | None:
    """Return a downloadable, attributed file only when a supported license is explicit."""
    info = (page.get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata") or {}
    license_name = _plain((meta.get("LicenseShortName") or {}).get("value", ""))
    if license_name not in ALLOWED_LICENSES:
        return None
    original = info.get("url", "")
    if not original.startswith("https://upload.wikimedia.org/"):
        return None
    title = page.get("title", "").removeprefix("File:")
    return {
        "title": title,
        "page_url": "https://commons.wikimedia.org/wiki/" + page.get("title", "").replace(" ", "_"),
        "audio_url": original,
        "license": license_name,
        "license_url": _plain((meta.get("LicenseUrl") or {}).get("value", "")),
        "artist": _plain((meta.get("Artist") or {}).get("value", "")) or "Creator not listed",
        "description": _plain((meta.get("ImageDescription") or {}).get("value", "")),
        "date": _plain((meta.get("DateTimeOriginal") or {}).get("value", "")),
    }


def search_audio(query: str, limit: int = 8) -> list[dict]:
    """Search Commons files; every result keeps its source and license attribution."""
    query = query.strip()
    if not query:
        return []
    params = urlencode({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f'filetype:audio "{query}"', "gsrnamespace": 6,
        "gsrlimit": max(1, min(int(limit), 20)), "prop": "imageinfo",
        "iiprop": "url|extmetadata",
    })
    request = Request(f"{API_URL}?{params}", headers={"User-Agent": "VizagBirdFinder/1.0 (bird-call sample library)"})
    with urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    pages = (payload.get("query") or {}).get("pages", {})
    rows = [normalize_file(page) for page in pages.values()]
    return [row for row in rows if row]
