import requests

from tools.arxiv_client import ArxivClient


SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2501.12345v1</id>
    <updated>2026-01-10T00:00:00Z</updated>
    <published>2026-01-09T00:00:00Z</published>
    <title>Test Paper</title>
    <summary>Test abstract</summary>
    <author><name>Alice</name></author>
    <category term="cs.CL"/>
    <link title="pdf" href="http://arxiv.org/pdf/2501.12345v1" type="application/pdf"/>
  </entry>
</feed>
"""


class _DummyResponse:
    def __init__(self, status_code: int, text: str = "", headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def test_arxiv_caps_max_results(monkeypatch) -> None:
    client = ArxivClient(
        "https://export.arxiv.org/api/query",
        timeout_seconds=5,
        max_retries=0,
        max_results_per_query=7,
    )
    captured: dict[str, str] = {}

    def fake_get(url: str, timeout: int, headers: dict[str, str]):  # noqa: ARG001
        captured["url"] = url
        return _DummyResponse(status_code=200, text=SAMPLE_FEED)

    monkeypatch.setattr(client._session, "get", fake_get)
    papers, _attempts = client.search(topic="LLM evaluation", max_results=50)

    assert "max_results=7" in captured["url"]
    assert papers
    assert papers[0].arxiv_id.startswith("2501.12345")


def test_arxiv_429_triggers_cooldown_and_skips_fallback_requests(monkeypatch) -> None:
    client = ArxivClient(
        "https://export.arxiv.org/api/query",
        timeout_seconds=5,
        max_retries=0,
        max_results_per_query=8,
    )
    call_count = {"n": 0}

    def fake_get(url: str, timeout: int, headers: dict[str, str]):  # noqa: ARG001
        call_count["n"] += 1
        return _DummyResponse(status_code=429, headers={"Retry-After": "10"})

    monkeypatch.setattr(client._session, "get", fake_get)
    papers, _attempts = client.search(topic="LLM evaluation", max_results=8)

    assert papers == []
    # First request hits 429, then cooldown should prevent fallback requests from
    # issuing new network calls in the same search invocation.
    assert call_count["n"] == 1
