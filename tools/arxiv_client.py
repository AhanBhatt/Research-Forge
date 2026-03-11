"""Client for arXiv paper discovery."""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime
from urllib.parse import urlencode

import feedparser
import requests

from schemas.paper import Paper

LOGGER = logging.getLogger(__name__)


class ArxivClient:
    """Thin client around the arXiv Atom API."""

    def __init__(
        self,
        api_url: str,
        timeout_seconds: int = 20,
        max_retries: int = 2,
        backoff_seconds: float = 2.0,
        max_results_per_query: int = 16,
    ) -> None:
        # arXiv HTTP endpoint is often blocked by local/corporate policy; prefer HTTPS.
        if api_url.startswith("http://") and "export.arxiv.org" in api_url:
            self.api_url = api_url.replace("http://", "https://", 1)
        else:
            self.api_url = api_url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.backoff_seconds = max(0.5, backoff_seconds)
        self.max_results_per_query = max(1, max_results_per_query)
        self._session = requests.Session()
        self._headers = {"User-Agent": "ResearchForge/0.1 (local research agent)"}
        self._cooldown_until = 0.0

    def search(
        self,
        topic: str,
        max_results: int = 20,
        preferred_categories: list[str] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[Paper], list[str]]:
        """Return papers and query attempts."""

        attempts: list[str] = []
        primary_query = self._build_query(topic, preferred_categories)
        attempts.append(primary_query)
        papers = self._execute_query(primary_query, max_results, date_from, date_to)

        if papers:
            return papers, attempts

        # Fallback 1: broader token query with category constraint.
        fallback_terms = self._topic_keywords(topic)
        fallback_query = self._build_keyword_query(fallback_terms[:4], preferred_categories)
        if fallback_query != primary_query:
            attempts.append(fallback_query)
            papers = self._execute_query(fallback_query, max_results, date_from, date_to)
            if papers:
                return papers, attempts

        # Fallback 2: drop category filters entirely.
        unrestricted_query = self._build_keyword_query(fallback_terms[:4], preferred_categories=None)
        if unrestricted_query and unrestricted_query not in attempts:
            attempts.append(unrestricted_query)
            papers = self._execute_query(unrestricted_query, max_results, date_from, date_to)

        return papers, attempts

    def _build_query(self, topic: str, preferred_categories: list[str] | None) -> str:
        cleaned = re.sub(r"\s+", " ", topic.strip())
        query_parts = [f'all:"{cleaned}"']
        if preferred_categories:
            cats = " OR ".join(f"cat:{cat}" for cat in preferred_categories)
            query_parts.append(f"({cats})")
        return " AND ".join(query_parts)

    def _build_keyword_query(self, tokens: list[str], preferred_categories: list[str] | None) -> str:
        filtered = [token for token in tokens if token]
        if not filtered:
            return ""
        # Use OR over keywords to avoid over-constraining noisy topics.
        keyword_block = " OR ".join(f"all:{token}" for token in filtered)
        query_parts = [f"({keyword_block})"]
        if preferred_categories:
            cats = " OR ".join(f"cat:{cat}" for cat in preferred_categories)
            query_parts.append(f"({cats})")
        return " AND ".join(query_parts)

    def _execute_query(
        self,
        query: str,
        max_results: int,
        date_from: date | None,
        date_to: date | None,
    ) -> list[Paper]:
        now = time.monotonic()
        if now < self._cooldown_until:
            remaining = self._cooldown_until - now
            LOGGER.warning("Skipping arXiv query during cooldown window (%.1fs remaining).", remaining)
            return []

        capped_results = min(max(1, max_results), self.max_results_per_query)
        params = {
            "search_query": query,
            "start": 0,
            "max_results": capped_results,
            "sortBy": "lastUpdatedDate",
            "sortOrder": "descending",
        }
        url = f"{self.api_url}?{urlencode(params)}"
        for attempt in range(self.max_retries + 1):
            try:
                response = self._session.get(url, timeout=self.timeout_seconds, headers=self._headers)
            except requests.Timeout as exc:
                if attempt >= self.max_retries:
                    LOGGER.warning("arXiv query timed out after retries: %s", exc)
                    return []
                wait = self._compute_backoff(attempt)
                LOGGER.warning("arXiv query timed out; retrying in %.1fs (attempt %d/%d).", wait, attempt + 1, self.max_retries)
                time.sleep(wait)
                continue
            except requests.RequestException as exc:
                LOGGER.warning("arXiv query failed: %s", exc)
                return []

            if response.status_code == 429:
                wait = self._retry_after_seconds(response, attempt)
                self._cooldown_until = max(self._cooldown_until, time.monotonic() + wait)
                if attempt >= self.max_retries:
                    LOGGER.warning("arXiv query failed with 429 after retries; cooling down for %.1fs.", wait)
                    return []
                LOGGER.warning("arXiv rate limited (429); retrying in %.1fs (attempt %d/%d).", wait, attempt + 1, self.max_retries)
                time.sleep(wait)
                continue

            if response.status_code >= 500:
                if attempt >= self.max_retries:
                    LOGGER.warning("arXiv server error after retries: %s", response.status_code)
                    return []
                wait = self._compute_backoff(attempt)
                LOGGER.warning("arXiv server error %s; retrying in %.1fs.", response.status_code, wait)
                time.sleep(wait)
                continue

            try:
                response.raise_for_status()
            except requests.RequestException as exc:
                LOGGER.warning("arXiv query failed: %s", exc)
                return []

            feed = feedparser.parse(response.text)
            return self._parse_feed(feed, date_from, date_to)

        return []

    def _parse_feed(
        self,
        feed: feedparser.FeedParserDict,
        date_from: date | None,
        date_to: date | None,
    ) -> list[Paper]:
        seen_ids: set[str] = set()
        papers: list[Paper] = []

        for entry in feed.entries:
            arxiv_id = self._extract_arxiv_id(getattr(entry, "id", ""))
            if not arxiv_id or arxiv_id in seen_ids:
                continue

            published = self._parse_datetime(getattr(entry, "published", None))
            updated = self._parse_datetime(getattr(entry, "updated", None))
            if not self._passes_date_filter(published, updated, date_from, date_to):
                continue

            paper = Paper(
                arxiv_id=arxiv_id,
                title=(getattr(entry, "title", "") or "").strip().replace("\n", " "),
                abstract=(getattr(entry, "summary", "") or "").strip().replace("\n", " "),
                authors=[a.name for a in getattr(entry, "authors", []) if getattr(a, "name", None)],
                categories=[t.term for t in getattr(entry, "tags", []) if getattr(t, "term", None)],
                published=published,
                updated=updated,
                pdf_url=self._extract_pdf_url(getattr(entry, "links", [])),
            )
            papers.append(paper)
            seen_ids.add(arxiv_id)
        return papers

    def _retry_after_seconds(self, response: requests.Response, attempt: int) -> float:
        header = response.headers.get("Retry-After", "").strip()
        if header.isdigit():
            return min(60.0, max(1.0, float(header)))
        return self._compute_backoff(attempt)

    def _compute_backoff(self, attempt: int) -> float:
        return min(30.0, self.backoff_seconds * (2**attempt))

    @staticmethod
    def _extract_pdf_url(links: list[object]) -> str | None:
        for link in links:
            href = getattr(link, "href", None)
            link_type = getattr(link, "type", "")
            if href and "pdf" in link_type:
                return href
        return None

    @staticmethod
    def _extract_arxiv_id(entry_id: str) -> str:
        # Entry ID usually ends with /abs/<id>.
        match = re.search(r"/abs/([^/?]+)", entry_id)
        return match.group(1) if match else entry_id.rsplit("/", maxsplit=1)[-1]

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _passes_date_filter(
        published: datetime | None,
        updated: datetime | None,
        date_from: date | None,
        date_to: date | None,
    ) -> bool:
        reference = updated or published
        if reference is None:
            return True
        ref_date = reference.date()
        if date_from and ref_date < date_from:
            return False
        if date_to and ref_date > date_to:
            return False
        return True

    @staticmethod
    def _topic_keywords(topic: str) -> list[str]:
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "for",
            "of",
            "to",
            "in",
            "on",
            "with",
            "using",
            "based",
            "study",
            "analysis",
        }
        tokens = re.findall(r"[A-Za-z0-9\-]+", topic.lower())
        return [token for token in tokens if token not in stop_words]
