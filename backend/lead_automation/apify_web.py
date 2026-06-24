from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

APIFY_BASE = "https://api.apify.com/v2"


class ApifyWebCrawler:
    def __init__(
        self,
        api_token: str,
        actor_id: str = "apify/website-content-crawler",
        timeout_seconds: int = 90,
    ) -> None:
        self.api_token = api_token
        self.actor_id = actor_id.replace("/", "~")
        self.timeout = timeout_seconds

    def crawl(self, url: str, max_pages: int = 3) -> dict[str, Any]:
        run_input = {
            "startUrls": [{"url": url}],
            "maxCrawlPages": max_pages,
            "maxCrawlDepth": 1,
            "crawlerType": "playwright:firefox",
            "saveMarkdown": True,
            "saveHtml": False,
            "removeCookieWarnings": True,
        }
        try:
            items = self._run_actor(run_input)
        except Exception:
            return {"text": "", "pages_scraped": 0}

        texts: list[str] = []
        for item in items:
            md = item.get("markdown") or item.get("text") or ""
            if md:
                texts.append(str(md))
        return {
            "text": "\n\n".join(texts)[:40_000],
            "pages_scraped": len(texts),
        }

    def _run_actor(self, run_input: dict[str, Any]) -> list[dict[str, Any]]:
        url = f"{APIFY_BASE}/acts/{self.actor_id}/runs?token={self.api_token}"
        body = json.dumps(run_input).encode()
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            run_data = json.loads(resp.read())
        run_id = run_data["data"]["id"]
        dataset_id = run_data["data"]["defaultDatasetId"]
        self._wait_for_run(run_id)
        return self._fetch_dataset(dataset_id)

    def _wait_for_run(self, run_id: str, poll_seconds: int = 4) -> None:
        url = f"{APIFY_BASE}/actor-runs/{run_id}?token={self.api_token}"
        waited = 0
        while waited < self.timeout:
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read())
            status = data["data"]["status"]
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                if status != "SUCCEEDED":
                    raise RuntimeError(f"Apify web crawler run {run_id} ended: {status}")
                return
            time.sleep(poll_seconds)
            waited += poll_seconds
        raise TimeoutError(f"Apify web crawler run {run_id} timed out after {self.timeout}s")

    def _fetch_dataset(self, dataset_id: str) -> list[dict[str, Any]]:
        url = f"{APIFY_BASE}/datasets/{dataset_id}/items?token={self.api_token}&format=json"
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read())
