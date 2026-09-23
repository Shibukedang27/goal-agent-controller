from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import quote

@dataclass
class BrowserEvidence:
    operation: str; url: str; title: str = ""; content: str = ""; links: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat()); status: str = "success"; error: str | None = None
    retrieval_method: str = "urllib-read-only"

class _Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]; self.links=[]
    def handle_data(self, data): self.parts.append(data.strip())
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href: self.links.append(href)

class BrowserTool:
    """Real, bounded, read-only retrieval; no script execution or writes."""
    def __init__(self, timeout: int = 8, max_pages: int = 3, enabled: bool = True): self.timeout, self.max_pages, self.enabled, self.pages = timeout, max_pages, enabled, 0
    def open(self, url: str) -> BrowserEvidence:
        if not self.enabled: return BrowserEvidence("open", url, status="blocked", error="SOURCE_DISCOVERY_BLOCKED")
        if self.pages >= self.max_pages: return BrowserEvidence("open", url, status="blocked", error="page_limit_reached")
        try:
            self.pages += 1; req = Request(url, headers={"User-Agent":"agi-research-prototype/0.1"})
            with urlopen(req, timeout=self.timeout) as response: raw = response.read(2_000_000)
            parser = _Text(); parser.feed(raw.decode("utf-8", errors="replace")); text = " ".join(x for x in parser.parts if x)
            return BrowserEvidence("open", url, content=text[:100_000], links=parser.links)
        except TimeoutError: return BrowserEvidence("open", url, status="failed", error="timeout")
        except Exception as exc: return BrowserEvidence("open", url, status="failed", error=f"page_unavailable:{type(exc).__name__}")
    def search(self, query: str) -> BrowserEvidence: return self.open("https://html.duckduckgo.com/html/?q=" + quote(query))
