"""Same-origin proxy for the small Wikimedia demo clips."""

from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        target = parse_qs(urlparse(self.path).query).get("url", [""])[0]
        if not target.startswith("https://commons.wikimedia.org/"):
            self.send_error(400, "Unsupported demo source")
            return
        try:
            request = Request(target, headers={"User-Agent": "EcoSound-Shift/1.0"})
            with urlopen(request, timeout=20) as response:
                body = response.read(3_000_001)
                content_type = response.headers.get_content_type()
            if len(body) > 3_000_000:
                self.send_error(413, "Demo clip is too large")
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type or "audio/ogg")
            self.send_header("Cache-Control", "public, max-age=3600")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            self.send_error(502, "Demo audio is temporarily unavailable")
