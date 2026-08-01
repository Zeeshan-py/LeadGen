"""Screenshot capture utilities for website evidence and visual enrichment."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Browser, Error as PlaywrightError, Playwright, sync_playwright

from lead_automation.url_safety import is_safe_public_url

logger = logging.getLogger(__name__)


def capture_website_screenshot(url: str, output_dir: Path, public_backend_url: str) -> str:
    if not url:
        return ""
    output_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    filename = f"{digest}.png"
    path = output_dir / filename
    if path.exists():
        return f"{public_backend_url.rstrip('/')}/static/screenshots/{filename}"

    parsed = urlparse(url)
    target = url if parsed.scheme else f"https://{url}"
    if not is_safe_public_url(target, resolve=True):
        logger.warning("Blocked unsafe screenshot target: %s", target)
        return ""
    with sync_playwright() as p:
        browser = _launch_browser(p)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
            page.route("**/*", _block_unsafe_route)
            page.goto(target, wait_until="networkidle", timeout=30000)
            page.screenshot(path=str(path), full_page=False)
        finally:
            browser.close()
    return f"{public_backend_url.rstrip('/')}/static/screenshots/{filename}"


def _launch_browser(playwright: Playwright) -> Browser:
    try:
        return playwright.chromium.launch()
    except PlaywrightError:
        logger.warning(
            "Bundled Playwright Chromium is unavailable; falling back to the installed Chrome channel"
        )
        return playwright.chromium.launch(channel="chrome")


def _block_unsafe_route(route) -> None:
    if is_safe_public_url(route.request.url, resolve=False):
        route.continue_()
        return
    route.abort()
