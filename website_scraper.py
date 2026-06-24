from __future__ import annotations

import re
import ssl
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urljoin, urlparse

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}")
CF_EMAIL_RE = re.compile(r'data-cfemail="([0-9a-f]+)"')

CONTACT_SLUGS = ("contact", "about", "team", "reach-us", "our-team", "staff", "connect")


class WebsiteScraper:
    def __init__(
        self,
        timeout_seconds: int = 20,
        max_pages: int = 5,
        js_fallback: Any = None,
    ) -> None:
        self.timeout = timeout_seconds
        self.max_pages = max_pages
        self.js_fallback = js_fallback
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def crawl(self, url: str) -> dict[str, Any]:
        visited: set[str] = set()
        all_text: list[str] = []
        all_emails: list[str] = []
        all_phones: list[str] = []
        pages_scraped = 0

        html = self._fetch(url)
        if html is None:
            return self._try_js_fallback(url, reason="fetch_failed")

        visited.add(url)
        pages_scraped += 1
        text, emails, phones = self._parse(html)
        all_text.append(text)
        all_emails.extend(emails)
        all_phones.extend(phones)

        if pages_scraped < self.max_pages:
            for slug in CONTACT_SLUGS:
                if pages_scraped >= self.max_pages:
                    break
                candidate = urljoin(url, f"/{slug}")
                if candidate in visited:
                    continue
                sub_html = self._fetch(candidate)
                if sub_html is None:
                    continue
                visited.add(candidate)
                pages_scraped += 1
                t, e, p = self._parse(sub_html)
                all_text.append(t)
                all_emails.extend(e)
                all_phones.extend(p)

        combined_text = "\n\n".join(filter(None, all_text))
        emails_unique = list(dict.fromkeys(all_emails))
        phones_unique = list(dict.fromkeys(all_phones))

        if _looks_js_rendered(combined_text, emails_unique, phones_unique):
            fb = self._try_js_fallback(url, reason="thin_content")
            if fb.get("text"):
                fb_text, fb_emails, fb_phones = self._parse(fb["text"])
                return {
                    "text": (combined_text + "\n\n" + fb_text)[:40_000],
                    "emails": list(dict.fromkeys(emails_unique + fb_emails)),
                    "phones": list(dict.fromkeys(phones_unique + fb_phones)),
                    "pages_scraped": pages_scraped + int(fb.get("pages_scraped", 0)),
                    "used_js_fallback": True,
                }

        return {
            "text": combined_text,
            "emails": emails_unique,
            "phones": phones_unique,
            "pages_scraped": pages_scraped,
        }

    def _try_js_fallback(self, url: str, reason: str) -> dict[str, Any]:
        if self.js_fallback is None:
            return {"text": "", "emails": [], "phones": [], "pages_scraped": 0}
        result = self.js_fallback.crawl(url)
        text = str(result.get("text", ""))
        if not text:
            return {"text": "", "emails": [], "phones": [], "pages_scraped": 0}
        parsed_text, emails, phones = self._parse(text)
        return {
            "text": parsed_text,
            "emails": emails,
            "phones": phones,
            "pages_scraped": int(result.get("pages_scraped", 0)),
            "used_js_fallback": True,
        }

    def _fetch(self, url: str) -> str | None:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; LeadBot/1.0)"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout, context=self._ssl_ctx) as resp:
                raw = resp.read(500_000)
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except Exception:
            return None

    def _parse(self, html: str) -> tuple[str, list[str], list[str]]:
        cf_emails = [_decode_cf_email(m) for m in CF_EMAIL_RE.findall(html)]

        mailto_emails = re.findall(r'href=["\']mailto:([^"\'?\s]+)', html, re.IGNORECASE)

        if HAS_BS4:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
        else:
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()

        emails = list(dict.fromkeys(cf_emails + mailto_emails + EMAIL_RE.findall(text)))
        emails = [e for e in emails if not e.endswith((".png", ".jpg", ".gif", ".svg", ".webp"))]
        phones = list(dict.fromkeys(PHONE_RE.findall(text)))
        return text[:20_000], emails, phones


def _looks_js_rendered(text: str, emails: list[str], phones: list[str]) -> bool:
    if len(text) < 600:
        return True
    if len(text) < 2000 and not emails and not phones:
        return True
    return False


def _decode_cf_email(encoded: str) -> str:
    try:
        key = int(encoded[:2], 16)
        return "".join(chr(int(encoded[i:i+2], 16) ^ key) for i in range(2, len(encoded), 2))
    except Exception:
        return ""
